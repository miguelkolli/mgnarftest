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


def make_session(root: Path, probe_state: dict, label: str):
    store = ReceiptStore(root / f"receipts-{label}", b"a" * 32)
    gate = NARFGate(store)
    task = {"description": "MGnarfTest authority availability boundary", "case": label}
    state = FrozenState(
        candidate_sha256=sha256_bytes(b"mgnarftest-authority-candidate"),
        requirements_sha256=sha256_bytes(b"mgnarftest-authority-requirements"),
        policy_sha256=sha256_bytes(b"mgnarftest-authority-policy"),
    )
    requirement = Requirement("required", "host-check", "1")
    producer_calls = []
    effects = []

    def producer():
        producer_calls.append("called")
        return VerifierResult("PASS", b"authority-proof")

    def effect():
        effects.append("published")
        return "published"

    def revocation_probe(_contract_id, _candidate_sha256):
        mode = probe_state["mode"]
        if mode == "false":
            return False
        if mode == "raise":
            raise RuntimeError("authority unavailable")
        if mode == "none":
            return None
        if mode == "string":
            return "false"
        raise RuntimeError(f"unknown probe mode: {mode}")

    contract_id = gate.freeze_contract(
        task,
        task_id=f"mgnarftest-authority-001-{label}",
        requirements=(requirement,),
        effect_id="publish",
        effect_version="1",
        state=state,
    )
    session = gate.open_session(
        contract_id,
        task,
        verifier_bindings=(VerifierBinding("host-check", "1", producer),),
        effect_binding=EffectBinding("publish", "1", effect),
        state_probe=lambda: state,
        revocation_probe=revocation_probe,
    )
    return session, producer_calls, effects


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mgnarftest-authority-") as tmp:
        root = Path(tmp)

        for mode in ("raise", "none", "string"):
            probe_state = {"mode": "false"}
            session, producer_calls, effects = make_session(root, probe_state, mode)

            result = session.execute("required")
            if result.get("status") != "PASS" or producer_calls != ["called"]:
                print(f"FAIL: verifier did not PASS before authority failure for {mode}: {result!r}")
                return 1
            final = session.finalize()
            if final.get("result") != "PASS":
                print(f"FAIL: decision was not PASS before authority failure for {mode}: {final!r}")
                return 1

            probe_state["mode"] = mode
            verdict = session.verdict()
            if verdict.get("result") != "BLOCKED" or verdict.get("reason") != "REVOKED":
                print(f"FAIL: unavailable authority did not fail closed for {mode}: {verdict!r}")
                return 1
            try:
                session.execute_effect()
            except NARFError:
                pass
            else:
                print(f"FAIL: unavailable authority allowed protected effect for {mode}")
                return 1
            if effects:
                print(f"FAIL: unavailable authority changed effect state for {mode}: {effects!r}")
                return 1

        control_state = {"mode": "false"}
        control, control_calls, control_effects = make_session(root, control_state, "control")
        if control.execute("required").get("status") != "PASS":
            print("FAIL: available authority control verifier did not PASS")
            return 1
        if control.finalize().get("result") != "PASS":
            print("FAIL: available authority control did not finalize PASS")
            return 1
        if control.execute_effect() != "published":
            print("FAIL: available authority control did not execute expected effect")
            return 1
        if control_calls != ["called"] or control_effects != ["published"]:
            print(f"FAIL: available authority control mismatch: calls={control_calls!r} effects={control_effects!r}")
            return 1

    print("PASS: authority probe failure or non-boolean output invalidated prior PASS; explicit available control reached one protected effect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
