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


def make_session(label, producer, effects):
    tmp = tempfile.TemporaryDirectory(prefix=f"mgnarftest-verifiercrash-{label}-")
    store = ReceiptStore(Path(tmp.name) / "receipts", b"c" * 32)
    gate = NARFGate(store)
    task = {"description": "MGnarfTest verifier crash/partial execution attack", "project": "mgnarf", "case": label}
    state = FrozenState(
        candidate_sha256=sha256_bytes(b"mgnarftest-verifiercrash-candidate"),
        requirements_sha256=sha256_bytes(b"mgnarftest-verifiercrash-requirements"),
        policy_sha256=sha256_bytes(b"mgnarftest-verifiercrash-policy"),
    )
    contract = gate.freeze_contract(
        task,
        task_id=f"mgnarftest-verifiercrash-001-{label}",
        requirements=(Requirement("unit", "host-tests", "1"),),
        effect_id="publish",
        effect_version="1",
        state=state,
    )

    def effect():
        effects.append(label)
        return label

    session = gate.open_session(
        contract,
        task,
        verifier_bindings=(VerifierBinding("host-tests", "1", producer),),
        effect_binding=EffectBinding("publish", "1", effect),
        state_probe=lambda: state,
    )
    return tmp, store, session


def require_crash_blocked(label, producer):
    effects = []
    tmp, store, session = make_session(label, producer, effects)
    try:
        result = session.execute("unit")
        if result.get("status") != "BLOCKED" or result.get("reason") != "VERIFIER_UNAVAILABLE":
            print(f"FAIL: {label} did not convert verifier crash to VERIFIER_UNAVAILABLE/BLOCKED: {result!r}")
            return False
        evidence = store.load(result["evidence_id"])
        if evidence.get("status") != "BLOCKED" or evidence.get("reason") != "VERIFIER_UNAVAILABLE":
            print(f"FAIL: {label} persisted non-blocked crash evidence: {evidence!r}")
            return False
        verdict = session.verdict()
        if verdict.get("result") != "BLOCKED" or verdict.get("reason") != "VERIFIER_BLOCKED":
            print(f"FAIL: {label} verdict was not VERIFIER_BLOCKED: {verdict!r}")
            return False
        final = session.finalize()
        if final.get("result") != "BLOCKED" or final.get("reason") != "VERIFIER_BLOCKED":
            print(f"FAIL: {label} final decision was not VERIFIER_BLOCKED: {final!r}")
            return False
        try:
            session.execute_effect()
        except NARFError:
            pass
        else:
            print(f"FAIL: {label} reached protected effect")
            return False
        if effects:
            print(f"FAIL: {label} changed protected effects: {effects!r}")
            return False
        return True
    finally:
        tmp.cleanup()


def main() -> int:
    immediate_steps = []

    def immediate_crash():
        immediate_steps.append("entered")
        raise RuntimeError("verifier crashed before result")

    if not require_crash_blocked("immediate-crash", immediate_crash):
        return 1
    if immediate_steps != ["entered"]:
        print(f"FAIL: immediate crash producer call count mismatch: {immediate_steps!r}")
        return 1

    partial_steps = []

    def partial_crash():
        partial_steps.extend(["opened-input", "computed-partial", "wrote-temporary-output"])
        raise RuntimeError("verifier crashed after partial work")

    if not require_crash_blocked("partial-crash", partial_crash):
        return 1
    if partial_steps != ["opened-input", "computed-partial", "wrote-temporary-output"]:
        print(f"FAIL: partial crash steps mismatch: {partial_steps!r}")
        return 1

    control_steps = []
    effects = []

    def valid_producer():
        control_steps.append("complete")
        return VerifierResult("PASS", b"complete-verifier-proof")

    tmp, store, session = make_session("control", valid_producer, effects)
    try:
        result = session.execute("unit")
        if result.get("status") != "PASS":
            print(f"FAIL: valid verifier control did not PASS: {result!r}")
            return 1
        evidence = store.load(result["evidence_id"])
        if evidence.get("status") != "PASS" or evidence.get("reason") != "VERIFIER_PASS":
            print(f"FAIL: valid verifier control evidence mismatch: {evidence!r}")
            return 1
        final = session.finalize()
        if final.get("result") != "PASS":
            print(f"FAIL: valid verifier control did not finalize PASS: {final!r}")
            return 1
        if session.execute_effect() != "control" or effects != ["control"] or control_steps != ["complete"]:
            print(f"FAIL: valid verifier control mismatch: steps={control_steps!r} effects={effects!r}")
            return 1
    finally:
        tmp.cleanup()

    print("PASS: immediate and partial verifier crashes persisted BLOCKED evidence and never authorized effect; completed verifier control reached one effect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
