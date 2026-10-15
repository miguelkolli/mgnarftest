#!/usr/bin/env python3
import tempfile
import threading
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


WORKERS = 16


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mgnarftest-racefail-") as tmp:
        store = ReceiptStore(Path(tmp) / "receipts", b"x" * 32)
        gate = NARFGate(store)
        task = {"description": "MGnarfTest concurrent effect race with crashing winner", "project": "mgnarf"}
        state = FrozenState(
            candidate_sha256=sha256_bytes(b"mgnarftest-racefail-candidate"),
            requirements_sha256=sha256_bytes(b"mgnarftest-racefail-requirements"),
            policy_sha256=sha256_bytes(b"mgnarftest-racefail-policy"),
        )
        requirement = Requirement("approval", "authority-check", "1")
        contract = gate.freeze_contract(
            task,
            task_id="mgnarftest-racefail-001",
            requirements=(requirement,),
            effect_id="publish",
            effect_version="1",
            state=state,
        )

        callback_entries = []
        callback_lock = threading.Lock()

        def crashing_effect():
            with callback_lock:
                callback_entries.append(threading.get_ident())
            raise RuntimeError("simulated protected-effect crash")

        def make_ready_session(index: int):
            session = gate.open_session(
                contract,
                task,
                verifier_bindings=(
                    VerifierBinding(
                        "authority-check",
                        "1",
                        lambda i=index: VerifierResult("PASS", f"proof:{i}".encode()),
                    ),
                ),
                effect_binding=EffectBinding("publish", "1", crashing_effect),
                state_probe=lambda: state,
            )
            result = session.execute("approval")
            if result.get("status") != "PASS":
                raise AssertionError(f"worker {index} verifier did not PASS: {result!r}")
            final = session.finalize()
            if final.get("result") != "PASS":
                raise AssertionError(f"worker {index} did not finalize PASS: {final!r}")
            return session

        try:
            sessions = [make_ready_session(index) for index in range(WORKERS)]
        except AssertionError as error:
            print(f"FAIL: {error}")
            return 1

        barrier = threading.Barrier(WORKERS)
        outcomes = []
        outcomes_lock = threading.Lock()

        def race(index: int) -> None:
            try:
                barrier.wait(timeout=5)
                value = sessions[index].execute_effect()
            except NARFError as error:
                outcome = (index, "BLOCKED", str(error))
            except RuntimeError as error:
                outcome = (index, "CALLBACK_CRASH", str(error))
            except BaseException as error:  # diagnostic fail path
                outcome = (index, "ERROR", f"{type(error).__name__}:{error}")
            else:
                outcome = (index, "SUCCESS", value)
            with outcomes_lock:
                outcomes.append(outcome)

        threads = [threading.Thread(target=race, args=(index,)) for index in range(WORKERS)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        if any(thread.is_alive() for thread in threads):
            print("FAIL: concurrent crash race left a worker thread alive")
            return 1

        crashes = [item for item in outcomes if item[1] == "CALLBACK_CRASH"]
        blocked = [item for item in outcomes if item[1] == "BLOCKED"]
        successes = [item for item in outcomes if item[1] == "SUCCESS"]
        errors = [item for item in outcomes if item[1] == "ERROR"]
        if (
            len(outcomes) != WORKERS
            or len(crashes) != 1
            or len(blocked) != WORKERS - 1
            or successes
            or errors
        ):
            print(f"FAIL: crash-race outcome mismatch: outcomes={sorted(outcomes)!r}")
            return 1
        if crashes[0][2] != "simulated protected-effect crash":
            print(f"FAIL: winning callback crash mismatch: {crashes!r}")
            return 1
        if any("already consumed" not in item[2] for item in blocked):
            print(f"FAIL: losing racers were not rejected as consumed: {blocked!r}")
            return 1
        if len(callback_entries) != 1:
            print(f"FAIL: crashing protected callback entered {len(callback_entries)} times instead of once")
            return 1

        effect_receipts = []
        for path in store.directory.glob("*.json"):
            evidence = store.load(path.stem)
            if isinstance(evidence, dict) and evidence.get("evidence_type") == "narf.effect":
                effect_receipts.append(evidence)
        if len(effect_receipts) != 1:
            print(f"FAIL: expected one durable effect receipt after crash race, found {len(effect_receipts)}")
            return 1

        winner_index = crashes[0][0]
        loser_index = blocked[0][0]
        for label, session in (("winner-retry", sessions[winner_index]), ("loser-retry", sessions[loser_index])):
            try:
                session.execute_effect()
            except NARFError:
                pass
            else:
                print(f"FAIL: {label} regained protected effect authority")
                return 1

        # A completely fresh PASS session for the same frozen contract must also
        # observe the durable consumption receipt left before the crashed callback.
        try:
            fresh = make_ready_session(WORKERS)
        except AssertionError as error:
            print(f"FAIL: fresh retry session setup failed: {error}")
            return 1
        try:
            fresh.execute_effect()
        except NARFError as error:
            if "already consumed" not in str(error):
                print(f"FAIL: fresh retry failed for unexpected reason: {error}")
                return 1
        else:
            print("FAIL: fresh PASS session re-entered protected callback after crash")
            return 1

        if len(callback_entries) != 1:
            print(f"FAIL: retry path re-entered crashing callback: {callback_entries!r}")
            return 1

    print(f"PASS: {WORKERS} concurrent PASS sessions produced one crashing callback and one durable effect receipt; all competing and later retries failed closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
