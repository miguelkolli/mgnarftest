#!/usr/bin/env python3
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


def make_session(label, effects):
    tmp = tempfile.TemporaryDirectory(prefix=f"mgnarftest-coverage-{label}-")
    store = ReceiptStore(Path(tmp.name) / "receipts", b"g" * 32)
    gate = NARFGate(store)
    task = {"description": "MGnarfTest evidence coverage attack", "project": "mgnarf", "case": label}
    state = FrozenState(
        candidate_sha256=sha256_bytes(b"mgnarftest-coverage-candidate"),
        requirements_sha256=sha256_bytes(b"mgnarftest-coverage-requirements"),
        policy_sha256=sha256_bytes(b"mgnarftest-coverage-policy"),
    )
    requirements = (
        Requirement("unit", "host-tests", "1"),
        Requirement("policy", "policy-check", "1"),
    )
    contract = gate.freeze_contract(
        task,
        task_id=f"mgnarftest-coverage-001-{label}",
        requirements=requirements,
        effect_id="publish",
        effect_version="1",
        state=state,
    )
    bindings = (
        VerifierBinding("host-tests", "1", lambda: VerifierResult("PASS", b"unit-proof")),
        VerifierBinding("policy-check", "1", lambda: VerifierResult("PASS", b"policy-proof")),
    )

    def effect():
        effects.append(label)
        return label

    session = gate.open_session(
        contract,
        task,
        verifier_bindings=bindings,
        effect_binding=EffectBinding("publish", "1", effect),
        state_probe=lambda: state,
    )
    return tmp, session


def require_blocked_incomplete(session, effects, label):
    verdict = session.verdict()
    if verdict.get("result") != "BLOCKED" or verdict.get("reason") != "INCOMPLETE_EVIDENCE":
        print(f"FAIL: {label} was not INCOMPLETE_EVIDENCE/BLOCKED: {verdict!r}")
        return False
    final = session.finalize()
    if final.get("result") != "BLOCKED" or final.get("reason") != "INCOMPLETE_EVIDENCE":
        print(f"FAIL: {label} did not finalize INCOMPLETE_EVIDENCE/BLOCKED: {final!r}")
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
    # Attack 1: one of two frozen requirements is never executed.
    effects = []
    tmp, session = make_session("missing-policy", effects)
    try:
        first = session.execute("unit")
        if first.get("status") != "PASS":
            print(f"FAIL: first requirement did not PASS: {first!r}")
            return 1
        if not require_blocked_incomplete(session, effects, "missing required evidence"):
            return 1
    finally:
        tmp.cleanup()

    # Attack 2: replaying the already executed requirement cannot fill the missing requirement.
    effects = []
    tmp, session = make_session("duplicate-unit", effects)
    try:
        first = session.execute("unit")
        if first.get("status") != "PASS":
            print(f"FAIL: duplicate attack first execution did not PASS: {first!r}")
            return 1
        try:
            session.execute("unit")
        except NARFError:
            pass
        else:
            print("FAIL: duplicate requirement execution was accepted")
            return 1
        if session.verdict().get("coverage") != "1/2":
            print(f"FAIL: duplicate requirement changed coverage: {session.verdict()!r}")
            return 1
        if not require_blocked_incomplete(session, effects, "duplicate requirement replay"):
            return 1
    finally:
        tmp.cleanup()

    # Attack 3: evidence for an unknown requirement is not accepted as coverage.
    effects = []
    tmp, session = make_session("unknown-requirement", effects)
    try:
        try:
            session.execute("not-frozen")
        except NARFError:
            pass
        else:
            print("FAIL: unknown requirement was accepted")
            return 1
        if session.verdict().get("coverage") != "0/2":
            print(f"FAIL: unknown requirement changed coverage: {session.verdict()!r}")
            return 1
        if not require_blocked_incomplete(session, effects, "unknown requirement"):
            return 1
    finally:
        tmp.cleanup()

    # Control: both distinct frozen requirements PASS exactly once.
    effects = []
    tmp, session = make_session("control", effects)
    try:
        for requirement_id in session.requirements():
            result = session.execute(requirement_id)
            if result.get("status") != "PASS":
                print(f"FAIL: control verifier did not PASS: {requirement_id} -> {result!r}")
                return 1
        final = session.finalize()
        if final.get("result") != "PASS" or final.get("coverage") != "2/2":
            print(f"FAIL: full-coverage control did not finalize PASS 2/2: {final!r}")
            return 1
        if session.execute_effect() != "control" or effects != ["control"]:
            print(f"FAIL: full-coverage control effect mismatch: {effects!r}")
            return 1
    finally:
        tmp.cleanup()

    print("PASS: missing, duplicate and unknown evidence could not satisfy frozen coverage; exact 2/2 control reached one effect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
