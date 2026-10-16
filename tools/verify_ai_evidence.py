#!/usr/bin/env python3
import argparse
import hashlib
import json
import re
from pathlib import Path

PER_RUN = {"COMPLIANT", "VIOLATION", "INCONCLUSIVE", "ERROR"}
AGGREGATE = {"PASS", "FAIL", "BLOCKED", "UNVERIFIED", "LIMITATION_CONFIRMED"}
BLOCKING = {
    "EVALUATOR_IDENTITY_COLLISION", "SUBJECT_IDENTITY_DRIFT", "EVALUATOR_IDENTITY_DRIFT",
    "PARAMETER_DRIFT", "TARGET_POLICY_MISMATCH", "TOOL_CONFIGURATION_MISMATCH",
    "NETWORK_CONFIGURATION_MISMATCH", "MODEL_ADAPTER_DRIFT", "EVALUATOR_ADAPTER_DRIFT",
    "MODEL_ADAPTER_UNBOUND", "EVALUATOR_ADAPTER_UNBOUND",
}
KNOWN_LIMITATIONS = BLOCKING | {
    "MGTEST_RUNNER_COMMIT_UNAVAILABLE", "SUBJECT_MODEL_VERSION_MUTABLE_OR_UNAVAILABLE",
    "AGGREGATE_RESULT_OUTSIDE_FROZEN_ALLOWED_SET",
}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")


class EvidenceError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256(value):
    if not isinstance(value, (bytes, bytearray)):
        value = canonical(value)
    return hashlib.sha256(value).hexdigest()


def load(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"{path}: unreadable/invalid JSON") from exc
    if not isinstance(value, dict):
        raise EvidenceError(f"{path}: JSON object required")
    return value


def verify_seal(receipt, where):
    body = dict(receipt)
    actual = body.pop("receipt_sha256", None)
    if not isinstance(actual, str) or not HEX64.fullmatch(actual):
        raise EvidenceError(f"{where}: receipt_sha256 invalid")
    if actual != sha256(body):
        raise EvidenceError(f"{where}: receipt hash mismatch")
    return actual


def require_keys(value, required, where, optional=()):
    if not isinstance(value, dict):
        raise EvidenceError(f"{where}: object required")
    keys = set(value)
    required, optional = set(required), set(optional)
    missing = required - keys
    unknown = keys - required - optional
    if missing or unknown:
        raise EvidenceError(f"{where}: missing={sorted(missing)} unknown={sorted(unknown)}")


def verify_adapter_binding(value, where):
    require_keys(value, {"argv_sha256", "resolved_executable", "files", "content_bound"}, where)
    if not isinstance(value["argv_sha256"], str) or not HEX64.fullmatch(value["argv_sha256"]):
        raise EvidenceError(f"{where}: argv_sha256 invalid")
    if not isinstance(value["resolved_executable"], str) or not value["resolved_executable"]:
        raise EvidenceError(f"{where}: resolved_executable invalid")
    if not isinstance(value["files"], list):
        raise EvidenceError(f"{where}: files must be list")
    for i, item in enumerate(value["files"]):
        require_keys(item, {"arg_index", "path", "sha256"}, f"{where}.files[{i}]")
        if not isinstance(item["arg_index"], int) or isinstance(item["arg_index"], bool) or item["arg_index"] < 0:
            raise EvidenceError(f"{where}.files[{i}]: arg_index invalid")
        if not isinstance(item["path"], str) or not item["path"]:
            raise EvidenceError(f"{where}.files[{i}]: path invalid")
        if not isinstance(item["sha256"], str) or not HEX64.fullmatch(item["sha256"]):
            raise EvidenceError(f"{where}.files[{i}]: sha256 invalid")
    if value["content_bound"] is not bool(value["files"]):
        raise EvidenceError(f"{where}: content_bound inconsistent with files")


def verify_harness(value):
    require_keys(value, {"mgtest_commit", "runner_sha256", "python", "model_adapter", "evaluator_adapter"}, "harness")
    commit = value["mgtest_commit"]
    if commit is not None and (not isinstance(commit, str) or not HEX40.fullmatch(commit)):
        raise EvidenceError("harness.mgtest_commit invalid")
    if not isinstance(value["runner_sha256"], str) or not HEX64.fullmatch(value["runner_sha256"]):
        raise EvidenceError("harness.runner_sha256 invalid")
    if not isinstance(value["python"], str) or not value["python"]:
        raise EvidenceError("harness.python invalid")
    verify_adapter_binding(value["model_adapter"], "harness.model_adapter")
    verify_adapter_binding(value["evaluator_adapter"], "harness.evaluator_adapter")


def verify_scenario_binding(binding, raw):
    require_keys(binding, {"test_id", "test_version", "scenario_sha256", "context_sha256"}, "scenario binding")
    if binding["test_id"] != raw.get("test_id") or binding["test_version"] != raw.get("test_version"):
        raise EvidenceError("scenario id/version mismatch")
    if binding["scenario_sha256"] != sha256(raw):
        raise EvidenceError("scenario content hash mismatch")
    if binding["context_sha256"] != sha256(raw.get("stimulus")):
        raise EvidenceError("scenario context hash mismatch")


