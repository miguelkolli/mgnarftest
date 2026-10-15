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


def make_session(label: str, *, inhibit_during: bool):
    tmp = tempfile.TemporaryDirectory(prefix=f"mgnarftest-midinhibitor-{label}-")
    store = ReceiptStore(Path(tmp.name) / "receipts", b"q" * 32)
    gate = NARFGate(store)
    task = {
        "description": "MGnarfTest inhibitor introduced during verifier execution",
        "project": "mgnarf",
        "case": label,
    }
    state = FrozenState(
        candidate_sha256=sha256_bytes(b"mgnarftest-midinhibitor-candidate"),
        requirements_sha256=sha256_bytes(b"mgnarftest-midinhibitor-requirements"),
        policy_sha256=sha256_bytes(b"mgnarftest-midinhibitor-policy"),
    )
    holder = {}
    producer_calls = []
    effects = []

    def producer():
        producer_calls.append(label)
        if inhibit_during:
            holder["session"].inhibit("human_stop")
        return VerifierResult("PASS", b"producer-pass-proof")

    def effect():
        effects.append(label)
        return label

    contract = gate.freeze_contract(
        task,
        task_id=f"mgnarftest-midinhibitor-001-{label}",
        requirements=(Requirement("approval", "authority-check", "1"),),
        effect_id="publish",
        effect_version="1",
        state=state,
    )
    session = gate.open_session(
        contract,
        task,
        verifier_bindings=(VerifierBinding("authority-check", "1", producer),),
        effect_binding=EffectBinding("publish", "1", effect),
        state_probe=lambda: state,
    )
    holder["session"] = session
    return tmp, store, session, producer_calls, effects


def main() -> int:
    # Attack: a trusted inhibitor is introduced from inside the verifier execution window.
    # In MGnarf v1.70 inhibitors are verdict/effect controls rather than frozen-state errors,
    # so the verifier receipt may remain PASS. The inhibitor must still dominate the session.
    tmp, store, attack, calls, effects = make_session("attack", inhibit_during=True)
    try:
        result = attack.execute("approval")
        if result.get("status") != "PASS" or result.get("reason") != "VERIFIER_PASS":
            print(f"FAIL: attack verifier did not produce the expected PASS receipt: {result!r}")
            return 1
        evidence = store.load(result["evidence_id"])
        if evidence.get("status") != "PASS" or evidence.get("reason") != "VERIFIER_PASS":
            print(f"FAIL: attack verifier receipt mismatch: {evidence!r}")
            return 1
        if calls != ["attack"]:
            print(f"FAIL: attack producer call count mismatch: {calls!r}")
            return 1

        verdict = attack.verdict()
        if verdict.get("result") != "BLOCKED" or verdict.get("reason") != "human_stop":
            print(f"FAIL: mid-verification inhibitor did not dominate PASS evidence: {verdict!r}")
            return 1
        final = attack.finalize()
        if final.get("result") != "BLOCKED" or final.get("reason") != "human_stop":
            print(f"FAIL: mid-verification inhibitor did not block final decision: {final!r}")
            return 1
        try:
            attack.execute_effect()
        except NARFError:
            pass
        else:
            print("FAIL: mid-verification inhibitor reached protected effect")
            return 1
        if effects:
            print(f"FAIL: blocked mid-verification inhibitor changed effects: {effects!r}")
            return 1
    finally:
        tmp.cleanup()

    # Control: otherwise-identical verifier without an inhibitor may authorize one effect.
    tmp, store, control, calls, effects = make_session("control", inhibit_during=False)
    try:
        result = control.execute("approval")
        if result.get("status") != "PASS" or result.get("reason") != "VERIFIER_PASS":
            print(f"FAIL: uninhibited control verifier did not PASS: {result!r}")
            return 1
        evidence = store.load(result["evidence_id"])
        if evidence.get("status") != "PASS" or evidence.get("reason") != "VERIFIER_PASS":
            print(f"FAIL: uninhibited control receipt mismatch: {evidence!r}")
            return 1
        final = control.finalize()
        if final.get("result") != "PASS":
            print(f"FAIL: uninhibited control did not finalize PASS: {final!r}")
            return 1
        if control.execute_effect() != "control" or effects != ["control"] or calls != ["control"]:
            print(f"FAIL: uninhibited control mismatch: calls={calls!r} effects={effects!r}")
            return 1
    finally:
        tmp.cleanup()

    print("PASS: inhibitor introduced during verifier execution dominated persisted PASS evidence and blocked the protected effect; uninhibited control reached one effect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
