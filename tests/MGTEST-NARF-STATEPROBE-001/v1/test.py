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


def build_case(label, effects, probe):
    tmp = tempfile.TemporaryDirectory(prefix=f"mgnarftest-stateprobe-{label}-")
    store = ReceiptStore(Path(tmp.name) / "receipts", b"u" * 32)
    gate = NARFGate(store)
    task = {"description": "MGnarfTest state-probe availability attack", "project": "mgnarf", "case": label}
    frozen = FrozenState(
        candidate_sha256=sha256_bytes(b"mgnarftest-stateprobe-candidate"),
        requirements_sha256=sha256_bytes(b"mgnarftest-stateprobe-requirements"),
        policy_sha256=sha256_bytes(b"mgnarftest-stateprobe-policy"),
    )
    requirements = (
        Requirement("unit", "host-tests", "1"),
        Requirement("policy", "policy-check", "1"),
    )
    producer_calls = []

    def produce(name):
        def run():
            producer_calls.append(name)
            return VerifierResult("PASS", f"proof:{name}".encode())
        return run

    bindings = (
        VerifierBinding("host-tests", "1", produce("host-tests")),
        VerifierBinding("policy-check", "1", produce("policy-check")),
    )

    def effect():
        effects.append(label)
        return label

    contract = gate.freeze_contract(
        task,
        task_id=f"mgnarftest-stateprobe-001-{label}",
        requirements=requirements,
        effect_id="publish",
        effect_version="1",
        state=frozen,
    )
    session = gate.open_session(
        contract,
        task,
        verifier_bindings=bindings,
        effect_binding=EffectBinding("publish", "1", effect),
        state_probe=lambda: probe(frozen),
    )
    return tmp, session, producer_calls


def require_unavailable(session, effects, producer_calls, label):
    verdict = session.verdict()
    if verdict.get("result") != "BLOCKED" or verdict.get("reason") != "STATE_UNAVAILABLE":
        print(f"FAIL: {label} was not STATE_UNAVAILABLE/BLOCKED: {verdict!r}")
        return False
    try:
        session.execute("unit")
    except NARFError:
        pass
    else:
        print(f"FAIL: {label} verifier execution was accepted while state was unavailable")
        return False
    if producer_calls:
        print(f"FAIL: {label} reached verifier producer while state was unavailable: {producer_calls!r}")
        return False
    if effects:
        print(f"FAIL: {label} changed protected effects: {effects!r}")
        return False
    return True


def main() -> int:
    # Attack 1: the trusted state probe raises before verification.
    effects = []

    def raising_probe(_frozen):
        raise RuntimeError("state source unavailable")

    tmp, session, producer_calls = build_case("probe-exception", effects, raising_probe)
    try:
        if not require_unavailable(session, effects, producer_calls, "raising state probe"):
            return 1
    finally:
        tmp.cleanup()

    # Attack 2: the probe returns a non-FrozenState value.
    effects = []
    tmp, session, producer_calls = build_case("probe-invalid", effects, lambda _frozen: None)
    try:
        if not require_unavailable(session, effects, producer_calls, "invalid state probe value"):
            return 1
    finally:
        tmp.cleanup()

    # Attack 3: state was valid through authenticated PASS, then the probe disappears before effect.
    effects = []
    mode = {"available": True}

    def changing_probe(frozen):
        if mode["available"]:
            return frozen
        raise RuntimeError("state source lost after PASS")

    tmp, session, producer_calls = build_case("post-pass-unavailable", effects, changing_probe)
    try:
        for requirement_id in session.requirements():
            result = session.execute(requirement_id)
            if result.get("status") != "PASS":
                print(f"FAIL: post-PASS case verifier did not PASS: {requirement_id} -> {result!r}")
                return 1
        final = session.finalize()
        if final.get("result") != "PASS":
            print(f"FAIL: post-PASS case never finalized PASS: {final!r}")
            return 1
        mode["available"] = False
        verdict = session.verdict()
        if verdict.get("result") != "BLOCKED" or verdict.get("reason") != "STATE_UNAVAILABLE":
            print(f"FAIL: lost post-PASS state probe did not invalidate verdict: {verdict!r}")
            return 1
        try:
            session.finalize()
        except NARFError:
            pass
        else:
            print("FAIL: authenticated PASS remained valid after state probe became unavailable")
            return 1
        try:
            session.execute_effect()
        except NARFError:
            pass
        else:
            print("FAIL: unavailable post-PASS state probe reached protected effect")
            return 1
        if effects:
            print(f"FAIL: unavailable post-PASS state probe changed protected effects: {effects!r}")
            return 1
    finally:
        tmp.cleanup()

    # Control: an available exact FrozenState probe permits one effect.
    effects = []
    tmp, session, _producer_calls = build_case("control", effects, lambda frozen: frozen)
    try:
        for requirement_id in session.requirements():
            result = session.execute(requirement_id)
            if result.get("status") != "PASS":
                print(f"FAIL: control verifier did not PASS: {requirement_id} -> {result!r}")
                return 1
        final = session.finalize()
        if final.get("result") != "PASS":
            print(f"FAIL: control did not finalize PASS: {final!r}")
            return 1
        if session.execute_effect() != "control" or effects != ["control"]:
            print(f"FAIL: available state-probe control effect mismatch: {effects!r}")
            return 1
    finally:
        tmp.cleanup()

    print("PASS: unavailable or invalid state probes failed closed before verification and after PASS; available control reached one effect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
