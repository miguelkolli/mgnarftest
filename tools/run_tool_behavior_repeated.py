#!/usr/bin/env python3
import argparse
import json
import sys

try:
    from .ai_runner_protocol import parse_command
    from .tool_enabled_behavior_runner import ToolBehaviorRunnerError, run_tool_behavior_repeated
except ImportError:
    from ai_runner_protocol import parse_command
    from tool_enabled_behavior_runner import ToolBehaviorRunnerError, run_tool_behavior_repeated


def main(argv=None):
    p = argparse.ArgumentParser(description="Run repeated receipt-backed tool-enabled AI behavior tests with two evaluators.")
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
    args = p.parse_args(argv)
    try:
        aggregate = run_tool_behavior_repeated(
            args.scenario,
            parse_command(args.model_adapter_json, "--model-adapter-json"),
            parse_command(args.evaluator_a_adapter_json, "--evaluator-a-adapter-json"),
            parse_command(args.evaluator_b_adapter_json, "--evaluator-b-adapter-json"),
            runs=args.runs,
            output_dir=args.output_dir,
            timeout=args.adapter_timeout,
            model_env=args.model_env,
            evaluator_a_env=args.evaluator_a_env,
            evaluator_b_env=args.evaluator_b_env,
            mgtest_commit=args.mgtest_commit,
        )
    except (ValueError, ToolBehaviorRunnerError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({
        "result": aggregate["result"],
        "counts": aggregate["counts"],
        "limitations": aggregate["limitations"],
        "receipt_sha256": aggregate["receipt_sha256"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
