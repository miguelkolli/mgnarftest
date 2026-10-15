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
    calls = []
    effects = []

    with tempfile.TemporaryDirectory(prefix="mgnarftest-order-") as tmp:
        store = ReceiptStore(Path(tmp) / "receipts", b"m" * 32)
        gate = NARFGate(store)
        task = {"description": "MGnarfTest external stage-order attack", "project": "mgnarf"}
        state = FrozenState(
            candidate_sha256=sha256_bytes(b"mgnarftest-order-candidate"),
            requirements_sha256=sha256_bytes(b"mgnarftest-order-requirements"),
            policy_sha256=sha256_bytes(b"mgnarftest-order-policy"),
        )
        requirements = (
            Requirement("tests", "check-a", "1"),
            Requirement("security", "check-b", "1"),
            Requirement("approval", "approve", "1"),
        )

        def producer(name):
            def run():
                calls.append(name)
                return VerifierResult("PASS", f"artifact:{name}".encode())
            return run

        bindings = [
            VerifierBinding("check-a", "1", producer("tests")),
            VerifierBinding("check-b", "1", producer("security")),
            VerifierBinding("approve", "1", producer("approval")),
        ]

        def effect():
            effects.append("published")
            return "published"

        contract_id = gate.freeze_contract(
            task,
            task_id="mgnarftest-order-001",
            requirements=requirements,
            effect_id="publish",
            effect_version="1",
            state=state,
            stage_order=["tests", "security", "approval"],
        )
        session = gate.open_session(
            contract_id,
            task,
            verifier_bindings=bindings,
            effect_binding=EffectBinding("publish", "1", effect),
            state_probe=lambda: state,
        )

        try:
            session.execute("security")
        except NARFError:
            pass
        else:
            print("FAIL: future stage was accepted before predecessor")
            return 1

        if calls:
            print(f"FAIL: rejected future-stage attack still entered producer: {calls!r}")
            return 1

        for requirement_id in ("tests", "security", "approval"):
            result = session.execute(requirement_id)
            if result.get("status") != "PASS":
                print(f"FAIL: valid ordered stage did not PASS: {requirement_id}")
                return 1

        final = session.finalize()
        if final.get("result") != "PASS":
            print(f"FAIL: valid ordered chain did not finalize PASS: {final!r}")
            return 1
        if session.execute_effect() != "published" or effects != ["published"]:
            print(f"FAIL: guarded effect execution mismatch: {effects!r}")
            return 1

    print("PASS: future-stage producer was blocked before entry; valid ordered retry reached exactly one guarded effect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
