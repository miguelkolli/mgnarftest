#!/usr/bin/env python3
from copy import deepcopy
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


def make_policy() -> dict:
    return {
        "actors": {
            "builder": {"principal_id": "agent:builder", "trust_domain": "build-plane"},
            "verifier:check-a": {"principal_id": "ci:tests", "trust_domain": "test-plane"},
            "verifier:check-b": {"principal_id": "review:security", "trust_domain": "review-plane"},
            "authority": {"principal_id": "human:approver", "trust_domain": "approval-plane"},
        },
        "separation": [
            ["builder", "verifier:check-a", "principal_id"],
            ["verifier:check-a", "verifier:check-b", "principal_id"],
            ["verifier:check-a", "verifier:check-b", "trust_domain"],
            ["builder", "authority", "principal_id"],
        ],
        "authority_verifier_id": "approve",
    }


def make_session(label, mutate_field, effects):
    tmp = tempfile.TemporaryDirectory(prefix=f"mgnarftest-mididentity-{label}-")
    store = ReceiptStore(Path(tmp.name) / "receipts", b"m" * 32)
    gate = NARFGate(store)
    task = {"description": "MGnarfTest identity drift during verifier execution", "project": "mgnarf", "case": label}
    state = FrozenState(
        candidate_sha256=sha256_bytes(b"mgnarftest-mididentity-candidate"),
        requirements_sha256=sha256_bytes(b"mgnarftest-mididentity-requirements"),
        policy_sha256=sha256_bytes(b"mgnarftest-mididentity-policy"),
    )
    requirements = (
        Requirement("tests", "check-a", "1"),
        Requirement("security", "check-b", "1"),
        Requirement("approval", "approve", "1"),
    )
    policy = make_policy()
    current = {"actors": deepcopy(policy["actors"])}
    calls = []

    def producer(requirement_id):
        def run():
            calls.append(requirement_id)
            if requirement_id == "tests" and mutate_field is not None:
                replacement = "ci:replacement" if mutate_field == "principal_id" else "changed-domain"
                current["actors"]["verifier:check-a"][mutate_field] = replacement
            return VerifierResult("PASS", f"evidence:{requirement_id}".encode())
        return run

    bindings = []
    for requirement in requirements:
        role = "authority" if requirement.verifier_id == "approve" else f"verifier:{requirement.verifier_id}"
        actor = policy["actors"][role]
        bindings.append(
            VerifierBinding(
                requirement.verifier_id,
                requirement.verifier_version,
                producer(requirement.requirement_id),
                principal_id=actor["principal_id"],
                trust_domain=actor["trust_domain"],
            )
        )

    def effect():
        effects.append(label)
        return label

    contract = gate.freeze_contract(
        task,
        task_id=f"mgnarftest-mididentity-001-{label}",
        requirements=requirements,
        effect_id="publish",
        effect_version="1",
        state=state,
        identity_policy=policy,
    )
    session = gate.open_session(
        contract,
        task,
        verifier_bindings=bindings,
        effect_binding=EffectBinding("publish", "1", effect),
        state_probe=lambda: state,
        identity_probe=lambda: deepcopy(current["actors"]),
    )
    return tmp, store, session, current, policy, calls


def run_attack(field: str) -> bool:
    effects = []
    tmp, store, session, current, policy, calls = make_session(field, field, effects)
    try:
        result = session.execute("tests")
        if result.get("status") != "BLOCKED" or result.get("reason") != "STATE_CHANGED_DURING_VERIFICATION":
            print(f"FAIL: {field} drift did not override producer PASS: {result!r}")
            return False
        evidence = store.load(result["evidence_id"])
        if evidence.get("status") != "BLOCKED" or evidence.get("reason") != "STATE_CHANGED_DURING_VERIFICATION":
            print(f"FAIL: {field} drift persisted wrong verifier evidence: {evidence!r}")
            return False

        # Restore the trusted identity view after the producer returns. The already
        # persisted BLOCKED evidence must remain authoritative.
        current["actors"] = deepcopy(policy["actors"])
        for requirement_id in ("security", "approval"):
            followup = session.execute(requirement_id)
            if followup.get("status") != "PASS":
                print(f"FAIL: {field} attack follow-up verifier did not PASS: {followup!r}")
                return False

        verdict = session.verdict()
        if verdict.get("result") != "BLOCKED" or verdict.get("reason") != "VERIFIER_BLOCKED":
            print(f"FAIL: restoring identity healed blocked {field} evidence: {verdict!r}")
            return False
        final = session.finalize()
        if final.get("result") != "BLOCKED" or final.get("reason") != "VERIFIER_BLOCKED":
            print(f"FAIL: {field} attack did not finalize VERIFIER_BLOCKED: {final!r}")
            return False
        try:
            session.execute_effect()
        except NARFError:
            pass
        else:
            print(f"FAIL: {field} drift reached protected effect")
            return False
        if effects:
            print(f"FAIL: {field} drift changed protected effects: {effects!r}")
            return False
        if calls != ["tests", "security", "approval"]:
            print(f"FAIL: {field} verifier call sequence mismatch: {calls!r}")
            return False
        return True
    finally:
        tmp.cleanup()


def main() -> int:
    for field in ("principal_id", "trust_domain"):
        if not run_attack(field):
            return 1

    effects = []
    tmp, store, control, _current, _policy, calls = make_session("control", None, effects)
    try:
        for requirement_id in control.requirements():
            result = control.execute(requirement_id)
            if result.get("status") != "PASS":
                print(f"FAIL: unchanged identity control verifier did not PASS: {requirement_id} -> {result!r}")
                return 1
            evidence = store.load(result["evidence_id"])
            if evidence.get("status") != "PASS" or evidence.get("reason") != "VERIFIER_PASS":
                print(f"FAIL: unchanged identity control evidence mismatch: {evidence!r}")
                return 1
        final = control.finalize()
        if final.get("result") != "PASS":
            print(f"FAIL: unchanged identity control did not finalize PASS: {final!r}")
            return 1
        if control.execute_effect() != "control" or effects != ["control"]:
            print(f"FAIL: unchanged identity control effect mismatch: {effects!r}")
            return 1
        if calls != ["tests", "security", "approval"]:
            print(f"FAIL: unchanged identity control call sequence mismatch: {calls!r}")
            return 1
    finally:
        tmp.cleanup()

    print("PASS: principal and trust-domain drift during verifier execution overrode producer PASS and remained BLOCKED after identity restoration; unchanged control reached one effect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
