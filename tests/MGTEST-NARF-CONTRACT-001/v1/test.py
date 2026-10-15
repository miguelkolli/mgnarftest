#!/usr/bin/env python3
import json
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
    tmp = tempfile.TemporaryDirectory(prefix=f"mgnarftest-contract-{label}-")
    store = ReceiptStore(Path(tmp.name) / "receipts", b"c" * 32)
    gate = NARFGate(store)
    task = {"description": "MGnarfTest contract tamper attack", "project": "mgnarf", "case": label}
    state = FrozenState(
        candidate_sha256=sha256_bytes(b"mgnarftest-contract-candidate"),
        requirements_sha256=sha256_bytes(b"mgnarftest-contract-requirements"),
        policy_sha256=sha256_bytes(b"mgnarftest-contract-policy"),
    )
    requirements = (Requirement("unit", "host-tests", "1"),)
    contract_id = gate.freeze_contract(
        task,
        task_id=f"mgnarftest-contract-001-{label}",
        requirements=requirements,
        effect_id="publish",
        effect_version="1",
        state=state,
    )
    return tmp, store, gate, task, state, contract_id


def tamper_contract(store, contract_id):
    path = store.directory / f"{contract_id}.json"
    envelope = json.loads(path.read_text(encoding="utf-8"))
    envelope["payload"]["evidence"]["task_id"] = "tampered-contract"
    path.write_text(json.dumps(envelope), encoding="utf-8")


def binding(calls):
    def produce():
        calls.append("producer")
        return VerifierResult("PASS", b"contract-proof")
    return VerifierBinding("host-tests", "1", produce)


def main() -> int:
    # Attack 1: tamper the persisted contract before session creation.
    effects = []
    producer_calls = []
    tmp, store, gate, task, state, contract_id = make_fixture("before-open")
    try:
        tamper_contract(store, contract_id)
        try:
            gate.open_session(
                contract_id,
                task,
                verifier_bindings=(binding(producer_calls),),
                effect_binding=EffectBinding("publish", "1", lambda: effects.append("before-open")),
                state_probe=lambda: state,
            )
        except NARFError:
            pass
        else:
            print("FAIL: tampered frozen contract opened a session")
            return 1
        if producer_calls or effects:
            print(f"FAIL: pre-open contract tamper reached producer/effect: producers={producer_calls!r} effects={effects!r}")
            return 1
    finally:
        tmp.cleanup()

    # Attack 2: obtain a genuine PASS first, then tamper the persisted contract before effect execution.
    effects = []
    producer_calls = []
    tmp, store, gate, task, state, contract_id = make_fixture("after-pass")
    try:
        def attack_effect():
            effects.append("after-pass")
            return "after-pass"

        session = gate.open_session(
            contract_id,
            task,
            verifier_bindings=(binding(producer_calls),),
            effect_binding=EffectBinding("publish", "1", attack_effect),
            state_probe=lambda: state,
        )
        result = session.execute("unit")
        if result.get("status") != "PASS":
            print(f"FAIL: attack verifier did not PASS before contract tamper: {result!r}")
            return 1
        final = session.finalize()
        if final.get("result") != "PASS":
            print(f"FAIL: attack did not reach genuine PASS before contract tamper: {final!r}")
            return 1

        tamper_contract(store, contract_id)
        verdict = session.verdict()
        if verdict.get("result") != "BLOCKED" or verdict.get("reason") != "CONTRACT_INVALID":
            print(f"FAIL: post-PASS contract tamper was not classified CONTRACT_INVALID: {verdict!r}")
            return 1
        try:
            session.execute_effect()
        except NARFError:
            pass
        else:
            print("FAIL: tampered persisted contract retained effect authority")
            return 1
        if effects:
            print(f"FAIL: tampered persisted contract changed protected effects: {effects!r}")
            return 1
    finally:
        tmp.cleanup()

    # Control: authenticated persisted contract remains unchanged through effect execution.
    effects = []
    producer_calls = []
    tmp, store, gate, task, state, contract_id = make_fixture("control")
    try:
        def control_effect():
            effects.append("control")
            return "control"

        session = gate.open_session(
            contract_id,
            task,
            verifier_bindings=(binding(producer_calls),),
            effect_binding=EffectBinding("publish", "1", control_effect),
            state_probe=lambda: state,
        )
        result = session.execute("unit")
        if result.get("status") != "PASS":
            print(f"FAIL: intact contract control verifier did not PASS: {result!r}")
            return 1
        final = session.finalize()
        if final.get("result") != "PASS":
            print(f"FAIL: intact contract control did not finalize PASS: {final!r}")
            return 1
        if session.execute_effect() != "control" or effects != ["control"] or producer_calls != ["producer"]:
            print(f"FAIL: intact contract control mismatch: producers={producer_calls!r} effects={effects!r}")
            return 1
    finally:
        tmp.cleanup()

    print("PASS: frozen contract tampering was rejected before session creation and after PASS; intact control reached exactly one effect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
