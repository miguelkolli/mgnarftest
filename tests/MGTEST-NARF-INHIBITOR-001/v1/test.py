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
    tmp = tempfile.TemporaryDirectory(prefix=f"mgnarftest-inhibitor-{label}-")
    store = ReceiptStore(Path(tmp.name) / "receipts", b"h" * 32)
    gate = NARFGate(store)
    task = {"description": "MGnarfTest inhibitor invalidation attack", "project": "mgnarf", "case": label}
    state = FrozenState(
        candidate_sha256=sha256_bytes(b"mgnarftest-inhibitor-candidate"),
        requirements_sha256=sha256_bytes(b"mgnarftest-inhibitor-requirements"),
        policy_sha256=sha256_bytes(b"mgnarftest-inhibitor-policy"),
    )
    requirements = (
        Requirement("unit", "host-tests", "1"),
        Requirement("policy", "policy-check", "1"),
    )
    contract = gate.freeze_contract(
        task,
        task_id=f"mgnarftest-inhibitor-001-{label}",
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


def execute_all(session):
    for requirement_id in session.requirements():
        result = session.execute(requirement_id)
        if result.get("status") != "PASS":
            raise AssertionError(f"verifier did not PASS: {requirement_id} -> {result!r}")


def main() -> int:
    # Attack 1: all verifier evidence is PASS, then an inhibitor is set before finalize.
    effects = []
    tmp, session = make_session("pre-finalize", effects)
    try:
        execute_all(session)
        if session.verdict().get("result") != "PASS":
            print(f"FAIL: pre-finalize attack never reached PASS before inhibitor: {session.verdict()!r}")
            return 1
        session.inhibit("policy_hold")
        verdict = session.verdict()
        if verdict.get("result") != "BLOCKED" or verdict.get("reason") != "policy_hold":
            print(f"FAIL: pre-finalize inhibitor did not block verdict: {verdict!r}")
            return 1
        final = session.finalize()
        if final.get("result") != "BLOCKED" or final.get("reason") != "policy_hold":
            print(f"FAIL: pre-finalize inhibitor did not block final decision: {final!r}")
            return 1
        try:
            session.execute_effect()
        except NARFError:
            pass
        else:
            print("FAIL: pre-finalize inhibitor reached protected effect")
            return 1
        if effects:
            print(f"FAIL: pre-finalize inhibitor changed protected effects: {effects!r}")
            return 1
    finally:
        tmp.cleanup()

    # Attack 2: obtain an authenticated PASS decision first, then inhibit before effect.
    effects = []
    tmp, session = make_session("post-pass", effects)
    try:
        execute_all(session)
        final = session.finalize()
        if final.get("result") != "PASS":
            print(f"FAIL: post-PASS attack did not first finalize PASS: {final!r}")
            return 1
        session.inhibit("human_stop")
        verdict = session.verdict()
        if verdict.get("result") != "BLOCKED" or verdict.get("reason") != "human_stop":
            print(f"FAIL: post-PASS inhibitor did not invalidate verdict: {verdict!r}")
            return 1
        try:
            session.finalize()
        except NARFError:
            pass
        else:
            print("FAIL: stale PASS decision remained authenticated after inhibitor")
            return 1
        try:
            session.execute_effect()
        except NARFError:
            pass
        else:
            print("FAIL: post-PASS inhibitor reached protected effect")
            return 1
        if effects:
            print(f"FAIL: post-PASS inhibitor changed protected effects: {effects!r}")
            return 1
    finally:
        tmp.cleanup()

    # Control: without any inhibitor, the exact PASS decision authorizes one effect.
    effects = []
    tmp, session = make_session("control", effects)
    try:
        execute_all(session)
        final = session.finalize()
        if final.get("result") != "PASS":
            print(f"FAIL: uninhibited control did not finalize PASS: {final!r}")
            return 1
        if session.execute_effect() != "control" or effects != ["control"]:
            print(f"FAIL: uninhibited control effect mismatch: {effects!r}")
            return 1
    finally:
        tmp.cleanup()

    print("PASS: pre-finalize and post-PASS inhibitors blocked protected effects; uninhibited control reached exactly one effect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
