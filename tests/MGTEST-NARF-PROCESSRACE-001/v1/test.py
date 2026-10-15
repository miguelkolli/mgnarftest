#!/usr/bin/env python3
import multiprocessing
import queue
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


WORKERS = 8
KEY = b"p" * 32
TASK = {"description": "MGnarfTest multi-process protected-effect race", "project": "mgnarf"}
STATE = FrozenState(
    candidate_sha256=sha256_bytes(b"mgnarftest-processrace-candidate"),
    requirements_sha256=sha256_bytes(b"mgnarftest-processrace-requirements"),
    policy_sha256=sha256_bytes(b"mgnarftest-processrace-policy"),
)
REQUIREMENT = Requirement("approval", "authority-check", "1")


def worker(index, receipt_directory, contract_id, ready_queue, start_event, outcome_queue, callback_queue):
    try:
        store = ReceiptStore(receipt_directory, KEY)
        gate = NARFGate(store)

        def effect():
            callback_queue.put(index)
            return "published"

        session = gate.open_session(
            contract_id,
            TASK,
            verifier_bindings=(
                VerifierBinding(
                    "authority-check",
                    "1",
                    lambda: VerifierResult("PASS", f"process-proof:{index}".encode()),
                ),
            ),
            effect_binding=EffectBinding("publish", "1", effect),
            state_probe=lambda: STATE,
        )
        result = session.execute("approval")
        if result.get("status") != "PASS":
            outcome_queue.put((index, "SETUP_FAIL", repr(result)))
            return
        final = session.finalize()
        if final.get("result") != "PASS":
            outcome_queue.put((index, "SETUP_FAIL", repr(final)))
            return

        ready_queue.put(index)
        if not start_event.wait(timeout=10):
            outcome_queue.put((index, "ERROR", "start event timeout"))
            return

        try:
            value = session.execute_effect()
        except NARFError as error:
            outcome_queue.put((index, "BLOCKED", str(error)))
        except BaseException as error:
            outcome_queue.put((index, "ERROR", f"{type(error).__name__}:{error}"))
        else:
            outcome_queue.put((index, "SUCCESS", value))
    except BaseException as error:
        outcome_queue.put((index, "ERROR", f"{type(error).__name__}:{error}"))


def drain_exact(q, count, label):
    values = []
    for _ in range(count):
        try:
            values.append(q.get(timeout=5))
        except queue.Empty:
            raise RuntimeError(f"{label}: expected {count}, received {len(values)}") from None
    return values


def main() -> int:
    context = multiprocessing.get_context("fork")
    with tempfile.TemporaryDirectory(prefix="mgnarftest-processrace-") as tmp:
        receipt_directory = str(Path(tmp) / "receipts")
        store = ReceiptStore(receipt_directory, KEY)
        gate = NARFGate(store)
        contract = gate.freeze_contract(
            TASK,
            task_id="mgnarftest-processrace-001",
            requirements=(REQUIREMENT,),
            effect_id="publish",
            effect_version="1",
            state=STATE,
        )

        ready_queue = context.Queue()
        outcome_queue = context.Queue()
        callback_queue = context.Queue()
        start_event = context.Event()
        processes = [
            context.Process(
                target=worker,
                args=(
                    index,
                    receipt_directory,
                    contract,
                    ready_queue,
                    start_event,
                    outcome_queue,
                    callback_queue,
                ),
            )
            for index in range(WORKERS)
        ]
        for process in processes:
            process.start()

        try:
            ready = drain_exact(ready_queue, WORKERS, "ready workers")
        except RuntimeError as error:
            for process in processes:
                if process.is_alive():
                    process.terminate()
            for process in processes:
                process.join(timeout=2)
            print(f"FAIL: {error}")
            return 1
        if sorted(ready) != list(range(WORKERS)):
            print(f"FAIL: unexpected ready worker set: {ready!r}")
            return 1

        start_event.set()
        for process in processes:
            process.join(timeout=10)
        if any(process.is_alive() for process in processes):
            for process in processes:
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=2)
            print("FAIL: multi-process race left a worker alive")
            return 1
        if any(process.exitcode != 0 for process in processes):
            print(f"FAIL: worker exit codes were not all zero: {[p.exitcode for p in processes]!r}")
            return 1

        try:
            outcomes = drain_exact(outcome_queue, WORKERS, "worker outcomes")
        except RuntimeError as error:
            print(f"FAIL: {error}")
            return 1
        successes = [item for item in outcomes if item[1] == "SUCCESS"]
        blocked = [item for item in outcomes if item[1] == "BLOCKED"]
        errors = [item for item in outcomes if item[1] not in {"SUCCESS", "BLOCKED"}]
        if len(successes) != 1 or len(blocked) != WORKERS - 1 or errors:
            print(f"FAIL: process race outcome mismatch: {sorted(outcomes)!r}")
            return 1
        if successes[0][2] != "published":
            print(f"FAIL: process race winner returned unexpected value: {successes!r}")
            return 1
        if any("already consumed" not in item[2] for item in blocked):
            print(f"FAIL: process race losers were not rejected as consumed: {blocked!r}")
            return 1

        callbacks = []
        try:
            while True:
                callbacks.append(callback_queue.get_nowait())
        except queue.Empty:
            pass
        if len(callbacks) != 1:
            print(f"FAIL: protected callback entered {len(callbacks)} processes instead of once: {callbacks!r}")
            return 1

        effect_receipts = []
        for path in store.directory.glob("*.json"):
            evidence = store.load(path.stem)
            if isinstance(evidence, dict) and evidence.get("evidence_type") == "narf.effect":
                effect_receipts.append(evidence)
        if len(effect_receipts) != 1:
            print(f"FAIL: expected one durable cross-process effect receipt, found {len(effect_receipts)}")
            return 1

        # A fresh parent-process session must observe the same durable receipt and
        # remain unable to enter a new callback.
        parent_callbacks = []
        retry = gate.open_session(
            contract,
            TASK,
            verifier_bindings=(
                VerifierBinding("authority-check", "1", lambda: VerifierResult("PASS", b"parent-retry-proof")),
            ),
            effect_binding=EffectBinding("publish", "1", lambda: parent_callbacks.append("retry") or "retry"),
            state_probe=lambda: STATE,
        )
        result = retry.execute("approval")
        if result.get("status") != "PASS" or retry.finalize().get("result") != "PASS":
            print(f"FAIL: parent retry session could not establish authenticated PASS: {result!r}")
            return 1
        try:
            retry.execute_effect()
        except NARFError as error:
            if "already consumed" not in str(error):
                print(f"FAIL: parent retry failed for unexpected reason: {error}")
                return 1
        else:
            print("FAIL: parent retry re-entered protected effect after process race")
            return 1
        if parent_callbacks:
            print(f"FAIL: parent retry entered callback: {parent_callbacks!r}")
            return 1

    print(f"PASS: {WORKERS} independent processes sharing one receipt store produced exactly one effect receipt and callback; {WORKERS - 1} racers and a later retry failed closed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
