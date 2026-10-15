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


def make_fixture(root: Path, *, label: str, crash_effect: bool):
    calls = []
    effects = []
    store = ReceiptStore(root / f"receipts-{label}", b"f" * 32)
    gate = NARFGate(store)
    task = {"description": f"MGnarfTest effect callback failure case: {label}"}
    state = FrozenState(
        candidate_sha256=sha256_bytes(f"effectfail-candidate-{label}".encode()),
        requirements_sha256=sha256_bytes(b"effectfail-requirements"),
        policy_sha256=sha256_bytes(b"effectfail-policy"),
    )
    requirements = (
        Requirement("tests", "host-tests", "1"),
        Requirement("approval", "approve", "1"),
    )

    def producer(requirement_id: str):
        def run():
            calls.append(requirement_id)
            return VerifierResult("PASS", f"proof:{requirement_id}".encode())
        return run

    bindings = (
        VerifierBinding("host-tests", "1", producer("tests")),
        VerifierBinding("approve", "1", producer("approval")),
    )

    def effect():
        effects.append(label)
        if crash_effect:
            raise RuntimeError("simulated protected-effect callback crash")
        return "published"

    contract_id = gate.freeze_contract(
        task,
        task_id=f"mgnarftest-effectfail-001-{label}",
        requirements=requirements,
        effect_id="publish",
        effect_version="1",
        state=state,
    )

    def open_session():
        return gate.open_session(
            contract_id,
            task,
            verifier_bindings=bindings,
            effect_binding=EffectBinding("publish", "1", effect),
            state_probe=lambda: state,
        )

    return open_session, calls, effects


def finalize_pass(session):
    for requirement_id in session.requirements():
        result = session.execute(requirement_id)
        if result.get("status") != "PASS":
            raise RuntimeError(f"verification did not PASS: {requirement_id} -> {result!r}")
    final = session.finalize()
    if final.get("result") != "PASS":
        raise RuntimeError(f"session did not finalize PASS: {final!r}")
    return final


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mgnarftest-effectfail-") as tmp:
        root = Path(tmp)

        # Attack: the effect callback starts, performs observable work, then crashes.
        # The effect capability must already be consumed before the callback starts.
        open_attack, attack_verifier_calls, attack_effect_calls = make_fixture(
            root,
            label="crash",
            crash_effect=True,
        )
        first = open_attack()
        try:
            finalize_pass(first)
        except RuntimeError as exc:
            print(f"FAIL: attack session could not reach authenticated PASS: {exc}")
            return 1

        try:
            first.execute_effect()
        except RuntimeError as exc:
            if "simulated protected-effect callback crash" not in str(exc):
                print(f"FAIL: unexpected first callback failure: {exc!r}")
                return 1
        else:
            print("FAIL: crashing effect callback unexpectedly returned success")
            return 1

        if attack_effect_calls != ["crash"]:
            print(f"FAIL: first crashing callback count mismatch: {attack_effect_calls!r}")
            return 1

        # Retry 1: same session must fail before callback re-entry.
        try:
            first.execute_effect()
        except NARFError:
            pass
        else:
            print("FAIL: same-session retry after callback crash was accepted")
            return 1
        if attack_effect_calls != ["crash"]:
            print(f"FAIL: same-session retry re-entered callback: {attack_effect_calls!r}")
            return 1

        # Retry 2: a fresh session for the same frozen contract may re-verify and PASS,
        # but the deterministic effect receipt must still prevent callback re-entry.
        second = open_attack()
        try:
            finalize_pass(second)
        except RuntimeError as exc:
            print(f"FAIL: fresh retry session could not independently PASS: {exc}")
            return 1
        try:
            second.execute_effect()
        except NARFError:
            pass
        else:
            print("FAIL: cross-session retry after callback crash was accepted")
            return 1
        if attack_effect_calls != ["crash"]:
            print(f"FAIL: cross-session retry re-entered callback: {attack_effect_calls!r}")
            return 1
        if attack_verifier_calls != ["tests", "approval", "tests", "approval"]:
            print(f"FAIL: retry verification path mismatch: {attack_verifier_calls!r}")
            return 1

        # Control: an ordinary successful callback executes once and cannot be replayed.
        open_control, control_verifier_calls, control_effect_calls = make_fixture(
            root,
            label="control",
            crash_effect=False,
        )
        control = open_control()
        try:
            finalize_pass(control)
        except RuntimeError as exc:
            print(f"FAIL: control session could not reach PASS: {exc}")
            return 1
        if control.execute_effect() != "published" or control_effect_calls != ["control"]:
            print(f"FAIL: successful control effect mismatch: {control_effect_calls!r}")
            return 1
        try:
            control.execute_effect()
        except NARFError:
            pass
        else:
            print("FAIL: successful control effect replay was accepted")
            return 1
        if control_effect_calls != ["control"]:
            print(f"FAIL: successful control replay re-entered callback: {control_effect_calls!r}")
            return 1
        if control_verifier_calls != ["tests", "approval"]:
            print(f"FAIL: control verifier path mismatch: {control_verifier_calls!r}")
            return 1

    print("PASS: crashing effect callback consumed authority before callback entry; same-session and cross-session retries could not execute the callback twice")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
