#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

try:
    from .ai_runner_protocol import seal, verify
    from .verify_ai_evidence import EvidenceError, load
    from .verify_ai_dual_evidence import verify_bundle
except ImportError:
    from ai_runner_protocol import seal, verify
    from verify_ai_evidence import EvidenceError, load
    from verify_ai_dual_evidence import verify_bundle


class ComparisonError(ValueError):
    pass


def _identity(binding):
    if not isinstance(binding, dict):
        raise ComparisonError("subject binding missing")
    return (binding.get("provider"), binding.get("model"), binding.get("immutable_version"))


def _rate(count, total):
    return 0 if total == 0 else count / total


def _entry(label, bundle_dir, scenario_path, expected_mgtest_commit):
    verified = verify_bundle(scenario_path, bundle_dir, expected_mgtest_commit)
    aggregate = load(Path(bundle_dir) / "aggregate.json")
    subject = aggregate.get("subject_binding")
    identity = _identity(subject)
    if not identity[0] or not identity[1]:
        raise ComparisonError(f"{label}: subject identity unavailable")
    counts = verified["counts"]
    runs = verified["runs"]
    return {
        "label": label,
        "bundle": str(Path(bundle_dir)),
        "subject_binding": subject,
        "aggregate_result": verified["aggregate_result"],
        "counts": counts,
        "rates": {
            "compliant": _rate(counts["COMPLIANT"], runs),
            "violation": _rate(counts["VIOLATION"], runs),
            "inconclusive": _rate(counts["INCONCLUSIVE"], runs),
            "error": _rate(counts["ERROR"], runs),
        },
        "limitations": verified["limitations"],
        "runs": runs,
        "aggregate_receipt_sha256": verified["aggregate_receipt_sha256"],
        "_aggregate": aggregate,
    }


def _same(value, expected, blocker, blockers):
    if value != expected:
        blockers.add(blocker)


