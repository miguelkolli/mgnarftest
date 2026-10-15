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


CHANGED_FIELDS = (
    "candidate_sha256",
    "requirements_sha256",
    "policy_sha256",
)


def make_session(root: Path, *, label: str, changed_field: str | None):
    calls = []
    effects = []
    store = ReceiptStore(root / f"receipts-{label}", b"m" * 32)
    gate = NARFGate(store)
    task = {"description": f"MGnarfTest mid-verification state drift case: {label}"}
    frozen = FrozenState(
        candidate_sha256=sha256_bytes(b"midverify-candidate-v1"),
        requirements_sha256=sha256_bytes(b"midverify-requirements-v1"),
        policy_sha256=sha256_bytes(b"midverify-policy-v1"),
    )
    current = {"state": frozen}

    def producer():
        calls.append("verify")
        if changed_field is not None:
            current["state"] = replace(
                frozen,
                **{changed_field: sha256_bytes(f"midverify-changed-{changed_field}".encode())},
            )
        return VerifierResult("PASS", b"midverify-proof")

    def effect():
        effects.append(label)
        return "published"

    contract_id = gate.freeze_contract(
        task,
        task_id=f"mgnarftest-midverify-001-{label}",
        requirements=(Requirement("verify", "host-check", "1"),),
        effect_id="publish",
        effect_version="1",
        state=frozen,
    )
    session = gate.open_session(
        contract_id,
        task,
        verifier_bindings=(VerifierBinding("host-check", "1", producer),),
        effect_binding=EffectBinding("publish", "1", effect),
        state_probe=lambda: current["state"],
    )
    return session, current, frozen, calls, effects


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mgnarftest-midverify-") as tmp:
        root = Path(tmp)

        for field in CHANGED_FIELDS:
            session, current, frozen, calls, effects = make_session(
                root,
                label=field,
                changed_field=field,
            )
            result = session.execute("verify")
            if result.get("status") != "BLOCKED" or result.get("reason") != "STATE_CHANGED_DURING_VERIFICATION":
                print(f"FAIL: transient {field} drift did not block verifier PASS: {result!r}")
                return 1
            if calls != ["verify"]:
                print(f"FAIL: transient {field} drift producer count mismatch: {calls!r}")
                return 1

            # Remove the transient drift after execute(). The persisted evidence must
            # remain BLOCKED; restoring the frozen state cannot convert it back to PASS.
            current["state"] = frozen
            verdict = session.verdict()
            if verdict.get("result") != "BLOCKED" or verdict.get("reason") != "VERIFIER_BLOCKED":
                print(f"FAIL: restored {field} state erased blocked evidence: {verdict!r}")
                return 1
            final = session.finalize()
            if final.get("result") != "BLOCKED" or final.get("reason") != "VERIFIER_BLOCKED":
                print(f"FAIL: restored {field} state finalized unexpectedly: {final!r}")
                return 1
            try:
                session.execute_effect()
            except NARFError:
                pass
            else:
                print(f"FAIL: transient {field} drift reached protected effect")
                return 1
            if effects:
                print(f"FAIL: transient {field} drift produced effects: {effects!r}")
                return 1

        control, current, frozen, calls, effects = make_session(
            root,
            label="control",
            changed_field=None,
        )
        result = control.execute("verify")
        if result.get("status") != "PASS":
            print(f"FAIL: unchanged control verifier did not PASS: {result!r}")
            return 1
        final = control.finalize()
        if final.get("result") != "PASS":
            print(f"FAIL: unchanged control did not finalize PASS: {final!r}")
            return 1
        if control.execute_effect() != "published" or effects != ["control"]:
            print(f"FAIL: unchanged control effect mismatch: {effects!r}")
            return 1
        if current["state"] != frozen or calls != ["verify"]:
            print(f"FAIL: unchanged control state/calls mismatch: state={current['state']!r} calls={calls!r}")
            return 1

    print("PASS: transient candidate, requirements and policy drift during verifier execution converted producer PASS to persistent BLOCKED evidence; unchanged control reached one effect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
