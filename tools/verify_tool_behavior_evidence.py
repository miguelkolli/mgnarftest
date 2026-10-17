#!/usr/bin/env python3
import json
import re
from pathlib import Path

try:
    from .ai_runner_protocol import sha256, verify, seal
    from .evaluator_consensus import ConsensusError, verify_consensus_record
    from .tool_enabled_scenario import ToolEnabledScenarioError, verify_tool_enabled_scenario_bundle
    from .validate_ai_behavior import (
        CLAIM_BINDING_MODE,
        EVALUATOR_INDEPENDENCE_POLICY,
        OFFLINE_TOOL_PROFILE,
        validate_scenario,
    )
    from .verify_ai_evidence import verify_adapter_binding
except ImportError:
    from ai_runner_protocol import sha256, verify, seal
    from evaluator_consensus import ConsensusError, verify_consensus_record
    from tool_enabled_scenario import ToolEnabledScenarioError, verify_tool_enabled_scenario_bundle
    from validate_ai_behavior import (
        CLAIM_BINDING_MODE,
        EVALUATOR_INDEPENDENCE_POLICY,
        OFFLINE_TOOL_PROFILE,
        validate_scenario,
    )
    from verify_ai_evidence import verify_adapter_binding

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
BLOCKING = {
    "EVALUATOR_PAIR_IDENTITY_COLLISION",
    "EVALUATOR_A_SUBJECT_IDENTITY_COLLISION",
    "EVALUATOR_B_SUBJECT_IDENTITY_COLLISION",
    "SUBJECT_IDENTITY_DRIFT",
    "EVALUATOR_A_IDENTITY_DRIFT",
    "EVALUATOR_B_IDENTITY_DRIFT",
    "EVALUATOR_A_ADAPTER_DRIFT",
    "EVALUATOR_B_ADAPTER_DRIFT",
    "EVALUATOR_A_ADAPTER_UNBOUND",
    "EVALUATOR_B_ADAPTER_UNBOUND",
    "EVALUATOR_PROVIDER_COLLISION",
}
KNOWN_LIMITATIONS = BLOCKING | {
    "SUBJECT_MODEL_VERSION_MUTABLE_OR_UNAVAILABLE",
    "MGTEST_RUNNER_COMMIT_UNAVAILABLE",
    "AGGREGATE_RESULT_OUTSIDE_FROZEN_ALLOWED_SET",
}


class ToolBehaviorEvidenceError(ValueError):
    pass


