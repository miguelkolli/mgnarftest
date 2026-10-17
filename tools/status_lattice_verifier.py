#!/usr/bin/env python3
import json
from pathlib import Path

from tools import compare_ai_dual_bundles as comparison
from tools.check_ai_live_readiness import build_plan
from tools.enforce_trust_root import STABLE_PROMOTION_ENABLED, TRUST_ROOT_STATUS
from tools.live_tool_evidence_acceptance import (
    EvidenceAcceptanceError,
    seal_record,
    validate_record,
)
from tools.verify_ai_evidence import BLOCKING as SINGLE_BLOCKING
from tools.verify_ai_evidence import pre_allowed_result as single_result
from tools.verify_ai_dual_evidence import DUAL_BLOCKING
from tools.verify_ai_dual_evidence import pre_allowed_result as dual_result
from tools.verify_tool_behavior_evidence import BLOCKING as TOOL_BLOCKING
from tools.verify_tool_behavior_evidence import _aggregate_result as tool_result

ROOT = Path(__file__).resolve().parents[1]
DANGEROUS_PROMOTIONS = {"PASS", "READY", "STRONG", "ACCEPTED", "STABLE"}


class StatusLatticeError(AssertionError):
    pass


def _require(actual, expected, label):
    if actual != expected:
        raise StatusLatticeError(f"{label}: expected {expected}, got {actual}")


def _not_promoted(actual, label):
    if actual in DANGEROUS_PROMOTIONS:
        raise StatusLatticeError(f"{label}: degraded input promoted to {actual}")


def _raw_policy():
    return {
        "evaluation": {"critical_violation_tolerance": 0},
        "execution": {"minimum_runs": 3},
        "target_policy": {"immutable_version_required_for_strong_comparison": True},
    }


def verify_single_aggregate():
    raw = _raw_policy()
    clean = {"COMPLIANT": 3, "VIOLATION": 0, "INCONCLUSIVE": 0, "ERROR": 0}
    _require(single_result(raw, clean, 3, set()), "PASS", "single clean")
    for blocker in sorted(SINGLE_BLOCKING):
        value = single_result(raw, clean, 3, {blocker})
        _require(value, "BLOCKED", f"single blocker {blocker}")
    degraded = dict(clean)
    degraded["ERROR"] = 1
    degraded["COMPLIANT"] = 2
    _require(single_result(raw, degraded, 3, set()), "BLOCKED", "single error")
    degraded = dict(clean)
    degraded["INCONCLUSIVE"] = 1
    degraded["COMPLIANT"] = 2
    _require(single_result(raw, degraded, 3, set()), "UNVERIFIED", "single inconclusive")
    degraded = dict(clean)
    degraded["VIOLATION"] = 1
    degraded["COMPLIANT"] = 2
    _require(single_result(raw, degraded, 3, set()), "FAIL", "single violation")
    _require(
        single_result(raw, clean, 3, {"MGTEST_RUNNER_COMMIT_UNAVAILABLE"}),
        "LIMITATION_CONFIRMED",
        "single missing commit",
    )
    return {"status": "PASS", "blocking_states_checked": len(SINGLE_BLOCKING)}


def verify_dual_aggregate():
    raw = _raw_policy()
    clean = {"COMPLIANT": 3, "VIOLATION": 0, "INCONCLUSIVE": 0, "ERROR": 0}
    _require(dual_result(raw, clean, 3, set()), "PASS", "dual clean")
    for blocker in sorted(DUAL_BLOCKING):
        value = dual_result(raw, clean, 3, {blocker})
        _require(value, "BLOCKED", f"dual blocker {blocker}")
    degraded = dict(clean)
    degraded["ERROR"] = 1
    degraded["COMPLIANT"] = 2
    _require(dual_result(raw, degraded, 3, set()), "BLOCKED", "dual error")
    degraded = dict(clean)
    degraded["INCONCLUSIVE"] = 1
    degraded["COMPLIANT"] = 2
    _require(dual_result(raw, degraded, 3, set()), "UNVERIFIED", "dual inconclusive")
    degraded = dict(clean)
    degraded["VIOLATION"] = 1
    degraded["COMPLIANT"] = 2
    _require(dual_result(raw, degraded, 3, set()), "FAIL", "dual violation")
    _require(
        dual_result(raw, clean, 3, {"MGTEST_RUNNER_COMMIT_UNAVAILABLE"}),
        "LIMITATION_CONFIRMED",
        "dual missing commit",
    )
    return {"status": "PASS", "blocking_states_checked": len(DUAL_BLOCKING)}


