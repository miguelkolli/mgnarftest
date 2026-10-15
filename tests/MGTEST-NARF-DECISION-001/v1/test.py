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

    with tempfile.TemporaryDirectory(prefix="mgnarftest-decision-") as tmp:
        store = ReceiptStore(Path(tmp) / "receipts", b"d" * 32)
        gate = NARFGate(store)
        task = {"description": "MGnarfTest authenticated decision tamper attack", "project": "mgnarf"}
        state = FrozenState(
            candidate_sha256=sha256_bytes(b"mgnarftest-decision-candidate"),
            requirements_sha256=sha256_bytes(b"mgnarftest-decision-requirements"),
            policy_sha256=sha256_bytes(b"mgnarftest-decision-policy"),
        )
        requirement = Requirement("required", "host-check", "1")
        binding = VerifierBinding("host-check", "1", lambda: VerifierResult("PASS", b"decision-proof"))

        def effect(label):
            def run():
                effects.append(label)
                return label
            return run

        attack_contract = gate.freeze_contract(
            task,
            task_id="mgnarftest-decision-001-attack",
            requirements=(requirement,),
            effect_id="publish",
            effect_version="1",
            state=state,
        )
        attack = gate.open_session(
            attack_contract,
            task,
            verifier_bindings=(binding,),
            effect_binding=EffectBinding("publish", "1", effect("attack")),
            state_probe=lambda: state,
        )
        if attack.execute("required").get("status") != "PASS":
            print("FAIL: attack verifier did not PASS before decision tamper")
            return 1
        decision = attack.finalize()
        if decision.get("result") != "PASS":
            print(f"FAIL: attack decision was not PASS before tamper: {decision!r}")
            return 1

        decision_path = store.directory / f"{decision['decision_id']}.json"
        envelope = json.loads(decision_path.read_text(encoding="utf-8"))
        envelope["payload"]["evidence"]["result"] = "FAIL"
        decision_path.write_text(json.dumps(envelope), encoding="utf-8")

        try:
            attack.execute_effect()
        except NARFError:
            pass
        else:
            print("FAIL: tampered PASS decision reached the protected effect")
            return 1
        if effects:
            print(f"FAIL: decision tamper changed protected effects: {effects!r}")
            return 1

        control_contract = gate.freeze_contract(
            task,
            task_id="mgnarftest-decision-001-control",
            requirements=(requirement,),
            effect_id="publish",
            effect_version="1",
            state=state,
        )
        control = gate.open_session(
            control_contract,
            task,
            verifier_bindings=(binding,),
            effect_binding=EffectBinding("publish", "1", effect("control")),
            state_probe=lambda: state,
        )
        if control.execute("required").get("status") != "PASS":
            print("FAIL: untampered control verifier did not PASS")
            return 1
        control_decision = control.finalize()
        if control_decision.get("result") != "PASS":
            print(f"FAIL: untampered control did not finalize PASS: {control_decision!r}")
            return 1
        if control.execute_effect() != "control" or effects != ["control"]:
            print(f"FAIL: untampered control effect mismatch: {effects!r}")
            return 1

    print("PASS: tampered authenticated PASS decision was rejected before effect; untampered control reached exactly one protected effect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
