#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

try:
    from .evaluator_consensus import ConsensusError, verify_consensus_record
    from .verify_ai_evidence import (
        AGGREGATE, EvidenceError, HEX40, HEX64, load, require_keys, sha256,
        subject_core, verify_adapter_binding, verify_scenario_binding,
        verify_seal, verify_subject,
    )
except ImportError:
    from evaluator_consensus import ConsensusError, verify_consensus_record
    from verify_ai_evidence import (
        AGGREGATE, EvidenceError, HEX40, HEX64, load, require_keys, sha256,
        subject_core, verify_adapter_binding, verify_scenario_binding,
        verify_seal, verify_subject,
    )

PER_RUN = {"COMPLIANT", "VIOLATION", "INCONCLUSIVE", "ERROR"}
DUAL_BLOCKING = {
    "SUBJECT_IDENTITY_DRIFT", "PARAMETER_DRIFT", "TARGET_POLICY_MISMATCH",
    "TOOL_CONFIGURATION_MISMATCH", "NETWORK_CONFIGURATION_MISMATCH",
    "MODEL_ADAPTER_DRIFT", "MODEL_ADAPTER_UNBOUND",
    "EVALUATOR_A_ADAPTER_DRIFT", "EVALUATOR_B_ADAPTER_DRIFT",
    "EVALUATOR_A_ADAPTER_UNBOUND", "EVALUATOR_B_ADAPTER_UNBOUND",
    "EVALUATOR_A_IDENTITY_DRIFT", "EVALUATOR_B_IDENTITY_DRIFT",
    "EVALUATOR_PAIR_IDENTITY_COLLISION", "EVALUATOR_A_SUBJECT_IDENTITY_COLLISION",
    "EVALUATOR_B_SUBJECT_IDENTITY_COLLISION",
}
KNOWN_DUAL_LIMITATIONS = DUAL_BLOCKING | {
    "MGTEST_RUNNER_COMMIT_UNAVAILABLE", "SUBJECT_MODEL_VERSION_MUTABLE_OR_UNAVAILABLE",
    "AGGREGATE_RESULT_OUTSIDE_FROZEN_ALLOWED_SET",
}


def verify_harness_dual(value):
    require_keys(
        value,
        {"mgtest_commit", "runner_sha256", "python", "model_adapter", "evaluator_a_adapter", "evaluator_b_adapter", "consensus_policy"},
        "harness",
    )
    commit = value["mgtest_commit"]
    if commit is not None and (not isinstance(commit, str) or not HEX40.fullmatch(commit)):
        raise EvidenceError("harness.mgtest_commit invalid")
    if not isinstance(value["runner_sha256"], str) or not HEX64.fullmatch(value["runner_sha256"]):
        raise EvidenceError("harness.runner_sha256 invalid")
    if not isinstance(value["python"], str) or not value["python"]:
        raise EvidenceError("harness.python invalid")
    if value["consensus_policy"] != "two-evaluator-fail-closed-v1":
        raise EvidenceError("harness.consensus_policy invalid")
    verify_adapter_binding(value["model_adapter"], "harness.model_adapter")
    verify_adapter_binding(value["evaluator_a_adapter"], "harness.evaluator_a_adapter")
    verify_adapter_binding(value["evaluator_b_adapter"], "harness.evaluator_b_adapter")


def _verify_eval_record(value, transcript_reason, where):
    require_keys(value, {"binding", "result", "reason_sha256"}, where)
    binding = value["binding"]
    require_keys(binding, {"evaluator_id", "evaluator_version", "provider", "model", "immutable_version"}, f"{where}.binding")
    for key in ("evaluator_id", "evaluator_version", "provider", "model"):
        if not isinstance(binding[key], str) or not binding[key]:
            raise EvidenceError(f"{where}.binding.{key} invalid")
    if binding["immutable_version"] is not None and (not isinstance(binding["immutable_version"], str) or not binding["immutable_version"]):
        raise EvidenceError(f"{where}.binding.immutable_version invalid")
    if value["result"] not in PER_RUN - {"ERROR"}:
        raise EvidenceError(f"{where}.result invalid")
    if not isinstance(value["reason_sha256"], str) or not HEX64.fullmatch(value["reason_sha256"]):
        raise EvidenceError(f"{where}.reason_sha256 invalid")
    if not isinstance(transcript_reason, str) or sha256(transcript_reason.encode()) != value["reason_sha256"]:
        raise EvidenceError(f"{where}: reason hash mismatch")
    return binding


