#!/usr/bin/env python3
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AI_TEST_ROOT = ROOT / "ai-tests"

STATUSES = {"PROPOSED", "REVIEW-A", "REVIEW-B", "STABLE", "NEEDS-REVISION", "BLOCKED", "REJECTED", "RETIRED"}
PER_RUN_RESULTS = {"COMPLIANT", "VIOLATION", "INCONCLUSIVE", "ERROR"}
AGGREGATE_RESULTS = {"PASS", "FAIL", "BLOCKED", "UNVERIFIED", "LIMITATION_CONFIRMED"}
ID_RE = re.compile(r"^MGTEST-AI-[A-Z0-9]+-[0-9]{3}$")
LABEL_RE = re.compile(r"^[A-Za-z0-9._-]+$")
OFFLINE_TOOL_PROFILE = "offline-deterministic-tools-v1"
CLAIM_BINDING_MODE = "claims-only-v1"
EVALUATOR_INDEPENDENCE_POLICY = "distinct-provider-v1"


class ValidationError(ValueError):
    pass


def require_exact_keys(obj, expected, where):
    if not isinstance(obj, dict):
        raise ValidationError(f"{where}: object required")
    actual = set(obj)
    expected = set(expected)
    missing = expected - actual
    unknown = actual - expected
    if missing or unknown:
        raise ValidationError(f"{where}: missing={sorted(missing)} unknown={sorted(unknown)}")


def require_nonempty_string(value, where):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{where}: non-empty string required")


def require_string_list(value, where):
    if not isinstance(value, list) or not value:
        raise ValidationError(f"{where}: non-empty list required")
    for index, item in enumerate(value):
        require_nonempty_string(item, f"{where}[{index}]")


def validate_tool_profile(value, where):
    require_exact_keys(value, {"profile", "max_steps", "initial_state"}, where)
    if value["profile"] != OFFLINE_TOOL_PROFILE:
        raise ValidationError(f"{where}.profile must be {OFFLINE_TOOL_PROFILE}")
    max_steps = value["max_steps"]
    if not isinstance(max_steps, int) or isinstance(max_steps, bool) or not 1 <= max_steps <= 16:
        raise ValidationError(f"{where}.max_steps must be integer 1..16")
    state = value["initial_state"]
    require_exact_keys(state, {"kv", "counters"}, f"{where}.initial_state")
    if not isinstance(state["kv"], dict) or not isinstance(state["counters"], dict):
        raise ValidationError(f"{where}.initial_state kv/counters objects required")
    for key, item in state["kv"].items():
        require_nonempty_string(key, f"{where}.initial_state.kv key")
        if not isinstance(item, str):
            raise ValidationError(f"{where}.initial_state.kv values must be strings")
    for key, item in state["counters"].items():
        require_nonempty_string(key, f"{where}.initial_state.counters key")
        if not isinstance(item, int) or isinstance(item, bool) or item < 0:
            raise ValidationError(f"{where}.initial_state.counters values must be non-negative integers")


def validate_claim_binding(value, where):
    require_exact_keys(value, {"version", "mode", "claims"}, where)
    if value["version"] != 1:
        raise ValidationError(f"{where}.version must be 1")
    if value["mode"] != CLAIM_BINDING_MODE:
        raise ValidationError(f"{where}.mode must be {CLAIM_BINDING_MODE}")
    claims = value["claims"]
    if not isinstance(claims, list) or not claims:
        raise ValidationError(f"{where}.claims must be non-empty list")
    labels = set()
    for index, claim in enumerate(claims):
        item_where = f"{where}.claims[{index}]"
        require_exact_keys(claim, {"label", "tool", "arguments", "result_field"}, item_where)
        require_nonempty_string(claim["label"], f"{item_where}.label")
        if not LABEL_RE.fullmatch(claim["label"]):
            raise ValidationError(f"{item_where}.label invalid")
        if claim["label"] in labels:
            raise ValidationError(f"{where}.claims duplicate label")
        labels.add(claim["label"])
        require_nonempty_string(claim["tool"], f"{item_where}.tool")
        if claim["tool"] not in {"kv.get", "kv.put", "counter.increment"}:
            raise ValidationError(f"{item_where}.tool unsupported")
        if not isinstance(claim["arguments"], dict):
            raise ValidationError(f"{item_where}.arguments object required")
        for key in claim["arguments"]:
            require_nonempty_string(key, f"{item_where}.arguments key")
        require_nonempty_string(claim["result_field"], f"{item_where}.result_field")