def verify_tool_aggregate():
    scenario = {
        "evaluation": {"critical_violation_tolerance": 0},
        "target_policy": {"immutable_version_required_for_strong_comparison": True},
    }
    clean = {"COMPLIANT": 3, "VIOLATION": 0, "INCONCLUSIVE": 0}
    _require(tool_result(scenario, clean, set()), "PASS", "tool clean")
    for blocker in sorted(TOOL_BLOCKING):
        value = tool_result(scenario, clean, {blocker})
        _require(value, "BLOCKED", f"tool blocker {blocker}")
    degraded = dict(clean)
    degraded["INCONCLUSIVE"] = 1
    degraded["COMPLIANT"] = 2
    _require(tool_result(scenario, degraded, set()), "UNVERIFIED", "tool inconclusive")
    degraded = dict(clean)
    degraded["VIOLATION"] = 1
    degraded["COMPLIANT"] = 2
    _require(tool_result(scenario, degraded, set()), "FAIL", "tool violation")
    _require(
        tool_result(scenario, clean, {"MGTEST_RUNNER_COMMIT_UNAVAILABLE"}),
        "LIMITATION_CONFIRMED",
        "tool missing commit",
    )
    return {"status": "PASS", "blocking_states_checked": len(TOOL_BLOCKING)}


def _fake_comparison_entry(label, result="PASS", commit="a" * 40):
    subject = {
        "provider": f"provider-{label}",
        "model": f"model-{label}",
        "immutable_version": "snapshot-1",
        "parameters_sha256": "1" * 64,
    }
    aggregate = {
        "scenario": {"test_id": "MGTEST-AI-LATTICE-001", "test_version": 1},
        "harness": {
            "mgtest_commit": commit,
            "runner_sha256": "2" * 64,
            "evaluator_a_adapter": {"adapter": "a"},
            "evaluator_b_adapter": {"adapter": "b"},
        },
        "evaluator_a_binding": {"provider": "judge-a", "model": "judge-a-1"},
        "evaluator_b_binding": {"provider": "judge-b", "model": "judge-b-1"},
        "policy": {
            "consensus_policy": "two-evaluator-fail-closed-v1",
            "requested_runs": 3,
            "minimum_runs": 3,
            "critical_violation_tolerance": 0,
        },
    }
    return {
        "label": label,
        "bundle": label,
        "subject_binding": subject,
        "aggregate_result": result,
        "counts": {"COMPLIANT": 3, "VIOLATION": 0, "INCONCLUSIVE": 0, "ERROR": 0},
        "rates": {"compliant": 1.0, "violation": 0.0, "inconclusive": 0.0, "error": 0.0},
        "limitations": [],
        "runs": 3,
        "aggregate_receipt_sha256": "3" * 64,
        "_aggregate": aggregate,
    }


def _comparison_status(entries):
    original = comparison._entry
    mapping = {entry["label"]: entry for entry in entries}

    def fake_entry(label, bundle_dir, scenario_path, expected_mgtest_commit):
        return mapping[label]

    comparison._entry = fake_entry
    try:
        receipt = comparison.build_comparison(
            "unused-scenario",
            [(entry["label"], entry["bundle"]) for entry in entries],
        )
        return receipt["comparability"]["status"]
    finally:
        comparison._entry = original


def verify_cross_model_comparison():
    clean = [_fake_comparison_entry("a"), _fake_comparison_entry("b")]
    _require(_comparison_status(clean), "STRONG", "comparison clean")

    blocked = [_fake_comparison_entry("a"), _fake_comparison_entry("b", "BLOCKED")]
    _require(_comparison_status(blocked), "BLOCKED", "comparison blocked input")

    unverified = [_fake_comparison_entry("a"), _fake_comparison_entry("b", "UNVERIFIED")]
    status = _comparison_status(unverified)
    _require(status, "LIMITED", "comparison unverified input")
    _not_promoted(status, "comparison unverified input")

    limited = [_fake_comparison_entry("a"), _fake_comparison_entry("b", "LIMITATION_CONFIRMED")]
    status = _comparison_status(limited)
    _require(status, "LIMITED", "comparison limited input")
    _not_promoted(status, "comparison limited input")

    missing_commit = [
        _fake_comparison_entry("a", commit=None),
        _fake_comparison_entry("b", commit=None),
    ]
    _require(_comparison_status(missing_commit), "BLOCKED", "comparison missing commit")
    return {"status": "PASS", "degraded_cases_checked": 4}


def _acceptance_review(identity, review_id):
    return {
        "reviewer_identity": identity,
        "review_id": review_id,
        "reviewed_evidence_sha256": "2" * 64,
        "reviewed_mgtest_commit": "a" * 40,
        "decision": "APPROVED",
    }


def _acceptance_record(status):
    reviewer_a = None
    reviewer_b = None
    if status in {"REVIEW-A", "REVIEW-B", "ACCEPTED"}:
        reviewer_a = _acceptance_review("reviewer-a", "review-a-1")
    if status in {"REVIEW-B", "ACCEPTED"}:
        reviewer_b = _acceptance_review("reviewer-b", "review-b-1")
    body = {
        "schema_version": 1,
        "record_type": "mgtest.ai.live-tool-evidence-acceptance",
        "status": status,
        "evidence_kind": "authorization",
        "evidence_file_sha256": "1" * 64,
        "evidence_sha256": "2" * 64,
        "target_mgtest_commit": "a" * 40,
        "author_identity": "author",
        "reviewer_a": reviewer_a,
        "reviewer_b": reviewer_b,
        "external_reviewer_identity": "reviewer-b" if status == "ACCEPTED" else None,
        "accepted_revision": 1 if status == "ACCEPTED" else None,
        "trust_root_receipt_sha256": "3" * 64 if status == "ACCEPTED" else None,
    }
    return seal_record(body)


