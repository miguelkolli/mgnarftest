#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
from pathlib import Path

from tools.enforce_trust_root import STABLE_PROMOTION_ENABLED, TRUST_ROOT_STATUS
from tools.validate_ai_behavior import OFFLINE_TOOL_PROFILE, validate_scenario

ROOT = Path(__file__).resolve().parents[1]
HEX40 = re.compile(r"^[0-9a-f]{40}$")
CONTINUATION_CHAIN_CONTRACT = "provider-native-context-chain-v1"
PROVIDERS = {
    "openai": {
        "adapter": "adapters/openai_adapter.py",
        "secret_env": "OPENAI_API_KEY",
        "tool_subject_contract": "openai.responses.function-tools+context-chain-v1",
        "continuation_context_kind": "openai.response.output.v1",
    },
    "google-gemini": {
        "adapter": "adapters/gemini_adapter.py",
        "secret_env": "GEMINI_API_KEY",
        "tool_subject_contract": "gemini.generate-content.function-calling+context-chain-v1",
        "continuation_context_kind": "gemini.candidate.content.v1",
    },
}


class ReadinessError(ValueError):
    pass


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha256(value):
    if not isinstance(value, (bytes, bytearray)):
        value = _canonical(value)
    return hashlib.sha256(value).hexdigest()


def _file_sha(path):
    try:
        return _sha256(path.read_bytes())
    except OSError as exc:
        raise ReadinessError(f"required adapter unavailable: {path}") from exc


def _provider(name):
    if name not in PROVIDERS:
        raise ReadinessError(f"unsupported provider: {name}")
    info = dict(PROVIDERS[name])
    info["adapter_sha256"] = _file_sha(ROOT / info["adapter"])
    return info


def _model(value, where):
    if not isinstance(value, str) or not value.strip():
        raise ReadinessError(f"{where} model required")
    return value.strip()


def _alias(provider, model):
    return provider, model


def _execution_mode(scenario, provider_tool_subject_authorized, provider_model_tool_capability_verified):
    execution = scenario["execution"]
    if execution["network"] is not False:
        raise ReadinessError("provider model network must remain false")

    tools = execution["tools"]
    blockers = []
    if tools == "none":
        return "dual-evaluator-v2", blockers
    if tools != OFFLINE_TOOL_PROFILE:
        raise ReadinessError(
            f"unsupported provider subject tool configuration: {tools}"
        )
    profile = scenario.get("tool_profile")
    if not isinstance(profile, dict) or profile.get("profile") != OFFLINE_TOOL_PROFILE:
        raise ReadinessError("offline tool scenario profile binding missing")
    if not provider_tool_subject_authorized:
        blockers.append("PROVIDER_TOOL_SUBJECT_LIVE_NOT_AUTHORIZED")
    if not provider_model_tool_capability_verified:
        blockers.append("PROVIDER_MODEL_TOOL_CAPABILITY_UNVERIFIED")
    return "tool-enabled-dual-evaluator-v1", blockers