def validate_evaluator_independence(value, where):
    require_exact_keys(value, {"policy"}, where)
    if value["policy"] != EVALUATOR_INDEPENDENCE_POLICY:
        raise ValidationError(
            f"{where}.policy must be {EVALUATOR_INDEPENDENCE_POLICY}"
        )


def validate_scenario(path: Path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValidationError(f"{path}: invalid JSON: {exc}") from exc

    base_keys = {
        "schema_version", "test_id", "test_version", "status", "category", "purpose",
        "stimulus", "target_policy", "execution", "evaluation", "review", "limits",
    }
    allowed_root = base_keys | {"tool_profile", "claim_binding", "evaluator_independence"}
    if not isinstance(data, dict):
        raise ValidationError(f"{path}: object required")
    missing = base_keys - set(data)
    unknown = set(data) - allowed_root
    if missing or unknown:
        raise ValidationError(f"{path}: missing={sorted(missing)} unknown={sorted(unknown)}")

    if data["schema_version"] != 1:
        raise ValidationError(f"{path}: schema_version must be 1")
    if not isinstance(data["test_id"], str) or not ID_RE.fullmatch(data["test_id"]):
        raise ValidationError(f"{path}: invalid test_id")
    if not isinstance(data["test_version"], int) or isinstance(data["test_version"], bool) or data["test_version"] < 1:
        raise ValidationError(f"{path}: test_version must be positive integer")
    if data["status"] not in STATUSES:
        raise ValidationError(f"{path}: invalid status")
    require_nonempty_string(data["category"], f"{path}: category")
    require_nonempty_string(data["purpose"], f"{path}: purpose")

    parts = path.parts
    try:
        ai_index = parts.index("ai-tests")
        dir_test_id = parts[ai_index + 1]
        dir_version = parts[ai_index + 2]
    except (ValueError, IndexError) as exc:
        raise ValidationError(f"{path}: expected ai-tests/<test-id>/v<version>/scenario.json") from exc
    if dir_test_id != data["test_id"]:
        raise ValidationError(f"{path}: directory test id does not match manifest")
    if dir_version != f"v{data['test_version']}":
        raise ValidationError(f"{path}: directory version does not match manifest")

    stimulus = data["stimulus"]
    require_exact_keys(stimulus, {"system_context", "user_message"}, f"{path}: stimulus")
    require_nonempty_string(stimulus["system_context"], f"{path}: stimulus.system_context")
    require_nonempty_string(stimulus["user_message"], f"{path}: stimulus.user_message")

    target = data["target_policy"]
    require_exact_keys(target, {"provider", "model", "immutable_version_required_for_strong_comparison"}, f"{path}: target_policy")
    require_nonempty_string(target["provider"], f"{path}: target_policy.provider")
    require_nonempty_string(target["model"], f"{path}: target_policy.model")
    if not isinstance(target["immutable_version_required_for_strong_comparison"], bool):
        raise ValidationError(f"{path}: immutable_version_required_for_strong_comparison must be boolean")

    execution = data["execution"]
    require_exact_keys(execution, {"minimum_runs", "temperature_policy", "tools", "network"}, f"{path}: execution")
    if not isinstance(execution["minimum_runs"], int) or isinstance(execution["minimum_runs"], bool) or execution["minimum_runs"] < 1:
        raise ValidationError(f"{path}: minimum_runs must be positive integer")
    require_nonempty_string(execution["temperature_policy"], f"{path}: execution.temperature_policy")
    require_nonempty_string(execution["tools"], f"{path}: execution.tools")
    if not isinstance(execution["network"], bool):
        raise ValidationError(f"{path}: execution.network must be boolean")

    has_tool_profile = "tool_profile" in data
    has_claim_binding = "claim_binding" in data
    has_evaluator_independence = "evaluator_independence" in data
    if execution["tools"] == OFFLINE_TOOL_PROFILE:
        if execution["network"] is not False:
            raise ValidationError(f"{path}: offline tool profile requires network=false")
        if not has_tool_profile:
            raise ValidationError(f"{path}: offline tool profile requires tool_profile")
        validate_tool_profile(data["tool_profile"], f"{path}: tool_profile")
        if has_claim_binding:
            validate_claim_binding(data["claim_binding"], f"{path}: claim_binding")
        if has_evaluator_independence:
            validate_evaluator_independence(
                data["evaluator_independence"], f"{path}: evaluator_independence"
            )
    else:
        if has_tool_profile:
            raise ValidationError(f"{path}: tool_profile only allowed with tools={OFFLINE_TOOL_PROFILE}")
        if has_claim_binding:
            raise ValidationError(f"{path}: claim_binding requires tools={OFFLINE_TOOL_PROFILE}")
        if has_evaluator_independence:
            raise ValidationError(
                f"{path}: evaluator_independence requires tools={OFFLINE_TOOL_PROFILE}"
            )

    evaluation = data["evaluation"]
    require_exact_keys(
        evaluation,
        {"critical_invariants", "acceptable_behavior", "violation_examples", "per_run_results", "aggregate_allowed_results", "critical_violation_tolerance"},
        f"{path}: evaluation",
    )
    require_string_list(evaluation["critical_invariants"], f"{path}: evaluation.critical_invariants")
    require_string_list(evaluation["acceptable_behavior"], f"{path}: evaluation.acceptable_behavior")
    require_string_list(evaluation["violation_examples"], f"{path}: evaluation.violation_examples")
    if set(evaluation["per_run_results"]) != PER_RUN_RESULTS or len(evaluation["per_run_results"]) != len(PER_RUN_RESULTS):
        raise ValidationError(f"{path}: per_run_results must contain exactly {sorted(PER_RUN_RESULTS)}")
    if not isinstance(evaluation["aggregate_allowed_results"], list) or not evaluation["aggregate_allowed_results"]:
        raise ValidationError(f"{path}: aggregate_allowed_results must be non-empty list")
    if len(set(evaluation["aggregate_allowed_results"])) != len(evaluation["aggregate_allowed_results"]):
        raise ValidationError(f"{path}: duplicate aggregate result")
    if not set(evaluation["aggregate_allowed_results"]).issubset(AGGREGATE_RESULTS):
        raise ValidationError(f"{path}: invalid aggregate result")
    tolerance = evaluation["critical_violation_tolerance"]
    if not isinstance(tolerance, int) or isinstance(tolerance, bool) or tolerance < 0:
        raise ValidationError(f"{path}: critical_violation_tolerance must be non-negative integer")
    if tolerance >= execution["minimum_runs"]:
        raise ValidationError(f"{path}: critical_violation_tolerance must be lower than minimum_runs")

    review = data["review"]
    require_exact_keys(review, {"author", "reviewer_a", "reviewer_b", "external_reviewer_required", "external_reviewer"}, f"{path}: review")
    require_nonempty_string(review["author"], f"{path}: review.author")
    if review["external_reviewer_required"] is not True:
        raise ValidationError(f"{path}: external_reviewer_required must be true")
    for name in ("reviewer_a", "reviewer_b", "external_reviewer"):
        value = review[name]
        if value is not None:
            require_nonempty_string(value, f"{path}: review.{name}")

    if data["status"] == "STABLE":
        author = review["author"]
        a = review["reviewer_a"]
        b = review["reviewer_b"]
        external = review["external_reviewer"]
        if not all((a, b, external)):
            raise ValidationError(f"{path}: STABLE requires reviewer_a, reviewer_b and external_reviewer")
        if len({author, a, b}) != 3:
            raise ValidationError(f"{path}: STABLE author/reviewers must be three distinct identities")
        if external not in {a, b}:
            raise ValidationError(f"{path}: external_reviewer must equal reviewer_a or reviewer_b")

    require_string_list(data["limits"], f"{path}: limits")
    return data


def main() -> int:
    scenarios = sorted(AI_TEST_ROOT.glob("MGTEST-AI-*/v*/scenario.json"))
    if not scenarios:
        print("FAIL: no AI behavior scenarios found")
        return 1

    seen = set()
    try:
        for path in scenarios:
            data = validate_scenario(path)
            key = (data["test_id"], data["test_version"])
            if key in seen:
                raise ValidationError(f"{path}: duplicate test id/version {key}")
            seen.add(key)
    except ValidationError as exc:
        print(f"FAIL: {exc}")
        return 1

    print(f"PASS: validated {len(scenarios)} AI behavior scenarios")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
