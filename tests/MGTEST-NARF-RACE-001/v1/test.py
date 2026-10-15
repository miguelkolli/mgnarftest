#!/usr/bin/env python3
import tempfile
import threading
import time
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
    with tempfile.TemporaryDirectory(prefix="mgnarftest-race-") as tmp:
        store = ReceiptStore(Path(tmp) / "receipts", b"r" * 32)
        gate = NARFGate(store)
        task = {"description": "MGnarfTest concurrent protected-effect race", "project": "mgnarf"}
        state = FrozenState(
            candidate_sha256=sha256_bytes(b"mgnarftest-race-candidate"),
            requirements_sha256=sha256_bytes(b"mgnarftest-race-requirements"),
            policy_sha256=sha256_bytes(b"mgnarftest-race-policy"),
        )
        requirement = Requirement("approval", "authority-check", "1")
        contract = gate.freeze_contract(
            task,
            task_id="mgnarftest-race-001",
            requirements=(requirement,),
            effect_id="publish",
            effect_version="1",
            state=state,
        )

        callback_entries = []
        callback_lock = threading.Lock()

        def effect():
            with callback_lock:
                callback_entries.append(threading.get_ident())
            # Keep the winning callback open briefly. The consumption receipt is
            # already durable, so every concurrent loser must still fail before
            # callback entry.
            time.sleep(0.05)
            return "published"

        sessions = []
        for index in range(WORKERS):
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
                effect_binding=EffectBinding("publish", "1", effect),
                state_probe=lambda: state,
            )
            result = session.execute("approval")
            if result.get("status") != "PASS":
                print(f"FAIL: worker {index} verifier did not PASS: {result!r}")
                return 1
            final = session.finalize()
            if final.get("result") != "PASS":
                print(f"FAIL: worker {index} did not finalize PASS: {final!r}")
                return 1
            sessions.append(session)

        barrier = threading.Barrier(WORKERS)
        outcomes = []
        outcomes_lock = threading.Lock()

        def race(index: int) -> None:
            try:
                barrier.wait(timeout=5)
                value = sessions[index].execute_effect()
            except NARFError as error:
                outcome = (index, "BLOCKED", str(error))
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
            print("FAIL: concurrent effect race left a worker thread alive")
            return 1

        successes = [item for item in outcomes if item[1] == "SUCCESS"]
        blocked = [item for item in outcomes if item[1] == "BLOCKED"]
        errors = [item for item in outcomes if item[1] == "ERROR"]
        if len(outcomes) != WORKERS or len(successes) != 1 or len(blocked) != WORKERS - 1 or errors:
            print(f"FAIL: race outcome mismatch: outcomes={sorted(outcomes)!r}")
            return 1
        if successes[0][2] != "published":
            print(f"FAIL: winning callback returned unexpected value: {successes!r}")
            return 1
        if len(callback_entries) != 1:
            print(f"FAIL: protected callback entered {len(callback_entries)} times instead of once")
            return 1
        if any("already consumed" not in item[2] for item in blocked):
            print(f"FAIL: race losers were not rejected as consumed: {blocked!r}")
            return 1

        effect_receipts = []
        for path in store.directory.glob("*.json"):
            evidence = store.load(path.stem)
            if isinstance(evidence, dict) and evidence.get("evidence_type") == "narf.effect":
                effect_receipts.append(evidence)
        if len(effect_receipts) != 1:
            print(f"FAIL: expected one durable effect receipt, found {len(effect_receipts)}")
            return 1

        # A loser cannot gain authority by retrying after the race.
        loser_index = blocked[0][0]
        try:
            sessions[loser_index].execute_effect()
        except NARFError:
            pass
        else:
            print("FAIL: losing session gained effect authority on retry")
            return 1
        if len(callback_entries) != 1:
            print(f"FAIL: loser retry re-entered callback: {callback_entries!r}")
            return 1

    print(f"PASS: {WORKERS} concurrent PASS sessions produced exactly one effect receipt and one callback; {WORKERS - 1} racers failed closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
