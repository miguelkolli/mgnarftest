#!/usr/bin/env python3
from dataclasses import replace
import tempfile
from pathlib import Path

from narf import (
    EffectBinding,
    FrozenState,
    NARFError,
    NARFGate,
    ReceiptStore,
    Requirement,
    VerifierBinding,
    VerifierResult,
    sha256_bytes,
)


EXPECTED_REASONS = {
    "candidate_sha256": "CANDIDATE_CHANGED",
    "requirements_sha256": "GOALPOST_CHANGED",
    "policy_sha256": "POLICY_CHANGED",
}


def run_case(root: Path, *, changed_field: str | None, label: str):
    effects = []
    store = ReceiptStore(root / f"receipts-{label}", b"s" * 32)
    gate = NARFGate(store)
    task = {"description": f"MGnarfTest post-PASS state binding case: {label}"}
    frozen = FrozenState(
        candidate_sha256=sha256_bytes(b"state-candidate-v1"),
        requirements_sha256=sha256_bytes(b"state-requirements-v1"),
        policy_sha256=sha256_bytes(b"state-policy-v1"),
    )
    current = {"state": frozen}
    requirements = (
        Requirement("tests", "check-a", "1"),
        Requirement("security", "check-b", "1"),
    )
    bindings = (
        VerifierBinding("check-a", "1", lambda: VerifierResult("PASS", b"state-tests-proof")),
        VerifierBinding("check-b", "1", lambda: VerifierResult("PASS", b"state-security-proof")),
    )

    def effect():
        effects.append("published")
        return "published"

    contract_id = gate.freeze_contract(
        task,
        task_id=f"mgnarftest-state-001-{label}",
        requirements=requirements,
        effect_id="publish",
        effect_version="1",
        state=frozen,
    )
    session = gate.open_session(
        contract_id,
        task,
        verifier_bindings=bindings,
        effect_binding=EffectBinding("publish", "1", effect),
        state_probe=lambda: current["state"],
    )

    for requirement_id in ("tests", "security"):
        result = session.execute(requirement_id)
        if result.get("status") != "PASS":
            raise RuntimeError(f"verification did not PASS for {label}: {requirement_id} -> {result!r}")
    final = session.finalize()
    if final.get("result") != "PASS":
        raise RuntimeError(f"session did not finalize PASS for {label}: {final!r}")

    if changed_field is not None:
        current["state"] = replace(
            frozen,
            **{changed_field: sha256_bytes(f"changed-{changed_field}".encode())},
        )

    return session, effects


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mgnarftest-state-") as tmp:
        root = Path(tmp)

        for field, expected_reason in EXPECTED_REASONS.items():
            session, effects = run_case(root, changed_field=field, label=field)
            verdict = session.verdict()
            if verdict.get("result") != "BLOCKED" or verdict.get("reason") != expected_reason:
                print(
                    f"FAIL: post-PASS {field} drift was not blocked as {expected_reason}: {verdict!r}"
                )
                return 1
            try:
                session.execute_effect()
            except NARFError:
                pass
            else:
                print(f"FAIL: post-PASS {field} drift reached protected effect")
                return 1
            if effects:
                print(f"FAIL: blocked post-PASS {field} drift produced effects: {effects!r}")
                return 1

        control, control_effects = run_case(root, changed_field=None, label="unchanged-control")
        if control.execute_effect() != "published" or control_effects != ["published"]:
            print(f"FAIL: unchanged control path effect mismatch: {control_effects!r}")
            return 1

    print("PASS: candidate, requirements and policy drift after PASS all blocked effect; unchanged state reached exactly one guarded effect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
