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


def make_policy(*, shared_builder_verifier: bool) -> dict:
    verifier_a = "agent:builder" if shared_builder_verifier else "ci:tests"
    return {
        "actors": {
            "builder": {"principal_id": "agent:builder", "trust_domain": "build-plane"},
            "verifier:check-a": {"principal_id": verifier_a, "trust_domain": "test-plane"},
            "verifier:check-b": {"principal_id": "review:security", "trust_domain": "review-plane"},
            "authority": {"principal_id": "human:approver", "trust_domain": "approval-plane"},
        },
        "separation": [
            ["builder", "verifier:check-a", "principal_id"],
            ["verifier:check-a", "verifier:check-b", "principal_id"],
            ["builder", "authority", "principal_id"],
        ],
        "authority_verifier_id": "approve",
    }


def run_case(root: Path, *, shared_builder_verifier: bool, label: str):
    calls = []
    effects = []
    store = ReceiptStore(root / f"receipts-{label}", b"i" * 32)
    gate = NARFGate(store)
    task = {"description": f"MGnarfTest identity-separation case: {label}"}
    state = FrozenState(
        candidate_sha256=sha256_bytes(f"identity-candidate-{label}".encode()),
        requirements_sha256=sha256_bytes(b"identity-requirements"),
        policy_sha256=sha256_bytes(b"identity-policy"),
    )
    requirements = (
        Requirement("tests", "check-a", "1"),
        Requirement("security", "check-b", "1"),
        Requirement("approval", "approve", "1"),
    )
    policy = make_policy(shared_builder_verifier=shared_builder_verifier)
    current_identities = deepcopy(policy["actors"])

    def producer(requirement_id: str):
        def run():
            calls.append(requirement_id)
            return VerifierResult("PASS", f"evidence:{requirement_id}".encode())
        return run

    bindings = []
    for req in requirements:
        role = "authority" if req.verifier_id == "approve" else f"verifier:{req.verifier_id}"
        actor = policy["actors"][role]
        bindings.append(
            VerifierBinding(
                req.verifier_id,
                req.verifier_version,
                producer(req.requirement_id),
                principal_id=actor["principal_id"],
                trust_domain=actor["trust_domain"],
            )
        )

    def effect():
        effects.append("published")
        return "published"

    contract_id = gate.freeze_contract(
        task,
        task_id=f"mgnarftest-identity-001-{label}",
        requirements=requirements,
        effect_id="publish",
        effect_version="1",
        state=state,
        identity_policy=policy,
    )
    session = gate.open_session(
        contract_id,
        task,
        verifier_bindings=bindings,
        effect_binding=EffectBinding("publish", "1", effect),
        state_probe=lambda: state,
        identity_probe=lambda: deepcopy(current_identities),
    )
    return session, calls, effects


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mgnarftest-identity-") as tmp:
        root = Path(tmp)

        attack, attack_calls, attack_effects = run_case(
            root,
            shared_builder_verifier=True,
            label="shared-principal",
        )
        verdict = attack.verdict()
        if verdict.get("result") != "BLOCKED" or verdict.get("reason") != "IDENTITY_SEPARATION_VIOLATED":
            print(f"FAIL: shared builder/verifier identity was not blocked correctly: {verdict!r}")
            return 1
        if attack_calls:
            print(f"FAIL: identity violation entered verifier producer: {attack_calls!r}")
            return 1
        if attack.finalize().get("result") != "BLOCKED":
            print("FAIL: identity-violating session did not remain BLOCKED at finalize")
            return 1
        try:
            attack.execute_effect()
        except NARFError:
            pass
        else:
            print("FAIL: identity-violating session reached protected effect")
            return 1
        if attack_effects:
            print(f"FAIL: blocked identity attack produced effects: {attack_effects!r}")
            return 1

        control, control_calls, control_effects = run_case(
            root,
            shared_builder_verifier=False,
            label="separate-principals",
        )
        for requirement_id in ("tests", "security", "approval"):
            result = control.execute(requirement_id)
            if result.get("status") != "PASS":
                print(f"FAIL: valid separated identity route did not PASS: {requirement_id} -> {result!r}")
                return 1
        final = control.finalize()
        if final.get("result") != "PASS":
            print(f"FAIL: valid separated identity route did not finalize PASS: {final!r}")
            return 1
        if control.execute_effect() != "published" or control_effects != ["published"]:
            print(f"FAIL: valid separated identity route effect mismatch: {control_effects!r}")
            return 1
        if control_calls != ["tests", "security", "approval"]:
            print(f"FAIL: valid separated identity producer order mismatch: {control_calls!r}")
            return 1

    print("PASS: builder/verifier principal reuse was blocked before producer entry; separated identities reached exactly one guarded effect")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