def build_plan(
    scenario_path,
    *,
    mgtest_commit,
    subject_provider,
    subject_model,
    evaluator_a_provider,
    evaluator_a_model,
    evaluator_b_provider,
    evaluator_b_model,
    runs,
    trust_root_status=None,
    stable_promotion_enabled=None,
    provider_tool_subject_authorized=False,
    provider_model_tool_capability_verified=False,
):
    if not isinstance(mgtest_commit, str) or not HEX40.fullmatch(mgtest_commit):
        raise ReadinessError("mgtest_commit must be exact lowercase 40-hex SHA")
    subject_model = _model(subject_model, "subject")
    evaluator_a_model = _model(evaluator_a_model, "evaluator A")
    evaluator_b_model = _model(evaluator_b_model, "evaluator B")
    if not isinstance(runs, int) or isinstance(runs, bool) or runs < 1:
        raise ReadinessError("runs must be positive integer")
    if not isinstance(provider_tool_subject_authorized, bool):
        raise ReadinessError("provider_tool_subject_authorized must be boolean")
    if not isinstance(provider_model_tool_capability_verified, bool):
        raise ReadinessError(
            "provider_model_tool_capability_verified must be boolean"
        )

    path = Path(scenario_path).resolve()
    scenario = validate_scenario(path)
    execution = scenario["execution"]
    if runs < execution["minimum_runs"]:
        raise ReadinessError(
            f"runs={runs} below frozen minimum_runs={execution['minimum_runs']}"
        )

    execution_mode, capability_blockers = _execution_mode(
        scenario,
        provider_tool_subject_authorized,
        provider_model_tool_capability_verified,
    )

    subject = _provider(subject_provider)
    evaluator_a = _provider(evaluator_a_provider)
    evaluator_b = _provider(evaluator_b_provider)
    blockers = list(capability_blockers)
    limitations = []

    subject_alias = _alias(subject_provider, subject_model)
    a_alias = _alias(evaluator_a_provider, evaluator_a_model)
    b_alias = _alias(evaluator_b_provider, evaluator_b_model)
    if subject_alias == a_alias:
        blockers.append("SUBJECT_EVALUATOR_A_SAME_MODEL_ALIAS")
    if subject_alias == b_alias:
        blockers.append("SUBJECT_EVALUATOR_B_SAME_MODEL_ALIAS")
    if a_alias == b_alias:
        blockers.append("EVALUATOR_PAIR_SAME_MODEL_ALIAS")

    trust_status = (
        TRUST_ROOT_STATUS if trust_root_status is None else trust_root_status
    )
    promotion_enabled = (
        STABLE_PROMOTION_ENABLED
        if stable_promotion_enabled is None
        else stable_promotion_enabled
    )
    if not promotion_enabled:
        blockers.append("REPOSITORY_TRUST_ROOT_NOT_ENFORCED")
    if trust_status not in {"PROTECTED", "ENFORCED"}:
        blockers.append(f"TRUST_ROOT_STATUS_{str(trust_status).upper()}")

    if scenario["target_policy"][
        "immutable_version_required_for_strong_comparison"
    ]:
        limitations.append(
            "IMMUTABLE_MODEL_VERSIONS_MUST_BE_SUPPLIED_BY_EXECUTION_AUTHORITY"
        )

    tool_enabled = execution["tools"] == OFFLINE_TOOL_PROFILE
    subject_plan = {
        "provider": subject_provider,
        "model": subject_model,
        "adapter": subject["adapter"],
        "adapter_sha256": subject["adapter_sha256"],
        "required_secret_env": subject["secret_env"],
        "tool_configuration": execution["tools"],
        "model_network": execution["network"],
    }
    if tool_enabled:
        subject_plan.update(
            {
                "tool_subject_contract": subject["tool_subject_contract"],
                "continuation_context_kind": subject[
                    "continuation_context_kind"
                ],
                "continuation_chain_contract": CONTINUATION_CHAIN_CONTRACT,
                "live_tool_subject_authorized": provider_tool_subject_authorized,
                "model_tool_capability_verified": provider_model_tool_capability_verified,
            }
        )

    def evaluator_plan(provider_name, model_name, provider_info):
        return {
            "provider": provider_name,
            "model": model_name,
            "adapter": provider_info["adapter"],
            "adapter_sha256": provider_info["adapter_sha256"],
            "required_secret_env": provider_info["secret_env"],
            "request_kind": (
                "mgtest.ai.tool-evaluator"
                if tool_enabled
                else "mgtest.ai.evaluator"
            ),
        }

    plan = {
        "schema_version": 3,
        "plan_type": "mgtest.ai.live-readiness",
        "execution_mode": execution_mode,
        "mgtest_commit": mgtest_commit,
        "readiness_gate_sha256": _file_sha(Path(__file__).resolve()),
        "scenario": {
            "path": str(path),
            "test_id": scenario["test_id"],
            "test_version": scenario["test_version"],
            "scenario_sha256": _sha256(scenario),
            "minimum_runs": execution["minimum_runs"],
            "requested_runs": runs,
            "tools": execution["tools"],
            "network": execution["network"],
        },
        "subject": subject_plan,
        "evaluators": {
            "a": evaluator_plan(
                evaluator_a_provider, evaluator_a_model, evaluator_a
            ),
            "b": evaluator_plan(
                evaluator_b_provider, evaluator_b_model, evaluator_b
            ),
        },
        "trust_root": {
            "status": trust_status,
            "stable_promotion_enabled": bool(promotion_enabled),
        },
        "blockers": sorted(set(blockers)),
        "limitations": sorted(set(limitations)),
    }
    plan["status"] = "READY" if not plan["blockers"] else "BLOCKED"
    return plan


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--scenario", required=True)
    p.add_argument("--mgtest-commit", required=True)
    p.add_argument(
        "--subject-provider", required=True, choices=sorted(PROVIDERS)
    )
    p.add_argument("--subject-model", required=True)
    p.add_argument(
        "--evaluator-a-provider", required=True, choices=sorted(PROVIDERS)
    )
    p.add_argument("--evaluator-a-model", required=True)
    p.add_argument(
        "--evaluator-b-provider", required=True, choices=sorted(PROVIDERS)
    )
    p.add_argument("--evaluator-b-model", required=True)
    p.add_argument("--runs", type=int, required=True)
    p.add_argument("--output")
    args = p.parse_args(argv)
    try:
        plan = build_plan(
            args.scenario,
            mgtest_commit=args.mgtest_commit,
            subject_provider=args.subject_provider,
            subject_model=args.subject_model,
            evaluator_a_provider=args.evaluator_a_provider,
            evaluator_a_model=args.evaluator_a_model,
            evaluator_b_provider=args.evaluator_b_provider,
            evaluator_b_model=args.evaluator_b_model,
            runs=args.runs,
        )
    except ReadinessError as exc:
        print(f"BLOCKED: {exc}")
        return 1
    text = json.dumps(plan, sort_keys=True, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if plan["status"] == "READY" else 1


if __name__ == "__main__":
    raise SystemExit(main())
