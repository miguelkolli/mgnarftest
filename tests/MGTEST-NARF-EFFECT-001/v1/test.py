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

    with tempfile.TemporaryDirectory(prefix="mgnarftest-effect-") as tmp:
        store = ReceiptStore(Path(tmp) / "receipts", b"f" * 32)
        gate = NARFGate(store)
        task = {"description": "MGnarfTest effect-binding substitution attack", "project": "mgnarf"}
        state = FrozenState(
            candidate_sha256=sha256_bytes(b"mgnarftest-effect-candidate"),
            requirements_sha256=sha256_bytes(b"mgnarftest-effect-requirements"),
            policy_sha256=sha256_bytes(b"mgnarftest-effect-policy"),
        )
        requirement = Requirement("required", "host-check", "1")

        def producer():
            producer_calls.append("host-check")
            return VerifierResult("PASS", b"effect-binding-proof")

        binding = VerifierBinding("host-check", "1", producer)
        contract_id = gate.freeze_contract(
            task,
            task_id="mgnarftest-effect-001",
            requirements=(requirement,),
            effect_id="publish",
            effect_version="1",
            state=state,
        )

        def effect(label):
            def run():
                effects.append(label)
                return label
            return run

        attacks = (
            ("wrong-id", EffectBinding("delete", "1", effect("wrong-id"))),
            ("wrong-version", EffectBinding("publish", "2", effect("wrong-version"))),
        )

        for label, wrong_effect in attacks:
            session = gate.open_session(
                contract_id,
                task,
                verifier_bindings=(binding,),
                effect_binding=wrong_effect,
                state_probe=lambda: state,
            )
            try:
                session.execute("required")
            except NARFError:
                pass
            else:
                print(f"FAIL: {label} effect binding entered verifier execution")
                return 1

            if producer_calls:
                print(f"FAIL: {label} effect-binding attack entered producer: {producer_calls!r}")
                return 1
            verdict = session.verdict()
            if verdict.get("result") != "BLOCKED" or verdict.get("reason") != "EFFECT_BINDING_CHANGED":
                print(f"FAIL: {label} effect binding was not rejected correctly: {verdict!r}")
                return 1
            if session.finalize().get("result") != "BLOCKED":
                print(f"FAIL: {label} effect binding did not finalize BLOCKED")
                return 1
            try:
                session.execute_effect()
            except NARFError:
                pass
            else:
                print(f"FAIL: {label} effect binding reached protected effect")
                return 1

        if effects:
            print(f"FAIL: substituted effect binding changed protected effects: {effects!r}")
            return 1

        control = gate.open_session(
            contract_id,
            task,
            verifier_bindings=(binding,),
            effect_binding=EffectBinding("publish", "1", effect("control")),
            state_probe=lambda: state,
        )
        result = control.execute("required")
        if result.get("status") != "PASS":
            print(f"FAIL: correct effect-binding control verifier did not PASS: {result!r}")
            return 1
        final = control.finalize()
        if final.get("result") != "PASS":
            print(f"FAIL: correct effect-binding control did not finalize PASS: {final!r}")
            return 1
        if control.execute_effect() != "control" or effects != ["control"]:
            print(f"FAIL: correct effect-binding control mismatch: {effects!r}")
            return 1
        if producer_calls != ["host-check"]:
            print(f"FAIL: verifier producer call count mismatch: {producer_calls!r}")
            return 1

    print("PASS: substituted effect id/version were blocked before verifier entry; exact frozen effect binding reached one effect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