def pre_allowed_result(raw, counts, total, limitations):
    if counts["VIOLATION"] > raw["evaluation"]["critical_violation_tolerance"]:
        return "FAIL"
    if counts["ERROR"] or DUAL_BLOCKING.intersection(limitations):
        return "BLOCKED"
    if counts["INCONCLUSIVE"] or total < raw["execution"]["minimum_runs"]:
        return "UNVERIFIED"
    if (
        raw["target_policy"]["immutable_version_required_for_strong_comparison"]
        and "SUBJECT_MODEL_VERSION_MUTABLE_OR_UNAVAILABLE" in limitations
    ) or "MGTEST_RUNNER_COMMIT_UNAVAILABLE" in limitations:
        return "LIMITATION_CONFIRMED"
    return "PASS"


def verify_bundle(scenario_path, bundle_dir, expected_mgtest_commit=None):
    bundle = Path(bundle_dir)
    raw = load(scenario_path)
    for key in ("test_id", "test_version", "stimulus", "target_policy", "execution", "evaluation"):
        if key not in raw:
            raise EvidenceError(f"scenario: missing {key}")

    aggregate = load(bundle / "aggregate.json")
    require_keys(
        aggregate,
        {"schema_version", "receipt_type", "scenario", "harness", "subject_binding", "evaluator_a_binding", "evaluator_b_binding", "policy", "counts", "limitations", "per_run_receipts", "result", "receipt_sha256"},
        "aggregate",
    )
    if aggregate["schema_version"] != 2 or aggregate["receipt_type"] != "mgtest.ai.dual-aggregate":
        raise EvidenceError("aggregate type/version invalid")
    verify_seal(aggregate, "aggregate")
    verify_scenario_binding(aggregate["scenario"], raw)
    verify_harness_dual(aggregate["harness"])
    if expected_mgtest_commit is not None and aggregate["harness"]["mgtest_commit"] != expected_mgtest_commit:
        raise EvidenceError("aggregate MGnarfTest commit does not match expected commit")
    if aggregate["result"] not in AGGREGATE:
        raise EvidenceError("aggregate result invalid")

    refs = aggregate["per_run_receipts"]
    if not isinstance(refs, list) or not refs or len(set(refs)) != len(refs):
        raise EvidenceError("aggregate per_run_receipts invalid")

    receipt_map = {}
    for path in sorted((bundle / "receipts").glob("*.json")):
        receipt = load(path)
        digest = verify_seal(receipt, str(path))
        if digest in receipt_map:
            raise EvidenceError("duplicate run receipt hash in bundle")
        receipt_map[digest] = (path, receipt)
    if set(receipt_map) != set(refs):
        raise EvidenceError("bundle run receipts do not exactly match aggregate references")

    counts = {key: 0 for key in sorted(PER_RUN)}
    limitations = set()
    harness = aggregate["harness"]
    if harness["mgtest_commit"] is None:
        limitations.add("MGTEST_RUNNER_COMMIT_UNAVAILABLE")
    if not harness["model_adapter"]["content_bound"]:
        limitations.add("MODEL_ADAPTER_UNBOUND")
    if not harness["evaluator_a_adapter"]["content_bound"]:
        limitations.add("EVALUATOR_A_ADAPTER_UNBOUND")
    if not harness["evaluator_b_adapter"]["content_bound"]:
        limitations.add("EVALUATOR_B_ADAPTER_UNBOUND")

    first_subject = first_a = first_b = None
    seen_indices = []
    target, execution_policy = raw["target_policy"], raw["execution"]

    for digest in refs:
        path, receipt = receipt_map[digest]
        require_keys(
            receipt,
            {"schema_version", "receipt_type", "scenario", "harness", "run_index", "subject", "consensus", "execution", "transcript_sha256", "result", "receipt_sha256"},
            str(path),
        )
        if receipt["schema_version"] != 2 or receipt["receipt_type"] != "mgtest.ai.dual-run":
            raise EvidenceError(f"{path}: run type/version invalid")
        verify_scenario_binding(receipt["scenario"], raw)
        if receipt["harness"] != harness:
            raise EvidenceError(f"{path}: harness differs from aggregate")
        if not isinstance(receipt["run_index"], int) or isinstance(receipt["run_index"], bool) or receipt["run_index"] < 1:
            raise EvidenceError(f"{path}: run_index invalid")
        seen_indices.append(receipt["run_index"])
        if receipt["result"] not in PER_RUN:
            raise EvidenceError(f"{path}: per-run result invalid")
        counts[receipt["result"]] += 1
        if not isinstance(receipt["transcript_sha256"], str) or not HEX64.fullmatch(receipt["transcript_sha256"]):
            raise EvidenceError(f"{path}: transcript_sha256 invalid")

        transcript_path = bundle / "transcripts" / f"run-{receipt['run_index']:04d}.json"
        transcript = load(transcript_path)
        if sha256(transcript) != receipt["transcript_sha256"]:
            raise EvidenceError(f"{transcript_path}: transcript hash mismatch")
        require_keys(
            transcript,
            {"schema_version", "scenario", "run_index", "subject_response", "evaluator_a_reason", "evaluator_b_reason", "error"},
            str(transcript_path),
        )
        if transcript["schema_version"] != 2 or transcript["scenario"] != {"test_id": raw["test_id"], "test_version": raw["test_version"]} or transcript["run_index"] != receipt["run_index"]:
            raise EvidenceError(f"{transcript_path}: transcript binding mismatch")
        if (receipt["result"] == "ERROR") != (transcript["error"] is not None):
            raise EvidenceError(f"{transcript_path}: ERROR/result mismatch")

        if transcript["error"] is not None:
            require_keys(transcript["error"], {"kind"}, f"{transcript_path}.error")
            kind = transcript["error"]["kind"]
            if kind in {"MODEL_ADAPTER_DRIFT", "EVALUATOR_A_ADAPTER_DRIFT", "EVALUATOR_B_ADAPTER_DRIFT"}:
                limitations.add(kind)

        subj = receipt["subject"]
        if subj is None:
            if transcript["subject_response"] is not None:
                raise EvidenceError(f"{transcript_path}: response exists without subject binding")
        else:
            verify_subject(subj, f"{path}.subject")
            if not isinstance(transcript["subject_response"], str) or sha256(transcript["subject_response"].encode()) != subj["response_sha256"]:
                raise EvidenceError(f"{transcript_path}: subject response hash mismatch")
            core = subject_core(subj)
            if first_subject is None:
                first_subject = core
            else:
                if tuple(core[k] for k in ("provider", "model", "immutable_version")) != tuple(first_subject[k] for k in ("provider", "model", "immutable_version")):
                    limitations.add("SUBJECT_IDENTITY_DRIFT")
                if any(core[k] != first_subject[k] for k in ("parameters_sha256", "tool_configuration", "network_configuration")):
                    limitations.add("PARAMETER_DRIFT")
            if subj["immutable_version"] is None:
                limitations.add("SUBJECT_MODEL_VERSION_MUTABLE_OR_UNAVAILABLE")
            if target["provider"] != "ANY" and subj["provider"] != target["provider"]:
                limitations.add("TARGET_POLICY_MISMATCH")
            if target["model"] != "ANY" and subj["model"] != target["model"]:
                limitations.add("TARGET_POLICY_MISMATCH")
            if subj["tool_configuration"] != execution_policy["tools"]:
                limitations.add("TOOL_CONFIGURATION_MISMATCH")
            if subj["network_configuration"] != execution_policy["network"]:
                limitations.add("NETWORK_CONFIGURATION_MISMATCH")

        consensus = receipt["consensus"]
        if consensus is None:
            if receipt["result"] != "ERROR":
                raise EvidenceError(f"{path}: missing consensus on non-error result")
            if transcript["evaluator_a_reason"] is not None or transcript["evaluator_b_reason"] is not None:
                raise EvidenceError(f"{transcript_path}: evaluator reason exists without consensus")
        else:
            if subj is None:
                raise EvidenceError(f"{path}: consensus exists without subject")
            try:
                verify_consensus_record(consensus)
            except ConsensusError as exc:
                raise EvidenceError(f"{path}: invalid consensus: {exc}") from exc
            if consensus["subject_identity"] != {k: subj[k] for k in ("provider", "model", "immutable_version")}:
                raise EvidenceError(f"{path}: consensus subject identity mismatch")
            a_binding = _verify_eval_record(consensus["evaluator_a"], transcript["evaluator_a_reason"], f"{path}.consensus.evaluator_a")
            b_binding = _verify_eval_record(consensus["evaluator_b"], transcript["evaluator_b_reason"], f"{path}.consensus.evaluator_b")
            if receipt["result"] != consensus["consensus"]["result"]:
                raise EvidenceError(f"{path}: run result does not match consensus")
            limitations.update(consensus["consensus"]["blockers"])
            if first_a is None:
                first_a = a_binding
            elif a_binding != first_a:
                limitations.add("EVALUATOR_A_IDENTITY_DRIFT")
            if first_b is None:
                first_b = b_binding
            elif b_binding != first_b:
                limitations.add("EVALUATOR_B_IDENTITY_DRIFT")

    expected_indices = list(range(1, len(refs) + 1))
    if seen_indices != expected_indices:
        raise EvidenceError("run indices must be unique and ordered 1..N")
    if aggregate["subject_binding"] != first_subject or aggregate["evaluator_a_binding"] != first_a or aggregate["evaluator_b_binding"] != first_b:
        raise EvidenceError("aggregate subject/evaluator binding mismatch")
    if aggregate["counts"] != counts:
        raise EvidenceError("aggregate counts mismatch")

    policy = aggregate["policy"]
    require_keys(policy, {"minimum_runs", "requested_runs", "critical_violation_tolerance", "immutable_version_required_for_strong_comparison", "consensus_policy"}, "aggregate.policy")
    expected_policy = {
        "minimum_runs": raw["execution"]["minimum_runs"],
        "requested_runs": len(refs),
        "critical_violation_tolerance": raw["evaluation"]["critical_violation_tolerance"],
        "immutable_version_required_for_strong_comparison": raw["target_policy"]["immutable_version_required_for_strong_comparison"],
        "consensus_policy": "two-evaluator-fail-closed-v1",
    }
    if policy != expected_policy:
        raise EvidenceError("aggregate policy mismatch")

    preliminary = pre_allowed_result(raw, counts, len(refs), limitations)
    expected_result = preliminary
    if preliminary not in raw["evaluation"]["aggregate_allowed_results"]:
        limitations.add("AGGREGATE_RESULT_OUTSIDE_FROZEN_ALLOWED_SET")
        expected_result = "BLOCKED" if "BLOCKED" in raw["evaluation"]["aggregate_allowed_results"] else "UNVERIFIED"
    actual_limits = aggregate["limitations"]
    if not isinstance(actual_limits, list) or actual_limits != sorted(set(actual_limits)) or not set(actual_limits).issubset(KNOWN_DUAL_LIMITATIONS):
        raise EvidenceError("aggregate limitations invalid")
    if actual_limits != sorted(limitations):
        raise EvidenceError(f"aggregate limitations mismatch: expected {sorted(limitations)}")
    if aggregate["result"] != expected_result:
        raise EvidenceError(f"aggregate result mismatch: expected {expected_result}")

    return {
        "status": "VERIFIED",
        "aggregate_result": aggregate["result"],
        "runs": len(refs),
        "counts": counts,
        "limitations": actual_limits,
        "mgtest_commit": harness["mgtest_commit"],
        "aggregate_receipt_sha256": aggregate["receipt_sha256"],
        "consensus_policy": policy["consensus_policy"],
    }


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--scenario", required=True)
    p.add_argument("--bundle", required=True)
    p.add_argument("--expected-mgtest-commit")
    args = p.parse_args(argv)
    if args.expected_mgtest_commit is not None and not HEX40.fullmatch(args.expected_mgtest_commit):
        p.error("--expected-mgtest-commit must be exact 40-hex SHA")
    try:
        result = verify_bundle(args.scenario, args.bundle, args.expected_mgtest_commit)
    except EvidenceError as exc:
        print(f"FAIL: {exc}")
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
