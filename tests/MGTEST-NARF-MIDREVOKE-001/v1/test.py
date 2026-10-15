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


def make_session(label, producer, revoked, effects):
    tmp = tempfile.TemporaryDirectory(prefix=f"mgnarftest-midrevoke-{label}-")
    store = ReceiptStore(Path(tmp.name) / "receipts", b"r" * 32)
    gate = NARFGate(store)
    task = {"description": "MGnarfTest revocation during verifier execution", "project": "mgnarf", "case": label}
    state = FrozenState(
        candidate_sha256=sha256_bytes(b"mgnarftest-midrevoke-candidate"),
        requirements_sha256=sha256_bytes(b"mgnarftest-midrevoke-requirements"),
        policy_sha256=sha256_bytes(b"mgnarftest-midrevoke-policy"),
    )
    contract = gate.freeze_contract(
        task,
        task_id=f"mgnarftest-midrevoke-001-{label}",
        requirements=(Requirement("approval", "authority-check", "1"),),
        effect_id="publish",
        effect_version="1",
        state=state,
    )

    def revocation_probe(_contract_id, _candidate_sha256):
        return revoked["value"]

    def effect():
        effects.append(label)
        return label

    session = gate.open_session(
        contract,
        task,
        verifier_bindings=(VerifierBinding("authority-check", "1", producer),),
        effect_binding=EffectBinding("publish", "1", effect),
        state_probe=lambda: state,
        revocation_probe=revocation_probe,
    )
    return tmp, store, session


def main() -> int:
    # Attack: revocation arrives while the verifier producer is running.
    revoked = {"value": False}
    producer_calls = []
    effects = []

    def revoke_then_pass():
        producer_calls.append("attack")
        revoked["value"] = True
        return VerifierResult("PASS", b"producer-thought-pass")

    tmp, store, attack = make_session("attack", revoke_then_pass, revoked, effects)
    try:
        result = attack.execute("approval")
        if result.get("status") != "BLOCKED" or result.get("reason") != "STATE_CHANGED_DURING_VERIFICATION":
            print(f"FAIL: mid-verification revocation did not override producer PASS: {result!r}")
            return 1
        evidence = store.load(result["evidence_id"])
        if evidence.get("status") != "BLOCKED" or evidence.get("reason") != "STATE_CHANGED_DURING_VERIFICATION":
            print(f"FAIL: mid-verification revocation persisted wrong evidence: {evidence!r}")
            return 1

        # Restore the probe to unrevoked after the verifier returns. The already-persisted
        # BLOCKED evidence must remain authoritative; it must not heal into PASS.
        revoked["value"] = False
        verdict = attack.verdict()
        if verdict.get("result") != "BLOCKED" or verdict.get("reason") != "VERIFIER_BLOCKED":
            print(f"FAIL: clearing revocation healed blocked evidence: {verdict!r}")
            return 1
        final = attack.finalize()
        if final.get("result") != "BLOCKED" or final.get("reason") != "VERIFIER_BLOCKED":
            print(f"FAIL: attack did not finalize VERIFIER_BLOCKED: {final!r}")
            return 1
        try:
            attack.execute_effect()
        except NARFError:
            pass
        else:
            print("FAIL: mid-verification revocation reached protected effect")
            return 1
        if effects:
            print(f"FAIL: blocked mid-revocation attack changed effects: {effects!r}")
            return 1
    finally:
        tmp.cleanup()

    if producer_calls != ["attack"]:
        print(f"FAIL: attack producer call count mismatch: {producer_calls!r}")
        return 1

    # Control: no revocation during or after verification.
    control_revoked = {"value": False}
    control_calls = []
    control_effects = []

    def control_producer():
        control_calls.append("control")
        return VerifierResult("PASS", b"stable-authority-proof")

    tmp, store, control = make_session("control", control_producer, control_revoked, control_effects)
    try:
        result = control.execute("approval")
        if result.get("status") != "PASS":
            print(f"FAIL: unrevoked control did not PASS: {result!r}")
            return 1
        evidence = store.load(result["evidence_id"])
        if evidence.get("status") != "PASS" or evidence.get("reason") != "VERIFIER_PASS":
            print(f"FAIL: unrevoked control evidence mismatch: {evidence!r}")
            return 1
        final = control.finalize()
        if final.get("result") != "PASS":
            print(f"FAIL: unrevoked control did not finalize PASS: {final!r}")
            return 1
        if control.execute_effect() != "control" or control_effects != ["control"] or control_calls != ["control"]:
            print(f"FAIL: unrevoked control mismatch: calls={control_calls!r} effects={control_effects!r}")
            return 1
    finally:
        tmp.cleanup()

    print("PASS: revocation arriving during verifier execution overrode producer PASS and remained BLOCKED after revocation cleared; unrevoked control reached one effect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
