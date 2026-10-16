#!/usr/bin/env python3
import argparse
import json

try:
    from .verify_tool_behavior_evidence import ToolBehaviorEvidenceError, verify_bundle
except ImportError:
    from verify_tool_behavior_evidence import ToolBehaviorEvidenceError, verify_bundle


def main(argv=None):
    p = argparse.ArgumentParser(description="Verify repeated tool-enabled AI behavior evidence independently.")
    p.add_argument("--scenario", required=True)
    p.add_argument("--bundle", required=True)
    p.add_argument("--expected-mgtest-commit")
    args = p.parse_args(argv)
    try:
        result = verify_bundle(args.scenario, args.bundle, args.expected_mgtest_commit)
    except ToolBehaviorEvidenceError as exc:
        print(f"FAIL: {exc}")
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
