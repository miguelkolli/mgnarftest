#!/usr/bin/env python3
import tempfile
from pathlib import Path
from uuid import uuid4

from narf import (
    EffectBinding,
    FileConsumptionAuthority,
    FrozenState,
    NARFError,
    OperationBoundEffectExecutor,
    OperationBoundGate,
    ReceiptStore,
    Requirement,
    VerifierBinding,
    VerifierResult,
    sha256_bytes,
)


def main() -> int:
    effects = []

    with tempfile.TemporaryDirectory(prefix="mgnarftest-replay-") as tmp:
        root = Path(tmp)
        store = ReceiptStore(root / "receipts", b"r" * 32)
        gate = OperationBoundGate(store)
        authority = FileConsumptionAuthority(root / "authority")
        executor = OperationBoundEffectExecutor(authority)

        task = {"description": "MGnarfTest same-operation replay attack"}
        requirement = Requirement("required", "host-check", "1")
        state = FrozenState(
            candidate_sha256=sha256_bytes(b"mgnarftest-replay-candidate"),
            requirements_sha256=sha256_bytes(b"mgnarftest-replay-requirements"),
            policy_sha256=sha256_bytes(b"mgnarftest-replay-policy"),
        )
        operation_id = str(uuid4())

        def open_session(contract_id: str, label: str):
            def effect():
                effects.append(label)
                return label

            session = gate.open_session(
                contract_id,
                task,
                verifier_bindings=(
                    VerifierBinding(
                        "host-check",
                        "1",
                        lambda: VerifierResult("PASS", b"external-replay-proof"),
                    ),
                ),
                effect_binding=EffectBinding("publish", "1", effect),
                state_probe=lambda: state,
            )
            result = session.execute("required")
            if result.get("status") != "PASS":
                raise RuntimeError(f"verification did not PASS for {label}: {result!r}")
            final = session.finalize()
            if final.get("result") != "PASS":
                raise RuntimeError(f"session did not finalize PASS for {label}: {final!r}")
            return session

        first_contract = gate.freeze_contract(
            task,
            operation_id=operation_id,
            task_id="mgnarftest-replay-001-a",
            requirements=(requirement,),
            effect_id="publish",
            effect_version="1",
            state=state,
        )
        second_contract = gate.freeze_contract(
            task,
            operation_id=operation_id,
            task_id="mgnarftest-replay-001-b",
            requirements=(requirement,),
            effect_id="publish",
            effect_version="1",
            state=state,
        )

        if first_contract == second_contract:
            print("FAIL: fresh contracts unexpectedly share the same contract id")
            return 1

        first = open_session(first_contract, "first")
        second = open_session(second_contract, "second")

        if executor.execute(first) != "first":
            print("FAIL: first operation did not execute as expected")
            return 1

        try:
            executor.execute(second)
        except NARFError as exc:
            if "already consumed" not in str(exc):
                print(f"FAIL: replay was blocked for unexpected reason: {exc}")
                return 1
        else:
            print("FAIL: same operation_id executed twice across fresh contracts")
            return 1

        if effects != ["first"]:
            print(f"FAIL: replay changed effect count/order: {effects!r}")
            return 1
        if not authority.is_reserved(operation_id):
            print("FAIL: operation authority did not persist the consumed operation")
            return 1

    print("PASS: same operation_id was consumed exactly once across two fresh contracts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