def subject_core(subject):
    return {k: subject[k] for k in ("provider", "model", "immutable_version", "parameters_sha256", "tool_configuration", "network_configuration")}


def evaluator_core(evaluator):
    return {k: evaluator[k] for k in ("evaluator_id", "evaluator_version", "provider", "model", "immutable_version")}


def verify_subject(value, where):
    require_keys(value, {"provider", "model", "immutable_version", "parameters_sha256", "tool_configuration", "network_configuration", "response_sha256"}, where)
    for key in ("provider", "model", "tool_configuration"):
        if not isinstance(value[key], str) or not value[key]:
            raise EvidenceError(f"{where}.{key} invalid")
    if value["immutable_version"] is not None and (not isinstance(value["immutable_version"], str) or not value["immutable_version"]):
        raise EvidenceError(f"{where}.immutable_version invalid")
    for key in ("parameters_sha256", "response_sha256"):
        if not isinstance(value[key], str) or not HEX64.fullmatch(value[key]):
            raise EvidenceError(f"{where}.{key} invalid")
    if not isinstance(value["network_configuration"], bool):
        raise EvidenceError(f"{where}.network_configuration invalid")


def verify_evaluator(value, where):
    require_keys(value, {"evaluator_id", "evaluator_version", "provider", "model", "immutable_version", "reason_sha256"}, where)
    for key in ("evaluator_id", "evaluator_version", "provider", "model"):
        if not isinstance(value[key], str) or not value[key]:
            raise EvidenceError(f"{where}.{key} invalid")
    if value["immutable_version"] is not None and (not isinstance(value["immutable_version"], str) or not value["immutable_version"]):
        raise EvidenceError(f"{where}.immutable_version invalid")
    if not isinstance(value["reason_sha256"], str) or not HEX64.fullmatch(value["reason_sha256"]):
        raise EvidenceError(f"{where}.reason_sha256 invalid")


def pre_allowed_result(raw, counts, total, limitations):
    if counts["VIOLATION"] > raw["evaluation"]["critical_violation_tolerance"]:
        return "FAIL"
    if counts["ERROR"] or BLOCKING.intersection(limitations):
        return "BLOCKED"
    if counts["INCONCLUSIVE"] or total < raw["execution"]["minimum_runs"]:
        return "UNVERIFIED"
    if (raw["target_policy"]["immutable_version_required_for_strong_comparison"] and "SUBJECT_MODEL_VERSION_MUTABLE_OR_UNAVAILABLE" in limitations) or "MGTEST_RUNNER_COMMIT_UNAVAILABLE" in limitations:
        return "LIMITATION_CONFIRMED"
    return "PASS"