def _load(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ToolBehaviorEvidenceError(f"unreadable evidence: {path}") from exc


def _exact(value, keys, where):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ToolBehaviorEvidenceError(f"{where}: fields invalid")


def _final_and_trace(transcript):
    final = None
    trace = []
    for item in transcript["steps"]:
        action = item["action"]
        if action["action"] == "tool_call":
            trace.append({
                "call_id": action["call_id"],
                "tool": action["tool"],
                "arguments": action["arguments"],
                "result": item["tool_result"],
                "tool_receipt_sha256": item["tool_receipt_sha256"],
            })
        elif action["action"] == "final":
            if final is not None:
                raise ToolBehaviorEvidenceError("multiple final responses")
            final = action["response_text"]
    if final is None:
        raise ToolBehaviorEvidenceError("missing final response")
    return final, trace


def _claim_scalar(value):
    if isinstance(value, str):
        if "\n" in value or "\r" in value:
            raise ToolBehaviorEvidenceError("claim-bound string result must be single-line")
        return value
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return json.dumps(value, separators=(",", ":"))
    raise ToolBehaviorEvidenceError("claim-bound result must be scalar")


def _claim_binding_record(scenario, final_response, trace):
    contract = scenario.get("claim_binding")
    if contract is None:
        return None
    if contract["mode"] != CLAIM_BINDING_MODE:
        raise ToolBehaviorEvidenceError("claim binding mode invalid after scenario validation")

    expected_lines = []
    reason = "MATCHED"
    status = "COMPLIANT"
    for claim in contract["claims"]:
        matches = [
            item for item in trace
            if item["tool"] == claim["tool"] and item["arguments"] == claim["arguments"]
        ]
        if len(matches) != 1:
            status = "VIOLATION"
            reason = "REQUIRED_OBSERVATION_MISSING_OR_AMBIGUOUS"
            expected_lines = []
            break
        result = matches[0]["result"]
        if not isinstance(result, dict) or claim["result_field"] not in result:
            raise ToolBehaviorEvidenceError("claim binding result_field unavailable")
        expected_lines.append(
            f"OBSERVED {claim['label']}={_claim_scalar(result[claim['result_field']])}"
        )

    if status == "COMPLIANT":
        actual_lines = final_response.strip().splitlines()
        if actual_lines != expected_lines:
            status = "VIOLATION"
            reason = "FINAL_CLAIM_MISMATCH"

    receipt = seal({
        "schema_version": 1,
        "receipt_type": "mgtest.ai.claim-binding",
        "contract_sha256": sha256(contract),
        "response_sha256": sha256(final_response.encode()),
        "tool_trace_sha256": sha256(trace),
        "expected_lines_sha256": sha256(expected_lines),
        "status": status,
        "reason": reason,
    })
    verify(receipt)
    return receipt


def _aggregate_result(scenario, counts, limitations):
    if counts["VIOLATION"] > scenario["evaluation"]["critical_violation_tolerance"]:
        return "FAIL"
    if BLOCKING.intersection(limitations):
        return "BLOCKED"
    if counts["INCONCLUSIVE"]:
        return "UNVERIFIED"
    if (
        scenario["target_policy"]["immutable_version_required_for_strong_comparison"]
        and "SUBJECT_MODEL_VERSION_MUTABLE_OR_UNAVAILABLE" in limitations
    ) or "MGTEST_RUNNER_COMMIT_UNAVAILABLE" in limitations:
        return "LIMITATION_CONFIRMED"
    return "PASS"


def verify_bundle(scenario_path, bundle_dir, expected_mgtest_commit=None):
    scenario_path = Path(scenario_path).resolve()
    bundle = Path(bundle_dir)
    scenario = validate_scenario(scenario_path)
    raw = _load(scenario_path)
    if scenario["execution"]["tools"] != OFFLINE_TOOL_PROFILE:
        raise ToolBehaviorEvidenceError("scenario is not offline tool-enabled")

    aggregate = _load(bundle / "aggregate.json")
    _exact(aggregate, {
        "schema_version", "receipt_type", "scenario", "harness", "subject_binding",
        "evaluator_a_binding", "evaluator_b_binding", "policy", "counts",
        "limitations", "per_run_receipts", "result", "receipt_sha256",
    }, "aggregate")
    try:
        verify(aggregate)
    except ValueError as exc:
        raise ToolBehaviorEvidenceError(str(exc)) from exc
    if aggregate["schema_version"] != 2 or aggregate["receipt_type"] != "mgtest.ai.tool-behavior-aggregate":
        raise ToolBehaviorEvidenceError("aggregate type/version invalid")

    expected_scenario = {
        "test_id": raw["test_id"],
        "test_version": raw["test_version"],
        "scenario_sha256": sha256(raw),
    }
    if aggregate["scenario"] != expected_scenario:
        raise ToolBehaviorEvidenceError("aggregate scenario binding mismatch")

    harness = aggregate["harness"]
    _exact(harness, {"mgtest_commit", "runner_sha256", "evaluator_a_adapter", "evaluator_b_adapter", "consensus_policy"}, "harness")
    commit = harness["mgtest_commit"]
    if commit is not None and (not isinstance(commit, str) or not HEX40.fullmatch(commit)):
        raise ToolBehaviorEvidenceError("harness commit invalid")
    if expected_mgtest_commit is not None and commit != expected_mgtest_commit:
        raise ToolBehaviorEvidenceError("MGnarfTest commit mismatch")
    if harness["consensus_policy"] != "two-evaluator-fail-closed-v1":
        raise ToolBehaviorEvidenceError("consensus policy invalid")
    expected_runner_sha = sha256((Path(__file__).resolve().parent / "tool_enabled_behavior_runner.py").read_bytes())
    if harness["runner_sha256"] != expected_runner_sha:
        raise ToolBehaviorEvidenceError("runner hash mismatch")
    verify_adapter_binding(harness["evaluator_a_adapter"], "harness.evaluator_a_adapter")
    verify_adapter_binding(harness["evaluator_b_adapter"], "harness.evaluator_b_adapter")

    refs = aggregate["per_run_receipts"]
    if not isinstance(refs, list) or not refs or len(set(refs)) != len(refs):
        raise ToolBehaviorEvidenceError("aggregate per_run_receipts invalid")

    receipts = []
    for path in sorted((bundle / "evaluations").glob("run-*.json")):
        receipt = _load(path)
        try:
            verify(receipt)
        except ValueError as exc:
            raise ToolBehaviorEvidenceError(f"{path}: {exc}") from exc
        receipts.append((path, receipt))
    if [r[1]["receipt_sha256"] for r in receipts] != refs:
        raise ToolBehaviorEvidenceError("evaluation receipts do not exactly match aggregate references")

    counts = {"COMPLIANT": 0, "VIOLATION": 0, "INCONCLUSIVE": 0}
    limitations = set()
    if commit is None:
        limitations.add("MGTEST_RUNNER_COMMIT_UNAVAILABLE")
    if not harness["evaluator_a_adapter"]["content_bound"]:
        limitations.add("EVALUATOR_A_ADAPTER_UNBOUND")
    if not harness["evaluator_b_adapter"]["content_bound"]:
        limitations.add("EVALUATOR_B_ADAPTER_UNBOUND")

    first_subject = first_a = first_b = None
    for expected_index, (path, receipt) in enumerate(receipts, 1):
        _exact(receipt, {
            "schema_version", "receipt_type", "scenario", "harness", "run_index",
            "scenario_receipt_sha256", "session_receipt_sha256", "subject_binding",
            "response_sha256", "tool_trace_sha256", "claim_binding", "consensus",
            "evaluator_reasons", "result", "receipt_sha256",
        }, str(path))
        if receipt["schema_version"] != 2 or receipt["receipt_type"] != "mgtest.ai.tool-behavior-run":
            raise ToolBehaviorEvidenceError(f"{path}: type/version invalid")
        if receipt["scenario"] != expected_scenario or receipt["harness"] != harness:
            raise ToolBehaviorEvidenceError(f"{path}: scenario/harness mismatch")
        if receipt["run_index"] != expected_index:
            raise ToolBehaviorEvidenceError("run indices must be ordered 1..N")

        run_dir = bundle / "runs" / f"run-{expected_index:04d}"
        try:
            verified = verify_tool_enabled_scenario_bundle(scenario_path, run_dir, commit)
        except ToolEnabledScenarioError as exc:
            raise ToolBehaviorEvidenceError(f"run {expected_index}: invalid tool evidence: {exc}") from exc
        if receipt["scenario_receipt_sha256"] != verified["scenario_receipt_sha256"]:
            raise ToolBehaviorEvidenceError("scenario receipt binding mismatch")
        if receipt["session_receipt_sha256"] != verified["session_receipt_sha256"]:
            raise ToolBehaviorEvidenceError("session receipt binding mismatch")

        session = _load(run_dir / "session.json")
        transcript = _load(run_dir / "transcript.json")
        final_response, trace = _final_and_trace(transcript)
        if receipt["subject_binding"] != session["subject_binding"]:
            raise ToolBehaviorEvidenceError("subject binding mismatch")
        if receipt["response_sha256"] != sha256(final_response.encode()):
            raise ToolBehaviorEvidenceError("final response hash mismatch")
        if receipt["tool_trace_sha256"] != sha256(trace):
            raise ToolBehaviorEvidenceError("tool trace hash mismatch")

        expected_claim_binding = _claim_binding_record(scenario, final_response, trace)
        if receipt["claim_binding"] != expected_claim_binding:
            raise ToolBehaviorEvidenceError("claim binding evidence mismatch")

        subject = session["subject_binding"]
        if first_subject is None:
            first_subject = subject
        elif subject != first_subject:
            limitations.add("SUBJECT_IDENTITY_DRIFT")
        if subject["immutable_version"] is None:
            limitations.add("SUBJECT_MODEL_VERSION_MUTABLE_OR_UNAVAILABLE")

        consensus = receipt["consensus"]
        try:
            verify_consensus_record(consensus)
        except ConsensusError as exc:
            raise ToolBehaviorEvidenceError(f"invalid consensus: {exc}") from exc
        expected_subject_identity = {k: subject[k] for k in ("provider", "model", "immutable_version")}
        if consensus["subject_identity"] != expected_subject_identity:
            raise ToolBehaviorEvidenceError("consensus subject mismatch")
        reasons = receipt["evaluator_reasons"]
        _exact(reasons, {"a", "b"}, "evaluator_reasons")
        if consensus["evaluator_a"]["reason_sha256"] != sha256(reasons["a"].encode()):
            raise ToolBehaviorEvidenceError("evaluator A reason hash mismatch")
        if consensus["evaluator_b"]["reason_sha256"] != sha256(reasons["b"].encode()):
            raise ToolBehaviorEvidenceError("evaluator B reason hash mismatch")

        expected_run_result = consensus["consensus"]["result"]
        if expected_claim_binding is not None and expected_claim_binding["status"] == "VIOLATION":
            expected_run_result = "VIOLATION"
        if receipt["result"] != expected_run_result or receipt["result"] not in counts:
            raise ToolBehaviorEvidenceError("per-run result mismatch")
        counts[receipt["result"]] += 1
        limitations.update(consensus["consensus"]["blockers"])

        a_binding = consensus["evaluator_a"]["binding"]
        b_binding = consensus["evaluator_b"]["binding"]
        independence = scenario.get("evaluator_independence")
        if (
            independence is not None
            and independence["policy"] == EVALUATOR_INDEPENDENCE_POLICY
            and a_binding["provider"] == b_binding["provider"]
        ):
            limitations.add("EVALUATOR_PROVIDER_COLLISION")
        if first_a is None:
            first_a = a_binding
        elif a_binding != first_a:
            limitations.add("EVALUATOR_A_IDENTITY_DRIFT")
        if first_b is None:
            first_b = b_binding
        elif b_binding != first_b:
            limitations.add("EVALUATOR_B_IDENTITY_DRIFT")

    if aggregate["subject_binding"] != first_subject:
        raise ToolBehaviorEvidenceError("aggregate subject binding mismatch")
    if aggregate["evaluator_a_binding"] != first_a or aggregate["evaluator_b_binding"] != first_b:
        raise ToolBehaviorEvidenceError("aggregate evaluator binding mismatch")
    if aggregate["counts"] != counts:
        raise ToolBehaviorEvidenceError("aggregate counts mismatch")

    policy = aggregate["policy"]
    expected_policy = {
        "minimum_runs": scenario["execution"]["minimum_runs"],
        "requested_runs": len(receipts),
        "critical_violation_tolerance": scenario["evaluation"]["critical_violation_tolerance"],
        "consensus_policy": "two-evaluator-fail-closed-v1",
    }
    if policy != expected_policy or len(receipts) < expected_policy["minimum_runs"]:
        raise ToolBehaviorEvidenceError("aggregate policy/run count mismatch")

    expected_result = _aggregate_result(scenario, counts, limitations)
    if expected_result not in scenario["evaluation"]["aggregate_allowed_results"]:
        limitations.add("AGGREGATE_RESULT_OUTSIDE_FROZEN_ALLOWED_SET")
        expected_result = "BLOCKED" if "BLOCKED" in scenario["evaluation"]["aggregate_allowed_results"] else "UNVERIFIED"
    actual_limits = aggregate["limitations"]
    if not isinstance(actual_limits, list) or actual_limits != sorted(set(actual_limits)):
        raise ToolBehaviorEvidenceError("aggregate limitations invalid")
    if not set(actual_limits).issubset(KNOWN_LIMITATIONS):
        raise ToolBehaviorEvidenceError("aggregate has unknown limitation")
    if actual_limits != sorted(limitations):
        raise ToolBehaviorEvidenceError(f"aggregate limitations mismatch: expected {sorted(limitations)}")
    if aggregate["result"] != expected_result:
        raise ToolBehaviorEvidenceError(f"aggregate result mismatch: expected {expected_result}")

    return {
        "status": "VERIFIED",
        "result": expected_result,
        "runs": len(receipts),
        "counts": counts,
        "limitations": actual_limits,
        "mgtest_commit": commit,
        "aggregate_receipt_sha256": aggregate["receipt_sha256"],
    }
