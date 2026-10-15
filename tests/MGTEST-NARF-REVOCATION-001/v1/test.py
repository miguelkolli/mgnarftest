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


def main() -> int:
    effects = []
    calls = []

    with tempfile.TemporaryDirectory(prefix="mgnarftest-revocation-") as tmp:
        store = ReceiptStore(Path(tmp) / "receipts", b"v" * 32)
        gate = NARFGate(store)
        task = {"description": "MGnarfTest post-PASS revocation attack", "project": "mgnarf"}
        state = FrozenState(
            candidate_sha256=sha256_bytes(b"mgnarftest-revocation-candidate"),
            requirements_sha256=sha256_bytes(b"mgnarftest-revocation-requirements"),
            policy_sha256=sha256_bytes(b"mgnarftest-revocation-policy"),
        )
        requirements = (
            Requirement("tests", "check-a", "1"),
            Requirement("approval", "approve", "1"),
        )

        def producer(name):
            def run():
                calls.append(name)
                return VerifierResult("PASS", f"artifact:{name}".encode())
            return run

        bindings = (
            VerifierBinding("check-a", "1", producer("tests")),
            VerifierBinding("approve", "1", producer("approval")),
        )
        revoked = {"value": False}

        def revocation_probe(_contract_id, _candidate_sha256):
            return revoked["value"]

        def effect(label):
            def run():
                effects.append(label)
                return label
            return run

        attack_contract = gate.freeze_contract(
            task,
            task_id="mgnarftest-revocation-001-attack",
            requirements=requirements,
            effect_id="publish",
            effect_version="1",
            state=state,
        )
        attack = gate.open_session(
            attack_contract,
            task,
            verifier_bindings=bindings,
            effect_binding=EffectBinding("publish", "1", effect("attack")),
            state_probe=lambda: state,
            revocation_probe=revocation_probe,
        )

        for requirement_id in attack.requirements():
            result = attack.execute(requirement_id)
            if result.get("status") != "PASS":
                print(f"FAIL: pre-revocation verifier did not PASS: {requirement_id} -> {result!r}")
                return 1

        final = attack.finalize()
        if final.get("result") != "PASS":
            print(f"FAIL: pre-revocation decision did not finalize PASS: {final!r}")
            return 1

        revoked["value"] = True
        try:
            attack.execute_effect()
        except NARFError:
            pass
        else:
            print("FAIL: revoked PASS executed the protected effect")
            return 1

        if effects:
            print(f"FAIL: revocation attack changed protected effects: {effects!r}")
            return 1

        revoked["value"] = False
        control_contract = gate.freeze_contract(
            task,
            task_id="mgnarftest-revocation-001-control",
            requirements=requirements,
            effect_id="publish",
            effect_version="1",
            state=state,
        )
        control = gate.open_session(
            control_contract,
            task,
            verifier_bindings=bindings,
            effect_binding=EffectBinding("publish", "1", effect("control")),
            state_probe=lambda: state,
            revocation_probe=revocation_probe,
        )

        for requirement_id in control.requirements():
            result = control.execute(requirement_id)
            if result.get("status") != "PASS":
                print(f"FAIL: control verifier did not PASS: {requirement_id} -> {result!r}")
                return 1

        final = control.finalize()
        if final.get("result") != "PASS":
            print(f"FAIL: unrevoked control did not finalize PASS: {final!r}")
            return 1
        if control.execute_effect() != "control":
            print("FAIL: unrevoked control effect returned unexpected result")
            return 1
        if effects != ["control"]:
            print(f"FAIL: protected effect count/order mismatch: {effects!r}")
            return 1

    if calls != ["tests", "approval", "tests", "approval"]:
        print(f"FAIL: verifier execution order/call count mismatch: {calls!r}")
        return 1

    print("PASS: post-PASS revocation blocked the protected effect; unrevoked control reached exactly one effect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
