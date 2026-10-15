#!/usr/bin/env python3
from copy import deepcopy
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


def profile(name: str) -> dict:
    return {
        "model": {"provider": "example", "name": name, "version": "1"},
        "system_prompt_sha256": sha256_bytes(f"system:{name}".encode()),
        "verifier_prompt_sha256": sha256_bytes(f"verifier:{name}".encode()),
        "toolchain": {"adapter": "1"},
    }


def make_session(label: str, attack_kind: str | None, effects: list[str]):
    tmp = tempfile.TemporaryDirectory(prefix=f"mgnarftest-midprofile-{label}-")
    store = ReceiptStore(Path(tmp.name) / "receipts", b"p" * 32)
    gate = NARFGate(store)
    task = {"description": "MGnarfTest verifier-profile drift during execution", "project": "mgnarf", "case": label}
    state = FrozenState(
        candidate_sha256=sha256_bytes(b"mgnarftest-midprofile-candidate"),
        requirements_sha256=sha256_bytes(b"mgnarftest-midprofile-requirements"),
        policy_sha256=sha256_bytes(b"mgnarftest-midprofile-policy"),
    )
    requirements = (
        Requirement("tests", "check-a", "1"),
        Requirement("security", "check-b", "1"),
        Requirement("approval", "approve", "1"),
    )
    policy = {
        "actors": {
            "builder": {"principal_id": "agent:builder", "trust_domain": "build-plane"},
            "verifier:check-a": {
                "principal_id": "ci:tests",
                "trust_domain": "test-plane",
                "verifier_profile": profile("reviewer-a"),
            },
            "verifier:check-b": {
                "principal_id": "review:security",
                "trust_domain": "review-plane",
                "verifier_profile": profile("reviewer-b"),
            },
            "authority": {"principal_id": "human:approver", "trust_domain": "approval-plane"},
        },
        "separation": [
            ["builder", "verifier:check-a", "principal_id"],
            ["verifier:check-a", "verifier:check-b", "principal_id"],
            ["verifier:check-a", "verifier:check-b", "trust_domain"],
            ["verifier:check-a", "verifier:check-b", "verifier_profile"],
            ["builder", "authority", "principal_id"],
        ],
        "authority_verifier_id": "approve",
    }
    current = {"actors": deepcopy(policy["actors"])}
    binding_profiles = {
        "check-a": deepcopy(policy["actors"]["verifier:check-a"]["verifier_profile"]),
        "check-b": deepcopy(policy["actors"]["verifier:check-b"]["verifier_profile"]),
    }
    calls = []

    def producer(requirement_id: str):
        def run():
            calls.append(requirement_id)
            if requirement_id == "tests":
                if attack_kind == "identity-profile":
                    current["actors"]["verifier:check-a"]["verifier_profile"]["model"]["version"] = "2"
                elif attack_kind == "binding-profile":
                    binding_profiles["check-a"]["model"]["version"] = "2"
            return VerifierResult("PASS", f"evidence:{requirement_id}".encode())
        return run

    bindings = []
    for requirement in requirements:
        role = "authority" if requirement.verifier_id == "approve" else f"verifier:{requirement.verifier_id}"
        actor = policy["actors"][role]
        bindings.append(
            VerifierBinding(
                requirement.verifier_id,
                requirement.verifier_version,
                producer(requirement.requirement_id),
                principal_id=actor["principal_id"],
                trust_domain=actor.get("trust_domain"),
                verifier_profile=(binding_profiles.get(requirement.verifier_id)),
            )
        )

    def effect():
        effects.append(label)
        return label

    contract = gate.freeze_contract(
        task,
        task_id=f"mgnarftest-midprofile-001-{label}",
        requirements=requirements,
        effect_id="publish",
        effect_version="1",
        state=state,
        identity_policy=policy,
    )
    session = gate.open_session(
        contract,
        task,
        verifier_bindings=bindings,
        effect_binding=EffectBinding("publish", "1", effect),
        state_probe=lambda: state,
        identity_probe=lambda: deepcopy(current["actors"]),
    )
    return tmp, store, session, current, policy, binding_profiles, calls


def run_attack(kind: str) -> bool:
    effects = []
    tmp, store, session, current, policy, binding_profiles, calls = make_session(kind, kind, effects)
    try:
        result = session.execute("tests")
        if result.get("status") != "BLOCKED" or result.get("reason") != "STATE_CHANGED_DURING_VERIFICATION":
            print(f"FAIL: {kind} drift did not override producer PASS: {result!r}")
            return False
        evidence = store.load(result["evidence_id"])
        if evidence.get("status") != "BLOCKED" or evidence.get("reason") != "STATE_CHANGED_DURING_VERIFICATION":
            print(f"FAIL: {kind} drift persisted wrong evidence: {evidence!r}")
            return False

        # Restore whichever trusted profile source was mutated. The persisted BLOCKED
        # verifier evidence must remain authoritative after restoration.
        current["actors"] = deepcopy(policy["actors"])
        binding_profiles["check-a"].clear()
        binding_profiles["check-a"].update(deepcopy(policy["actors"]["verifier:check-a"]["verifier_profile"]))

        for requirement_id in ("security", "approval"):
            followup = session.execute(requirement_id)
            if followup.get("status") != "PASS":
                print(f"FAIL: {kind} follow-up verifier did not PASS after profile restore: {followup!r}")
                return False
        verdict = session.verdict()
        if verdict.get("result") != "BLOCKED" or verdict.get("reason") != "VERIFIER_BLOCKED":
            print(f"FAIL: restoring profile healed blocked {kind} evidence: {verdict!r}")
            return False
        final = session.finalize()
        if final.get("result") != "BLOCKED" or final.get("reason") != "VERIFIER_BLOCKED":
            print(f"FAIL: {kind} attack did not finalize VERIFIER_BLOCKED: {final!r}")
            return False
        try:
            session.execute_effect()
        except NARFError:
            pass
        else:
            print(f"FAIL: {kind} profile drift reached protected effect")
            return False
        if effects:
            print(f"FAIL: {kind} profile drift changed effects: {effects!r}")
            return False
        if calls != ["tests", "security", "approval"]:
            print(f"FAIL: {kind} verifier call sequence mismatch: {calls!r}")
            return False
        return True
    finally:
        tmp.cleanup()


def main() -> int:
    for kind in ("identity-profile", "binding-profile"):
        if not run_attack(kind):
            return 1

    effects = []
    tmp, store, control, _current, _policy, _binding_profiles, calls = make_session("control", None, effects)
    try:
        for requirement_id in control.requirements():
            result = control.execute(requirement_id)
            if result.get("status") != "PASS":
                print(f"FAIL: unchanged profile control verifier did not PASS: {requirement_id} -> {result!r}")
                return 1
            evidence = store.load(result["evidence_id"])
            if evidence.get("status") != "PASS" or evidence.get("reason") != "VERIFIER_PASS":
                print(f"FAIL: unchanged profile control evidence mismatch: {evidence!r}")
                return 1
        final = control.finalize()
        if final.get("result") != "PASS":
            print(f"FAIL: unchanged profile control did not finalize PASS: {final!r}")
            return 1
        if control.execute_effect() != "control" or effects != ["control"] or calls != ["tests", "security", "approval"]:
            print(f"FAIL: unchanged profile control mismatch: calls={calls!r} effects={effects!r}")
            return 1
    finally:
        tmp.cleanup()

    print("PASS: identity-probe and binding verifier-profile drift during execution overrode producer PASS and remained BLOCKED after profile restoration; unchanged control reached one effect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
