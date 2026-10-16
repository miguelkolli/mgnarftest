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


def build_plan(
    scenario_path,
    *,
    mgtest_commit,
    subject_provider,
    subject_model,
    evaluator_provider,
    evaluator_model,
    runs,
    trust_root_status=None,
    stable_promotion_enabled=None,
):
    if not isinstance(mgtest_commit, str) or not HEX40.fullmatch(mgtest_commit):
        raise ReadinessError("mgtest_commit must be exact lowercase 40-hex SHA")
    if not isinstance(subject_model, str) or not subject_model.strip():
        raise ReadinessError("subject model required")
    if not isinstance(evaluator_model, str) or not evaluator_model.strip():
        raise ReadinessError("evaluator model required")
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
    evaluator = _provider(evaluator_provider)
    blockers = []
    limitations = []

    if (subject_provider, subject_model) == (evaluator_provider, evaluator_model):
        blockers.append("SUBJECT_EVALUATOR_SAME_MODEL_ALIAS")

    trust_status = TRUST_ROOT_STATUS if trust_root_status is None else trust_root_status
    promotion_enabled = STABLE_PROMOTION_ENABLED if stable_promotion_enabled is None else stable_promotion_enabled
    if not promotion_enabled:
        blockers.append("REPOSITORY_TRUST_ROOT_NOT_ENFORCED")
    if trust_status not in {"PROTECTED", "ENFORCED"}:
        blockers.append(f"TRUST_ROOT_STATUS_{str(trust_status).upper()}")

    if scenario["target_policy"]["immutable_version_required_for_strong_comparison"]:
        limitations.append("IMMUTABLE_MODEL_VERSIONS_MUST_BE_SUPPLIED_BY_EXECUTION_AUTHORITY")

    plan = {
        "schema_version": 1,
        "plan_type": "mgtest.ai.live-readiness",
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
        "evaluator": {
            "provider": evaluator_provider,
            "model": evaluator_model,
            "adapter": evaluator["adapter"],
            "required_secret_env": evaluator["secret_env"],
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
    p.add_argument("--evaluator-provider", required=True, choices=sorted(PROVIDERS))
    p.add_argument("--evaluator-model", required=True)
    p.add_argument("--runs", type=int, required=True)
    p.add_argument("--output")
    args = p.parse_args(argv)
    try:
        plan = build_plan(
            args.scenario,
            mgtest_commit=args.mgtest_commit,
            subject_provider=args.subject_provider,
            subject_model=args.subject_model,
            evaluator_provider=args.evaluator_provider,
            evaluator_model=args.evaluator_model,
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
