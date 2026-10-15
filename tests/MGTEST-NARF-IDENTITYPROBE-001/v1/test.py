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
            ["builder", "authority", "principal_id"],
        ],
        "authority_verifier_id": "approve",
    }


def make_session(label, effects):
    tmp = tempfile.TemporaryDirectory(prefix=f"mgnarftest-identityprobe-{label}-")
    store = ReceiptStore(Path(tmp.name) / "receipts", b"j" * 32)
    gate = NARFGate(store)
    task = {"description": "MGnarfTest identity-probe continuity attack", "project": "mgnarf", "case": label}
    state = FrozenState(
        candidate_sha256=sha256_bytes(b"mgnarftest-identityprobe-candidate"),
        requirements_sha256=sha256_bytes(b"mgnarftest-identityprobe-requirements"),
        policy_sha256=sha256_bytes(b"mgnarftest-identityprobe-policy"),
    )
    requirements = (
        Requirement("tests", "check-a", "1"),
        Requirement("security", "check-b", "1"),
        Requirement("approval", "approve", "1"),
    )
    policy = make_policy()
    current = {"actors": deepcopy(policy["actors"]), "raise": False}

    def producer(name):
        return lambda: VerifierResult("PASS", f"evidence:{name}".encode())

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

    def identity_probe():
        if current["raise"]:
            raise RuntimeError("identity source unavailable")
        return deepcopy(current["actors"])

    contract = gate.freeze_contract(
        task,
        task_id=f"mgnarftest-identityprobe-001-{label}",
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
        identity_probe=identity_probe,
    )
    return tmp, session, current


def execute_and_finalize_pass(session):
    for requirement_id in session.requirements():
        result = session.execute(requirement_id)
        if result.get("status") != "PASS":
            raise AssertionError(f"verifier did not PASS: {requirement_id} -> {result!r}")
    final = session.finalize()
    if final.get("result") != "PASS":
        raise AssertionError(f"session did not finalize PASS: {final!r}")


def require_stale_block(session, effects, expected_reason, label):
    verdict = session.verdict()
    if verdict.get("result") != "BLOCKED" or verdict.get("reason") != expected_reason:
        print(f"FAIL: {label} was not {expected_reason}/BLOCKED: {verdict!r}")
        return False
    try:
        session.finalize()
    except NARFError:
        pass
    else:
        print(f"FAIL: {label} left authenticated PASS reusable")
        return False
    try:
        session.execute_effect()
    except NARFError:
        pass
    else:
        print(f"FAIL: {label} reached protected effect")
        return False
    if effects:
        print(f"FAIL: {label} changed protected effects: {effects!r}")
        return False
    return True


def main() -> int:
    # Attack 1: principal identity changes after authenticated PASS.
    effects = []
    tmp, session, current = make_session("principal-drift", effects)
    try:
        execute_and_finalize_pass(session)
        current["actors"]["verifier:check-a"]["principal_id"] = "ci:replacement"
        if not require_stale_block(session, effects, "IDENTITY_CHANGED", "post-PASS identity drift"):
            return 1
    finally:
        tmp.cleanup()

    # Attack 2: identity authority becomes unavailable after authenticated PASS.
    effects = []
    tmp, session, current = make_session("probe-unavailable", effects)
    try:
        execute_and_finalize_pass(session)
        current["raise"] = True
        if not require_stale_block(session, effects, "IDENTITY_UNAVAILABLE", "post-PASS identity probe loss"):
            return 1
    finally:
        tmp.cleanup()

    # Control: unchanged current identities preserve the exact PASS authority.
    effects = []
    tmp, session, _current = make_session("control", effects)
    try:
        execute_and_finalize_pass(session)
        if session.execute_effect() != "control" or effects != ["control"]:
            print(f"FAIL: unchanged identity control effect mismatch: {effects!r}")
            return 1
    finally:
        tmp.cleanup()

    print("PASS: identity drift and identity-probe loss after PASS invalidated effect authority; unchanged identities reached one effect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