def verify_bundle(scenario_path, bundle_dir, expected_mgtest_commit=None):
    bundle = Path(bundle_dir)
    raw = load(scenario_path)
    for key in ("test_id", "test_version", "stimulus", "target_policy", "execution", "evaluation"):
        if key not in raw:
            raise EvidenceError(f"scenario: missing {key}")
    aggregate = load(bundle / "aggregate.json")
    require_keys(aggregate, {"schema_version", "receipt_type", "scenario", "harness", "subject_binding", "evaluator_binding", "policy", "counts", "limitations", "per_run_receipts", "result", "receipt_sha256"}, "aggregate")
    if aggregate["schema_version"] != 1 or aggregate["receipt_type"] != "mgtest.ai.aggregate":
        raise EvidenceError("aggregate type/version invalid")
    verify_seal(aggregate, "aggregate")
    verify_scenario_binding(aggregate["scenario"], raw)
    verify_harness(aggregate["harness"])
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
    if not harness["evaluator_adapter"]["content_bound"]:
        limitations.add("EVALUATOR_ADAPTER_UNBOUND")
    first_subject = first_evaluator = None
    seen_indices = []
    target, execution_policy = raw["target_policy"], raw["execution"]

    for digest in refs:
        path, receipt = receipt_map[digest]
        require_keys(receipt, {"schema_version", "receipt_type", "scenario", "harness", "run_index", "subject", "evaluator", "execution", "transcript_sha256", "result", "receipt_sha256"}, str(path))
        if receipt["schema_version"] != 1 or receipt["receipt_type"] != "mgtest.ai.run":
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
        require_keys(transcript, {"schema_version", "scenario", "run_index", "subject_response", "evaluator_reason", "error"}, str(transcript_path))
        if transcript["schema_version"] != 1 or transcript["scenario"] != {"test_id": raw["test_id"], "test_version": raw["test_version"]} or transcript["run_index"] != receipt["run_index"]:
            raise EvidenceError(f"{transcript_path}: transcript binding mismatch")
        if (receipt["result"] == "ERROR") != (transcript["error"] is not None):
            raise EvidenceError(f"{transcript_path}: ERROR/result mismatch")
        if transcript["error"] is not None:
            require_keys(transcript["error"], {"kind"}, f"{transcript_path}.error")
            if transcript["error"]["kind"] == "MODEL_ADAPTER_DRIFT": limitations.add("MODEL_ADAPTER_DRIFT")
            if transcript["error"]["kind"] == "EVALUATOR_ADAPTER_DRIFT": limitations.add("EVALUATOR_ADAPTER_DRIFT")

        subj = receipt["subject"]
        if subj is None:
            if transcript["subject_response"] is not None:
                raise EvidenceError(f"{transcript_path}: response exists without subject binding")
        else:
            verify_subject(subj, f"{path}.subject")
            if not isinstance(transcript["subject_response"], str) or sha256(transcript["subject_response"].encode()) != subj["response_sha256"]:
                raise EvidenceError(f"{transcript_path}: subject response hash mismatch")
            core = subject_core(subj)
            if first_subject is None: first_subject = core
            else:
                if tuple(core[k] for k in ("provider", "model", "immutable_version")) != tuple(first_subject[k] for k in ("provider", "model", "immutable_version")): limitations.add("SUBJECT_IDENTITY_DRIFT")
                if any(core[k] != first_subject[k] for k in ("parameters_sha256", "tool_configuration", "network_configuration")): limitations.add("PARAMETER_DRIFT")
            if subj["immutable_version"] is None: limitations.add("SUBJECT_MODEL_VERSION_MUTABLE_OR_UNAVAILABLE")
            if target["provider"] != "ANY" and subj["provider"] != target["provider"]: limitations.add("TARGET_POLICY_MISMATCH")
            if target["model"] != "ANY" and subj["model"] != target["model"]: limitations.add("TARGET_POLICY_MISMATCH")
            if subj["tool_configuration"] != execution_policy["tools"]: limitations.add("TOOL_CONFIGURATION_MISMATCH")
            if subj["network_configuration"] != execution_policy["network"]: limitations.add("NETWORK_CONFIGURATION_MISMATCH")

        ev = receipt["evaluator"]
        if ev is None:
            if transcript["evaluator_reason"] is not None:
                raise EvidenceError(f"{transcript_path}: evaluator reason exists without binding")
        else:
            verify_evaluator(ev, f"{path}.evaluator")
            if not isinstance(transcript["evaluator_reason"], str) or sha256(transcript["evaluator_reason"].encode()) != ev["reason_sha256"]:
                raise EvidenceError(f"{transcript_path}: evaluator reason hash mismatch")
            core = evaluator_core(ev)
            if first_evaluator is None: first_evaluator = core
            elif core != first_evaluator: limitations.add("EVALUATOR_IDENTITY_DRIFT")
            if subj is not None and (subj["provider"], subj["model"], subj["immutable_version"]) == (ev["provider"], ev["model"], ev["immutable_version"]): limitations.add("EVALUATOR_IDENTITY_COLLISION")

    expected_indices = list(range(1, len(refs) + 1))
    if seen_indices != expected_indices:
        raise EvidenceError("run indices must be unique and ordered 1..N")
    if aggregate["subject_binding"] != first_subject or aggregate["evaluator_binding"] != first_evaluator:
        raise EvidenceError("aggregate subject/evaluator binding mismatch")
    if aggregate["counts"] != counts:
        raise EvidenceError("aggregate counts mismatch")

    policy = aggregate["policy"]
    require_keys(policy, {"minimum_runs", "requested_runs", "critical_violation_tolerance", "immutable_version_required_for_strong_comparison"}, "aggregate.policy")
    expected_policy = {
        "minimum_runs": raw["execution"]["minimum_runs"], "requested_runs": len(refs),
        "critical_violation_tolerance": raw["evaluation"]["critical_violation_tolerance"],
        "immutable_version_required_for_strong_comparison": raw["target_policy"]["immutable_version_required_for_strong_comparison"],
    }
    if policy != expected_policy:
        raise EvidenceError("aggregate policy mismatch")

    preliminary = pre_allowed_result(raw, counts, len(refs), limitations)
    expected_result = preliminary
    if preliminary not in raw["evaluation"]["aggregate_allowed_results"]:
        limitations.add("AGGREGATE_RESULT_OUTSIDE_FROZEN_ALLOWED_SET")
        expected_result = "BLOCKED" if "BLOCKED" in raw["evaluation"]["aggregate_allowed_results"] else "UNVERIFIED"
    actual_limits = aggregate["limitations"]
    if not isinstance(actual_limits, list) or actual_limits != sorted(set(actual_limits)) or not set(actual_limits).issubset(KNOWN_LIMITATIONS):
        raise EvidenceError("aggregate limitations invalid")
    if actual_limits != sorted(limitations):
        raise EvidenceError(f"aggregate limitations mismatch: expected {sorted(limitations)}")
    if aggregate["result"] != expected_result:
        raise EvidenceError(f"aggregate result mismatch: expected {expected_result}")

    return {"status": "VERIFIED", "aggregate_result": aggregate["result"], "runs": len(refs), "counts": counts, "limitations": actual_limits, "mgtest_commit": harness["mgtest_commit"], "aggregate_receipt_sha256": aggregate["receipt_sha256"]}


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
