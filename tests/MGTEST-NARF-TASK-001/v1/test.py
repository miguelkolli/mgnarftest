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
    producer_calls = []
    effects = []

    with tempfile.TemporaryDirectory(prefix="mgnarftest-task-") as tmp:
        store = ReceiptStore(Path(tmp) / "receipts", b"t" * 32)
        gate = NARFGate(store)
        frozen_task = {
            "description": "MGnarfTest frozen task binding",
            "project": "mgnarf",
            "operation": {"name": "publish", "scope": "release"},
        }
        state = FrozenState(
            candidate_sha256=sha256_bytes(b"mgnarftest-task-candidate"),
            requirements_sha256=sha256_bytes(b"mgnarftest-task-requirements"),
            policy_sha256=sha256_bytes(b"mgnarftest-task-policy"),
        )
        requirement = Requirement("required", "host-check", "1")

        def producer():
            producer_calls.append("called")
            return VerifierResult("PASS", b"task-proof")

        def effect():
            effects.append("published")
            return "published"

        contract_id = gate.freeze_contract(
            frozen_task,
            task_id="mgnarftest-task-001",
            requirements=(requirement,),
            effect_id="publish",
            effect_version="1",
            state=state,
        )
        binding = VerifierBinding("host-check", "1", producer)

        changed_tasks = (
            {**frozen_task, "description": "changed after freeze"},
            {
                **frozen_task,
                "operation": {"name": "publish", "scope": "different-scope"},
            },
        )

        for index, changed_task in enumerate(changed_tasks, start=1):
            session = gate.open_session(
                contract_id,
                changed_task,
                verifier_bindings=(binding,),
                effect_binding=EffectBinding("publish", "1", effect),
                state_probe=lambda: state,
            )
            verdict = session.verdict()
            if verdict.get("result") != "BLOCKED" or verdict.get("reason") != "TASK_CHANGED":
                print(f"FAIL: changed task {index} was not blocked as TASK_CHANGED: {verdict!r}")
                return 1
            try:
                session.execute("required")
            except NARFError:
                pass
            else:
                print(f"FAIL: changed task {index} entered verifier execution")
                return 1
            if session.finalize().get("result") != "BLOCKED":
                print(f"FAIL: changed task {index} did not finalize BLOCKED")
                return 1
            try:
                session.execute_effect()
            except NARFError:
                pass
            else:
                print(f"FAIL: changed task {index} reached protected effect")
                return 1

        if producer_calls or effects:
            print(f"FAIL: changed task reached producer/effect: calls={producer_calls!r} effects={effects!r}")
            return 1

        control = gate.open_session(
            contract_id,
            frozen_task,
            verifier_bindings=(binding,),
            effect_binding=EffectBinding("publish", "1", effect),
            state_probe=lambda: state,
        )
        result = control.execute("required")
        if result.get("status") != "PASS":
            print(f"FAIL: exact frozen task control verifier did not PASS: {result!r}")
            return 1
        final = control.finalize()
        if final.get("result") != "PASS":
            print(f"FAIL: exact frozen task control did not finalize PASS: {final!r}")
            return 1
        if control.execute_effect() != "published":
            print("FAIL: exact frozen task control did not execute expected effect")
            return 1
        if producer_calls != ["called"] or effects != ["published"]:
            print(f"FAIL: exact frozen task control mismatch: calls={producer_calls!r} effects={effects!r}")
            return 1

    print("PASS: changed task inputs were blocked before verifier/effect; exact frozen task reached one protected effect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
