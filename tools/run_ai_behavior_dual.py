#!/usr/bin/env python3
import argparse
import json
import sys

try:
    from .ai_dual_runner_engine import run_scenario_dual
    from .ai_runner_protocol import parse_command
    from .validate_ai_behavior import ValidationError
except ImportError:
    from ai_dual_runner_engine import run_scenario_dual
    from ai_runner_protocol import parse_command
    from validate_ai_behavior import ValidationError


def main(argv=None):
    p = argparse.ArgumentParser(description="Run a versioned MGnarfTest AI behavior scenario with two independent evaluators.")
    p.add_argument("--scenario", required=True)
    p.add_argument("--model-adapter-json", required=True)
    p.add_argument("--evaluator-a-adapter-json", required=True)
    p.add_argument("--evaluator-b-adapter-json", required=True)
    p.add_argument("--runs", type=int)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--adapter-timeout", type=int, default=120)
    p.add_argument("--model-env", action="append", default=[])
    p.add_argument("--evaluator-a-env", action="append", default=[])
    p.add_argument("--evaluator-b-env", action="append", default=[])
    p.add_argument("--mgtest-commit")
    a = p.parse_args(argv)
    if a.adapter_timeout < 1:
        p.error("--adapter-timeout must be positive")
    try:
        r = run_scenario_dual(
            a.scenario,
            parse_command(a.model_adapter_json, "--model-adapter-json"),
            parse_command(a.evaluator_a_adapter_json, "--evaluator-a-adapter-json"),
            parse_command(a.evaluator_b_adapter_json, "--evaluator-b-adapter-json"),
            runs=a.runs,
            output_dir=a.output_dir,
            timeout=a.adapter_timeout,
            model_env=a.model_env,
            evaluator_a_env=a.evaluator_a_env,
            evaluator_b_env=a.evaluator_b_env,
            mgtest_commit=a.mgtest_commit,
        )
    except (ValueError, ValidationError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "test_id": r["scenario"]["test_id"],
        "test_version": r["scenario"]["test_version"],
        "runs": r["policy"]["requested_runs"],
        "counts": r["counts"],
        "result": r["result"],
        "aggregate_receipt_sha256": r["receipt_sha256"],
        "consensus_policy": r["policy"]["consensus_policy"],
    }, sort_keys=True))
    return 0 if r["result"] in {"PASS", "LIMITATION_CONFIRMED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
