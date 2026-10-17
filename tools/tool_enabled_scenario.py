#!/usr/bin/env python3
import json
from pathlib import Path

try:
    from .ai_runner_protocol import seal, sha256, verify
    from .offline_tool_agent import PROFILE_ID, ToolAgentError, run_tool_session
    from .validate_ai_behavior import OFFLINE_TOOL_PROFILE, ValidationError, validate_scenario
    from .verify_offline_tool_session import ToolSessionEvidenceError, verify_bundle as verify_tool_session_bundle
except ImportError:
    from ai_runner_protocol import seal, sha256, verify
    from offline_tool_agent import PROFILE_ID, ToolAgentError, run_tool_session
    from validate_ai_behavior import OFFLINE_TOOL_PROFILE, ValidationError, validate_scenario
    from verify_offline_tool_session import ToolSessionEvidenceError, verify_bundle as verify_tool_session_bundle


class ToolEnabledScenarioError(ValueError):
    pass


def build_tool_spec(scenario_path):
    path = Path(scenario_path).resolve()
    try:
        scenario = validate_scenario(path)
    except ValidationError as exc:
        raise ToolEnabledScenarioError(str(exc)) from exc
    if scenario["execution"]["tools"] != OFFLINE_TOOL_PROFILE:
        raise ToolEnabledScenarioError("scenario is not tool-enabled")
    if scenario["execution"]["network"] is not False:
        raise ToolEnabledScenarioError("offline tool scenario requires network=false")
    profile = scenario.get("tool_profile")
    if not isinstance(profile, dict) or profile.get("profile") != PROFILE_ID:
        raise ToolEnabledScenarioError("offline tool profile binding missing/invalid")
    task = (
        "SYSTEM CONTEXT:\n" + scenario["stimulus"]["system_context"] +
        "\n\nUSER MESSAGE:\n" + scenario["stimulus"]["user_message"]
    )
    return {
        "schema_version": 1,
        "profile": PROFILE_ID,
        "task": task,
        "max_steps": profile["max_steps"],
        "initial_state": profile["initial_state"],
    }


def run_tool_enabled_scenario(
    scenario_path,
    model_cmd,
    *,
    output_dir,
    timeout,
    model_env,
    mgtest_commit=None,
):
    scenario_path = Path(scenario_path).resolve()
    raw = json.loads(scenario_path.read_text(encoding="utf-8"))
    spec = build_tool_spec(scenario_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    spec_path = out / "tool-spec.json"
    spec_path.write_text(json.dumps(spec, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    try:
        session = run_tool_session(
            spec_path,
            model_cmd,
            output_dir=out,
            timeout=timeout,
            model_env=model_env,
            mgtest_commit=mgtest_commit,
        )
    except ToolAgentError as exc:
        raise ToolEnabledScenarioError(str(exc)) from exc
    receipt = seal({
        "schema_version": 1,
        "receipt_type": "mgtest.ai.tool-enabled-scenario",
        "scenario": {
            "test_id": raw["test_id"],
            "test_version": raw["test_version"],
            "scenario_sha256": sha256(raw),
        },
        "profile": PROFILE_ID,
        "spec_sha256": sha256(spec),
        "session_receipt_sha256": session["receipt_sha256"],
        "mgtest_commit": session["mgtest_commit"],
        "status": "EXECUTED",
    })
    verify(receipt)
    (out / "scenario-receipt.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return receipt


def verify_tool_enabled_scenario_bundle(scenario_path, bundle_dir, expected_mgtest_commit=None):
    scenario_path = Path(scenario_path).resolve()
    bundle = Path(bundle_dir)
    raw = json.loads(scenario_path.read_text(encoding="utf-8"))
    spec = build_tool_spec(scenario_path)
    spec_path = bundle / "tool-spec.json"
    try:
        stored_spec = json.loads(spec_path.read_text(encoding="utf-8"))
        receipt = json.loads((bundle / "scenario-receipt.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ToolEnabledScenarioError("tool-enabled evidence bundle unreadable") from exc
    if stored_spec != spec:
        raise ToolEnabledScenarioError("scenario-derived tool spec mismatch")
    try:
        verify(receipt)
    except ValueError as exc:
        raise ToolEnabledScenarioError(str(exc)) from exc
    expected_keys = {
        "schema_version", "receipt_type", "scenario", "profile", "spec_sha256",
        "session_receipt_sha256", "mgtest_commit", "status", "receipt_sha256",
    }
    if not isinstance(receipt, dict) or set(receipt) != expected_keys:
        raise ToolEnabledScenarioError("scenario receipt fields invalid")
    expected_scenario = {
        "test_id": raw["test_id"],
        "test_version": raw["test_version"],
        "scenario_sha256": sha256(raw),
    }
    if receipt["schema_version"] != 1 or receipt["receipt_type"] != "mgtest.ai.tool-enabled-scenario":
        raise ToolEnabledScenarioError("scenario receipt type/version invalid")
    if receipt["scenario"] != expected_scenario or receipt["profile"] != PROFILE_ID:
        raise ToolEnabledScenarioError("scenario receipt binding mismatch")
    if receipt["spec_sha256"] != sha256(spec) or receipt["status"] != "EXECUTED":
        raise ToolEnabledScenarioError("scenario receipt spec/status mismatch")
    try:
        session_result = verify_tool_session_bundle(spec_path, bundle, expected_mgtest_commit)
    except ToolSessionEvidenceError as exc:
        raise ToolEnabledScenarioError(f"tool session evidence invalid: {exc}") from exc
    if receipt["session_receipt_sha256"] != session_result["session_receipt_sha256"]:
        raise ToolEnabledScenarioError("scenario receipt session binding mismatch")
    if receipt["mgtest_commit"] != session_result["mgtest_commit"]:
        raise ToolEnabledScenarioError("scenario receipt commit mismatch")
    return {
        "status": "VERIFIED",
        "test_id": raw["test_id"],
        "test_version": raw["test_version"],
        "tool_calls": session_result["tool_calls"],
        "session_receipt_sha256": session_result["session_receipt_sha256"],
        "scenario_receipt_sha256": receipt["receipt_sha256"],
        "limitations": session_result["limitations"],
    }
