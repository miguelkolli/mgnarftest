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


def main() -> int:
    effects = []

    with tempfile.TemporaryDirectory(prefix="mgnarftest-evidence-") as tmp:
        store = ReceiptStore(Path(tmp) / "receipts", b"e" * 32)
        gate = NARFGate(store)
        task = {"description": "MGnarfTest authenticated evidence tamper attack", "project": "mgnarf"}
        state = FrozenState(
            candidate_sha256=sha256_bytes(b"mgnarftest-evidence-candidate"),
            requirements_sha256=sha256_bytes(b"mgnarftest-evidence-requirements"),
            policy_sha256=sha256_bytes(b"mgnarftest-evidence-policy"),
        )
        requirements = (
            Requirement("tests", "check-a", "1"),
            Requirement("policy", "check-b", "1"),
        )
        bindings = (
            VerifierBinding("check-a", "1", lambda: VerifierResult("PASS", b"tests-proof")),
            VerifierBinding("check-b", "1", lambda: VerifierResult("PASS", b"policy-proof")),
        )

        def effect(label):
            def run():
                effects.append(label)
                return label
            return run

        attack_contract = gate.freeze_contract(
            task,
            task_id="mgnarftest-evidence-001-attack",
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
        )

        first = attack.execute("tests")
        if first.get("status") != "PASS":
            print(f"FAIL: first verifier did not PASS before tamper: {first!r}")
            return 1

        receipt_path = store.directory / f"{first['evidence_id']}.json"
        envelope = json.loads(receipt_path.read_text(encoding="utf-8"))
        envelope["payload"]["evidence"]["task_id"] = "tampered-task-id"
        receipt_path.write_text(json.dumps(envelope), encoding="utf-8")

        second = attack.execute("policy")
        if second.get("status") != "PASS":
            print(f"FAIL: second verifier execution itself did not PASS: {second!r}")
            return 1

        verdict = attack.verdict()
        if verdict.get("result") != "BLOCKED" or verdict.get("reason") != "INVALID_EVIDENCE":
            print(f"FAIL: tampered authenticated evidence was not rejected correctly: {verdict!r}")
            return 1
        if attack.finalize().get("result") != "BLOCKED":
            print("FAIL: tampered evidence did not keep final decision BLOCKED")
            return 1
        try:
            attack.execute_effect()
        except NARFError:
            pass
        else:
            print("FAIL: tampered evidence reached the protected effect")
            return 1
        if effects:
            print(f"FAIL: tamper attack changed protected effects: {effects!r}")
            return 1

        control_contract = gate.freeze_contract(
            task,
            task_id="mgnarftest-evidence-001-control",
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
        )
        for requirement_id in control.requirements():
            result = control.execute(requirement_id)
            if result.get("status") != "PASS":
                print(f"FAIL: untampered control verifier did not PASS: {requirement_id} -> {result!r}")
                return 1
        final = control.finalize()
        if final.get("result") != "PASS":
            print(f"FAIL: untampered control did not finalize PASS: {final!r}")
            return 1
        if control.execute_effect() != "control" or effects != ["control"]:
            print(f"FAIL: untampered control effect mismatch: {effects!r}")
            return 1

    print("PASS: tampered verifier evidence was rejected and blocked the effect; untampered control reached exactly one effect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