def build_comparison(scenario_path, subjects, *, expected_mgtest_commit=None):
    if not isinstance(subjects, list) or len(subjects) < 2:
        raise ComparisonError("at least two subject bundles required")
    labels = [item[0] for item in subjects]
    if len(set(labels)) != len(labels) or any(not isinstance(x, str) or not x.strip() for x in labels):
        raise ComparisonError("subject labels must be unique non-empty strings")

    entries = []
    for label, bundle_dir in subjects:
        try:
            entries.append(_entry(label, bundle_dir, scenario_path, expected_mgtest_commit))
        except EvidenceError as exc:
            raise ComparisonError(f"{label}: evidence verification failed: {exc}") from exc

    first = entries[0]
    baseline = first["_aggregate"]
    blockers = set()
    limitations = set()

    base_scenario = baseline["scenario"]
    base_commit = baseline["harness"]["mgtest_commit"]
    base_runner = baseline["harness"]["runner_sha256"]
    base_eval_a = baseline["evaluator_a_binding"]
    base_eval_b = baseline["evaluator_b_binding"]
    base_eval_a_adapter = baseline["harness"]["evaluator_a_adapter"]
    base_eval_b_adapter = baseline["harness"]["evaluator_b_adapter"]
    base_policy = baseline["policy"]
    if base_commit is None:
        blockers.add("MGTEST_COMMIT_UNAVAILABLE")

    identities = []
    for entry in entries:
        aggregate = entry["_aggregate"]
        _same(aggregate["scenario"], base_scenario, "SCENARIO_BINDING_MISMATCH", blockers)
        _same(aggregate["harness"]["mgtest_commit"], base_commit, "MGTEST_COMMIT_MISMATCH", blockers)
        _same(aggregate["harness"]["runner_sha256"], base_runner, "DUAL_RUNNER_MISMATCH", blockers)
        _same(aggregate["evaluator_a_binding"], base_eval_a, "EVALUATOR_A_IDENTITY_MISMATCH", blockers)
        _same(aggregate["evaluator_b_binding"], base_eval_b, "EVALUATOR_B_IDENTITY_MISMATCH", blockers)
        _same(aggregate["harness"]["evaluator_a_adapter"], base_eval_a_adapter, "EVALUATOR_A_ADAPTER_MISMATCH", blockers)
        _same(aggregate["harness"]["evaluator_b_adapter"], base_eval_b_adapter, "EVALUATOR_B_ADAPTER_MISMATCH", blockers)
        _same(aggregate["policy"]["consensus_policy"], base_policy["consensus_policy"], "CONSENSUS_POLICY_MISMATCH", blockers)
        _same(aggregate["policy"]["requested_runs"], base_policy["requested_runs"], "RUN_COUNT_MISMATCH", blockers)
        _same(aggregate["policy"]["minimum_runs"], base_policy["minimum_runs"], "MINIMUM_RUNS_MISMATCH", blockers)
        _same(aggregate["policy"]["critical_violation_tolerance"], base_policy["critical_violation_tolerance"], "TOLERANCE_MISMATCH", blockers)

        identity = _identity(entry["subject_binding"])
        identities.append(identity)
        if identity[2] is None:
            limitations.add(f"{entry['label']}:SUBJECT_MODEL_VERSION_MUTABLE_OR_UNAVAILABLE")
        for item in entry["limitations"]:
            limitations.add(f"{entry['label']}:{item}")
        if entry["aggregate_result"] == "BLOCKED":
            blockers.add(f"{entry['label']}:INPUT_BUNDLE_BLOCKED")
        elif entry["aggregate_result"] in {"UNVERIFIED", "LIMITATION_CONFIRMED"}:
            limitations.add(f"{entry['label']}:INPUT_RESULT_{entry['aggregate_result']}")

    if len(set(identities)) != len(identities):
        blockers.add("DUPLICATE_SUBJECT_IDENTITY")

    parameter_hashes = {entry["subject_binding"]["parameters_sha256"] for entry in entries}
    if len(parameter_hashes) > 1:
        limitations.add("SUBJECT_PARAMETER_VARIANCE")

    public_entries = []
    for entry in entries:
        clean = dict(entry)
        clean.pop("_aggregate")
        clean.pop("bundle")
        public_entries.append(clean)

    comparability = "BLOCKED" if blockers else ("LIMITED" if limitations else "STRONG")
    receipt = {
        "schema_version": 1,
        "receipt_type": "mgtest.ai.cross-model-comparison",
        "scenario": base_scenario,
        "mgtest_commit": base_commit,
        "dual_runner_sha256": base_runner,
        "comparison_policy": {
            "same_scenario_required": True,
            "same_mgtest_commit_required": True,
            "same_dual_runner_required": True,
            "same_evaluator_pair_required": True,
            "same_evaluator_adapters_required": True,
            "same_run_count_required": True,
            "ranking_or_overall_pass": False,
        },
        "evaluator_a_binding": base_eval_a,
        "evaluator_b_binding": base_eval_b,
        "runs_per_subject": base_policy["requested_runs"],
        "subjects": public_entries,
        "comparability": {
            "status": comparability,
            "blockers": sorted(blockers),
            "limitations": sorted(limitations),
        },
    }
    return seal(receipt)


def verify_comparison_receipt(receipt, scenario_path, subjects, *, expected_mgtest_commit=None):
    try:
        verify(receipt)
    except ValueError as exc:
        raise ComparisonError(str(exc)) from exc
    recomputed = build_comparison(
        scenario_path,
        subjects,
        expected_mgtest_commit=expected_mgtest_commit,
    )
    if receipt != recomputed:
        raise ComparisonError("comparison receipt does not match independently recomputed evidence")
    return True


def _subject_arg(value):
    if "=" not in value:
        raise argparse.ArgumentTypeError("--subject requires LABEL=PATH")
    label, path = value.split("=", 1)
    if not label.strip() or not path.strip():
        raise argparse.ArgumentTypeError("--subject requires non-empty LABEL=PATH")
    return label, path


def main(argv=None):
    parser = argparse.ArgumentParser(description="Compare independently verified MGnarfTest dual-evaluator AI evidence bundles.")
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--subject", action="append", type=_subject_arg, required=True)
    parser.add_argument("--expected-mgtest-commit")
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    try:
        receipt = build_comparison(
            args.scenario,
            args.subject,
            expected_mgtest_commit=args.expected_mgtest_commit,
        )
        verify_comparison_receipt(
            receipt,
            args.scenario,
            args.subject,
            expected_mgtest_commit=args.expected_mgtest_commit,
        )
    except (ComparisonError, EvidenceError, OSError, json.JSONDecodeError) as exc:
        print(f"BLOCKED: {exc}")
        return 1
    text = json.dumps(receipt, sort_keys=True, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0 if receipt["comparability"]["status"] != "BLOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
