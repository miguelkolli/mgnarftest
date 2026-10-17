#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

try:
    from .ai_dual_runner_engine import run_scenario_dual
    from .ai_multi_subject_config import MultiSubjectConfigError, load_config
    from .ai_runner_protocol import seal, sha256, verify
    from .compare_ai_dual_bundles import build_comparison, verify_comparison_receipt
    from .verify_ai_dual_evidence import verify_bundle
except ImportError:
    from ai_dual_runner_engine import run_scenario_dual
    from ai_multi_subject_config import MultiSubjectConfigError, load_config
    from ai_runner_protocol import seal, sha256, verify
    from compare_ai_dual_bundles import build_comparison, verify_comparison_receipt
    from verify_ai_dual_evidence import verify_bundle


class MultiSubjectRunError(ValueError):
    pass


def _write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def run_multi_subject(
    scenario_path,
    config_path,
    *,
    output_dir,
    runs=None,
    timeout=120,
    mgtest_commit=None,
):
    if not isinstance(timeout, int) or isinstance(timeout, bool) or timeout < 1:
        raise MultiSubjectRunError("timeout must be positive integer")
    config = load_config(config_path)
    out = Path(output_dir)
    if out.exists() and any(out.iterdir()):
        raise MultiSubjectRunError("output directory must be empty")
    out.mkdir(parents=True, exist_ok=True)

    subjects = []
    subject_receipts = []
    for subject in config["subjects"]:
        bundle = out / "subjects" / subject["label"]
        aggregate = run_scenario_dual(
            scenario_path,
            subject["command"],
            config["evaluator_a"]["command"],
            config["evaluator_b"]["command"],
            runs=runs,
            output_dir=bundle,
            timeout=timeout,
            model_env=subject["env_names"],
            evaluator_a_env=config["evaluator_a"]["env_names"],
            evaluator_b_env=config["evaluator_b"]["env_names"],
            mgtest_commit=mgtest_commit,
        )
        verified = verify_bundle(scenario_path, bundle, aggregate["harness"]["mgtest_commit"])
        if verified["aggregate_receipt_sha256"] != aggregate["receipt_sha256"]:
            raise MultiSubjectRunError(f"{subject['label']}: aggregate verification hash mismatch")
        subjects.append((subject["label"], str(bundle)))
        subject_receipts.append({
            "label": subject["label"],
            "aggregate_receipt_sha256": verified["aggregate_receipt_sha256"],
            "aggregate_result": verified["aggregate_result"],
        })

    comparison = build_comparison(
        scenario_path,
        subjects,
        expected_mgtest_commit=mgtest_commit,
    )
    verify_comparison_receipt(
        comparison,
        scenario_path,
        subjects,
        expected_mgtest_commit=mgtest_commit,
    )
    _write(out / "comparison.json", comparison)

    receipt = seal({
        "schema_version": 1,
        "receipt_type": "mgtest.ai.multi-subject-orchestration",
        "scenario": comparison["scenario"],
        "mgtest_commit": comparison["mgtest_commit"],
        "config_sha256": sha256(config),
        "subjects": subject_receipts,
        "comparison_receipt_sha256": comparison["receipt_sha256"],
        "comparability": comparison["comparability"]["status"],
    })
    verify(receipt)
    _write(out / "orchestration.json", receipt)
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run one frozen MGnarfTest AI scenario across multiple subject adapters and compare independently verified evidence.")
    parser.add_argument("--scenario", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--runs", type=int)
    parser.add_argument("--adapter-timeout", type=int, default=120)
    parser.add_argument("--mgtest-commit")
    args = parser.parse_args(argv)
    try:
        receipt = run_multi_subject(
            args.scenario,
            args.config,
            output_dir=args.output_dir,
            runs=args.runs,
            timeout=args.adapter_timeout,
            mgtest_commit=args.mgtest_commit,
        )
    except (MultiSubjectRunError, MultiSubjectConfigError, ValueError, OSError) as exc:
        print(f"BLOCKED: {exc}")
        return 2
    print(json.dumps(receipt, sort_keys=True, indent=2))
    return 0 if receipt["comparability"] != "BLOCKED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
