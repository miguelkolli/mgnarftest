#!/usr/bin/env python3
import argparse
import json
import re
from pathlib import Path

from tools.enforce_trust_root import STABLE_PROMOTION_ENABLED, TRUST_ROOT_STATUS
from tools.validate_ai_behavior import validate_scenario

HEX40 = re.compile(r"^[0-9a-f]{40}$")
PROVIDERS = {
    "openai": {"adapter": "adapters/openai_adapter.py", "secret_env": "OPENAI_API_KEY"},
    "google-gemini": {"adapter": "adapters/gemini_adapter.py", "secret_env": "GEMINI_API_KEY"},
}


class ReadinessError(ValueError):
    pass


def _provider(name):
    if name not in PROVIDERS:
        raise ReadinessError(f"unsupported provider: {name}")
    return PROVIDERS[name]


def _model(value, where):
    if not isinstance(value, str) or not value.strip():
        raise ReadinessError(f"{where} model required")
    return value.strip()


def _alias(provider, model):
    return provider, model


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
):
    if not isinstance(mgtest_commit, str) or not HEX40.fullmatch(mgtest_commit):
        raise ReadinessError("mgtest_commit must be exact lowercase 40-hex SHA")
    subject_model = _model(subject_model, "subject")
    evaluator_a_model = _model(evaluator_a_model, "evaluator A")
    evaluator_b_model = _model(evaluator_b_model, "evaluator B")
    if not isinstance(runs, int) or isinstance(runs, bool) or runs < 1:
        raise ReadinessError("runs must be positive integer")

    path = Path(scenario_path).resolve()
    scenario = validate_scenario(path)
    execution = scenario["execution"]
    if execution["tools"] != "none" or execution["network"] is not False:
        raise ReadinessError("provider adapters v1 require tools=none and model network=false")
    if runs < execution["minimum_runs"]:
        raise ReadinessError(f"runs={runs} below frozen minimum_runs={execution['minimum_runs']}")

    subject = _provider(subject_provider)
    evaluator_a = _provider(evaluator_a_provider)
    evaluator_b = _provider(evaluator_b_provider)
    blockers = []
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

    trust_status = TRUST_ROOT_STATUS if trust_root_status is None else trust_root_status
    promotion_enabled = STABLE_PROMOTION_ENABLED if stable_promotion_enabled is None else stable_promotion_enabled
    if not promotion_enabled:
        blockers.append("REPOSITORY_TRUST_ROOT_NOT_ENFORCED")
    if trust_status not in {"PROTECTED", "ENFORCED"}:
        blockers.append(f"TRUST_ROOT_STATUS_{str(trust_status).upper()}")

    if scenario["target_policy"]["immutable_version_required_for_strong_comparison"]:
        limitations.append("IMMUTABLE_MODEL_VERSIONS_MUST_BE_SUPPLIED_BY_EXECUTION_AUTHORITY")

    plan = {
        "schema_version": 2,
        "plan_type": "mgtest.ai.live-readiness",
        "execution_mode": "dual-evaluator-v2",
        "mgtest_commit": mgtest_commit,
        "scenario": {
            "path": str(path),
            "test_id": scenario["test_id"],
            "test_version": scenario["test_version"],
            "minimum_runs": execution["minimum_runs"],
            "requested_runs": runs,
        },
        "subject": {
            "provider": subject_provider,
            "model": subject_model,
            "adapter": subject["adapter"],
            "required_secret_env": subject["secret_env"],
        },
        "evaluators": {
            "a": {
                "provider": evaluator_a_provider,
                "model": evaluator_a_model,
                "adapter": evaluator_a["adapter"],
                "required_secret_env": evaluator_a["secret_env"],
            },
            "b": {
                "provider": evaluator_b_provider,
                "model": evaluator_b_model,
                "adapter": evaluator_b["adapter"],
                "required_secret_env": evaluator_b["secret_env"],
            },
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
    p.add_argument("--subject-provider", required=True, choices=sorted(PROVIDERS))
    p.add_argument("--subject-model", required=True)
    p.add_argument("--evaluator-a-provider", required=True, choices=sorted(PROVIDERS))
    p.add_argument("--evaluator-a-model", required=True)
    p.add_argument("--evaluator-b-provider", required=True, choices=sorted(PROVIDERS))
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