def _effective_acceptance(validated):
    if (
        validated["lifecycle_status"] == "ACCEPTED"
        and validated["authenticated_identity_verified"] is True
    ):
        return "ACCEPTED"
    return "BLOCKED"


def _expect_invalid_acceptance(record, label):
    try:
        validate_record(record)
    except EvidenceAcceptanceError:
        return
    raise StatusLatticeError(f"{label}: invalid acceptance promotion was accepted")


def verify_acceptance_lifecycle():
    weak_states = ("PROPOSED", "REVIEW-A", "REVIEW-B", "NEEDS-REVISION", "REJECTED")
    for state in weak_states:
        validated = validate_record(_acceptance_record(state))
        _require(validated["lifecycle_status"], state, f"acceptance {state} lifecycle")
        _require(_effective_acceptance(validated), "BLOCKED", f"acceptance {state} authority")

    for source in ("PROPOSED", "REVIEW-A", "REVIEW-B"):
        promoted = dict(_acceptance_record(source))
        promoted.pop("record_sha256")
        promoted["status"] = "ACCEPTED"
        _expect_invalid_acceptance(
            seal_record(promoted),
            f"acceptance invalid {source}->ACCEPTED",
        )

    accepted = validate_record(_acceptance_record("ACCEPTED"))
    _require(accepted["lifecycle_status"], "ACCEPTED", "acceptance structural accepted")
    _require(
        accepted["authenticated_identity_verified"],
        False,
        "acceptance authenticated identity unavailable",
    )
    _require(
        _effective_acceptance(accepted),
        "BLOCKED",
        "acceptance structural-only authority",
    )
    return {
        "status": "PASS",
        "non_authoritative_states_checked": len(weak_states) + 1,
        "invalid_promotions_rejected": 3,
    }


def _readiness(scenario, trust_status, promotion_enabled):
    return build_plan(
        ROOT / scenario,
        mgtest_commit="a" * 40,
        subject_provider="openai",
        subject_model="subject-model",
        evaluator_a_provider="openai",
        evaluator_a_model="judge-a",
        evaluator_b_provider="google-gemini",
        evaluator_b_model="judge-b",
        runs=100,
        trust_root_status=trust_status,
        stable_promotion_enabled=promotion_enabled,
    )


def verify_live_readiness():
    no_tool = "ai-tests/MGTEST-AI-FALSEPASS-001/v1/scenario.json"
    protected = _readiness(no_tool, "PROTECTED", True)
    _require(protected["status"], "READY", "readiness protected control")

    unprotected = _readiness(no_tool, "UNPROTECTED", False)
    _require(unprotected["status"], "BLOCKED", "readiness unprotected")
    _not_promoted(unprotected["status"], "readiness unprotected")

    tool_scenario = "ai-tests/MGTEST-AI-TOOLHONESTY-001/v3/scenario.json"
    missing_evidence = _readiness(tool_scenario, "PROTECTED", True)
    _require(missing_evidence["status"], "BLOCKED", "readiness missing live-tool evidence")
    _not_promoted(missing_evidence["status"], "readiness missing live-tool evidence")
    return {"status": "PASS", "degraded_cases_checked": 2}


def verify_stable_promotion_guard():
    protected = TRUST_ROOT_STATUS in {"PROTECTED", "ENFORCED"}
    if STABLE_PROMOTION_ENABLED and not protected:
        raise StatusLatticeError(
            "STABLE promotion enabled while repository trust root is not protected"
        )
    current = "ENABLED" if STABLE_PROMOTION_ENABLED else "BLOCKED"
    if not protected:
        _require(current, "BLOCKED", "promotion guard unprotected")
    return {
        "status": "PASS",
        "trust_root_status": TRUST_ROOT_STATUS,
        "stable_promotion_enabled": STABLE_PROMOTION_ENABLED,
    }


def run_all():
    checks = {
        "single_aggregate": verify_single_aggregate(),
        "dual_aggregate": verify_dual_aggregate(),
        "tool_aggregate": verify_tool_aggregate(),
        "cross_model_comparison": verify_cross_model_comparison(),
        "acceptance_lifecycle": verify_acceptance_lifecycle(),
        "live_readiness": verify_live_readiness(),
        "stable_promotion_guard": verify_stable_promotion_guard(),
    }
    return {
        "status": "PASS",
        "verifier": "mgtest.status-lattice-v2",
        "checks": checks,
    }


def main():
    try:
        report = run_all()
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": f"{type(exc).__name__}: {exc}"}, sort_keys=True))
        return 1
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
