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


def make_fixture(label):
    tmp = tempfile.TemporaryDirectory(prefix=f"mgnarftest-verifier-{label}-")
    store = ReceiptStore(Path(tmp.name) / "receipts", b"v" * 32)
    gate = NARFGate(store)
    task = {"description": "MGnarfTest verifier binding attack", "project": "mgnarf", "case": label}
    state = FrozenState(
        candidate_sha256=sha256_bytes(b"mgnarftest-verifier-candidate"),
        requirements_sha256=sha256_bytes(b"mgnarftest-verifier-requirements"),
        policy_sha256=sha256_bytes(b"mgnarftest-verifier-policy"),
    )
    requirement = Requirement("unit", "host-tests", "1")
    contract = gate.freeze_contract(
        task,
        task_id=f"mgnarftest-verifier-001-{label}",
        requirements=(requirement,),
        effect_id="publish",
        effect_version="1",
        state=state,
    )
    return tmp, gate, task, state, contract


def blocked_effect(session, effects, label):
    final = session.finalize()
    if final.get("result") != "BLOCKED":
        print(f"FAIL: {label} did not finalize BLOCKED: {final!r}")
        return False
    try:
        session.execute_effect()
    except NARFError:
        pass
    else:
        print(f"FAIL: {label} reached the protected effect")
        return False
    if effects:
        print(f"FAIL: {label} changed protected effects: {effects!r}")
        return False
    return True


def main() -> int:
    # Attack 1: the frozen verifier binding is missing entirely.
    effects = []
    producer_calls = []
    tmp, gate, task, state, contract = make_fixture("missing")
    try:
        session = gate.open_session(
            contract,
            task,
            verifier_bindings=(),
            effect_binding=EffectBinding("publish", "1", lambda: effects.append("missing")),
            state_probe=lambda: state,
        )
        verdict = session.verdict()
        if verdict.get("result") != "BLOCKED" or verdict.get("reason") != "VERIFIER_UNAVAILABLE":
            print(f"FAIL: missing verifier was not rejected as VERIFIER_UNAVAILABLE: {verdict!r}")
            return 1
        try:
            session.execute("unit")
        except NARFError:
            pass
        else:
            print("FAIL: missing verifier allowed requirement execution")
            return 1
        if producer_calls:
            print(f"FAIL: missing verifier unexpectedly entered a producer: {producer_calls!r}")
            return 1
        if not blocked_effect(session, effects, "missing verifier"):
            return 1
    finally:
        tmp.cleanup()

    # Attack 2: verifier identity matches but its version no longer matches the frozen contract.
    effects = []
    producer_calls = []
    tmp, gate, task, state, contract = make_fixture("wrong-version")
    try:
        def wrong_version_producer():
            producer_calls.append("wrong-version")
            return VerifierResult("PASS", b"should-not-run")

        session = gate.open_session(
            contract,
            task,
            verifier_bindings=(VerifierBinding("host-tests", "2", wrong_version_producer),),
            effect_binding=EffectBinding("publish", "1", lambda: effects.append("wrong-version")),
            state_probe=lambda: state,
        )
        verdict = session.verdict()
        if verdict.get("result") != "BLOCKED" or verdict.get("reason") != "VERIFIER_VERSION_CHANGED":
            print(f"FAIL: wrong verifier version was not rejected: {verdict!r}")
            return 1
        try:
            session.execute("unit")
        except NARFError:
            pass
        else:
            print("FAIL: wrong verifier version allowed requirement execution")
            return 1
        if producer_calls:
            print(f"FAIL: wrong verifier version entered producer: {producer_calls!r}")
            return 1
        if not blocked_effect(session, effects, "wrong verifier version"):
            return 1
    finally:
        tmp.cleanup()

    # Attack 3: binding is exact, but the producer returns an invalid result type.
    effects = []
    producer_calls = []
    tmp, gate, task, state, contract = make_fixture("invalid-result")
    try:
        def invalid_producer():
            producer_calls.append("invalid-result")
            return "PASS"

        session = gate.open_session(
            contract,
            task,
            verifier_bindings=(VerifierBinding("host-tests", "1", invalid_producer),),
            effect_binding=EffectBinding("publish", "1", lambda: effects.append("invalid-result")),
            state_probe=lambda: state,
        )
        result = session.execute("unit")
        if result.get("status") != "BLOCKED" or result.get("reason") != "VERIFIER_UNAVAILABLE":
            print(f"FAIL: invalid verifier result did not fail closed: {result!r}")
            return 1
        if producer_calls != ["invalid-result"]:
            print(f"FAIL: invalid-result producer call count mismatch: {producer_calls!r}")
            return 1
        verdict = session.verdict()
        if verdict.get("result") != "BLOCKED" or verdict.get("reason") != "VERIFIER_BLOCKED":
            print(f"FAIL: invalid verifier result did not keep verdict BLOCKED: {verdict!r}")
            return 1
        if not blocked_effect(session, effects, "invalid verifier result"):
            return 1
    finally:
        tmp.cleanup()

    # Control: exact binding/version and a valid VerifierResult(PASS, bytes) may proceed.
    effects = []
    producer_calls = []
    tmp, gate, task, state, contract = make_fixture("control")
    try:
        def valid_producer():
            producer_calls.append("control")
            return VerifierResult("PASS", b"valid-proof")

        def valid_effect():
            effects.append("control")
            return "control"

        session = gate.open_session(
            contract,
            task,
            verifier_bindings=(VerifierBinding("host-tests", "1", valid_producer),),
            effect_binding=EffectBinding("publish", "1", valid_effect),
            state_probe=lambda: state,
        )
        result = session.execute("unit")
        if result.get("status") != "PASS":
            print(f"FAIL: valid verifier control did not PASS: {result!r}")
            return 1
        final = session.finalize()
        if final.get("result") != "PASS":
            print(f"FAIL: valid verifier control did not finalize PASS: {final!r}")
            return 1
        if session.execute_effect() != "control" or effects != ["control"] or producer_calls != ["control"]:
            print(f"FAIL: valid verifier control mismatch: producers={producer_calls!r} effects={effects!r}")
            return 1
    finally:
        tmp.cleanup()

    print("PASS: missing/wrong/invalid verifiers failed closed; exact verifier binding reached exactly one effect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
