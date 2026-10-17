#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

try:
    from .ai_multi_subject_config import MultiSubjectConfigError, load_config
    from .ai_runner_protocol import seal, sha256, verify
    from .compare_ai_dual_bundles import ComparisonError, verify_comparison_receipt
    from .verify_ai_evidence import EvidenceError, load
    from .verify_ai_dual_evidence import verify_bundle
except ImportError:
    from ai_multi_subject_config import MultiSubjectConfigError, load_config
    from ai_runner_protocol import seal, sha256, verify
    from compare_ai_dual_bundles import ComparisonError, verify_comparison_receipt
    from verify_ai_evidence import EvidenceError, load
    from verify_ai_dual_evidence import verify_bundle


class MultiSubjectVerificationError(ValueError):
    pass


def verify_multi_subject(scenario_path, config_path, output_dir, *, expected_mgtest_commit=None):
    config = load_config(config_path)
    out = Path(output_dir)
    subjects = [(item["label"], str(out / "subjects" / item["label"])) for item in config["subjects"]]

    comparison = load(out / "comparison.json")
    try:
        verify_comparison_receipt(
            comparison,
            scenario_path,
            subjects,
            expected_mgtest_commit=expected_mgtest_commit,
        )
    except (ComparisonError, EvidenceError, ValueError) as exc:
        raise MultiSubjectVerificationError(f"comparison verification failed: {exc}") from exc

    subject_receipts = []
    for label, bundle in subjects:
        verified = verify_bundle(
            scenario_path,
            bundle,
            expected_mgtest_commit=expected_mgtest_commit,
        )
        subject_receipts.append({
            "label": label,
            "aggregate_receipt_sha256": verified["aggregate_receipt_sha256"],
            "aggregate_result": verified["aggregate_result"],
        })

    receipt = load(out / "orchestration.json")
    try:
        verify(receipt)
    except ValueError as exc:
        raise MultiSubjectVerificationError(str(exc)) from exc
    expected_keys = {
        "schema_version", "receipt_type", "scenario", "mgtest_commit", "config_sha256",
        "subjects", "comparison_receipt_sha256", "comparability", "receipt_sha256",
    }
    if not isinstance(receipt, dict) or set(receipt) != expected_keys:
        raise MultiSubjectVerificationError("orchestration receipt fields invalid")
    if receipt["schema_version"] != 1 or receipt["receipt_type"] != "mgtest.ai.multi-subject-orchestration":
        raise MultiSubjectVerificationError("orchestration receipt type/version invalid")

    expected = seal({
        "schema_version": 1,
        "receipt_type": "mgtest.ai.multi-subject-orchestration",
        "scenario": comparison["scenario"],
        "mgtest_commit": comparison["mgtest_commit"],
        "config_sha256": sha256(config),
        "subjects": subject_receipts,
        "comparison_receipt_sha256": comparison["receipt_sha256"],
        "comparability": comparison["comparability"]["status"],
    })
    if receipt != expected:
        raise MultiSubjectVerificationError("orchestration receipt does not match independently recomputed evidence")
    return {
        "status": "VERIFIED",
        "comparability": receipt["comparability"],
        "subjects": len(subjects),
        "mgtest_commit": receipt["mgtest_commit"],
        "orchestration_receipt_sha256": receipt["receipt_sha256"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Independently verify MGnarfTest multi-subject orchestration evidence.")
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--expected-mgtest-commit")
    args = parser.parse_args(argv)
    try:
        result = verify_multi_subject(
            args.scenario,
            args.config,
            args.output_dir,
            expected_mgtest_commit=args.expected_mgtest_commit,
        )
    except (MultiSubjectVerificationError, MultiSubjectConfigError, EvidenceError, OSError, json.JSONDecodeError) as exc:
        print(f"BLOCKED: {exc}")
        return 1
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
