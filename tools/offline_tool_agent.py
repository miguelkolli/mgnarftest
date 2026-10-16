#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

try:
    from .ai_runner_protocol import command_binding, invoke, resolve_commit, seal, sha256, verify
    from .offline_tool_profile import PROFILE_ID, ToolProfileError, execute_plan, verify_execution
except ImportError:
    from ai_runner_protocol import command_binding, invoke, resolve_commit, seal, sha256, verify
    from offline_tool_profile import PROFILE_ID, ToolProfileError, execute_plan, verify_execution

HEX40 = re.compile(r"^[0-9a-f]{40}$")
MAX_SESSION_STEPS = 16


class ToolAgentError(ValueError):
    pass


def _exact(value, keys, where):
    if not isinstance(value, dict) or set(value) != set(keys):
        raise ToolAgentError(f"{where}: fields invalid")


def _text(value, where):
    if not isinstance(value, str) or not value:
        raise ToolAgentError(f"{where}: non-empty string required")
    return value


def validate_spec(spec):
    _exact(spec, {"schema_version", "profile", "task", "max_steps", "initial_state"}, "spec")
    if spec["schema_version"] != 1 or spec["profile"] != PROFILE_ID:
        raise ToolAgentError("spec: schema/profile invalid")
    _text(spec["task"], "spec.task")
    max_steps = spec["max_steps"]
    if not isinstance(max_steps, int) or isinstance(max_steps, bool) or not 1 <= max_steps <= MAX_SESSION_STEPS:
        raise ToolAgentError(f"spec.max_steps must be 1..{MAX_SESSION_STEPS}")
    try:
        # Validate initial state without executing a user plan.
        execute_plan({"schema_version": 1, "profile": PROFILE_ID, "calls": [{"call_id": "__validate__", "tool": "kv.get", "arguments": {"key": "__validate__"}}]}, spec["initial_state"])
    except ToolProfileError as exc:
        raise ToolAgentError(f"spec.initial_state invalid: {exc}") from exc
    return json.loads(json.dumps(spec))


def _identity(value):
    return {
        "provider": value["provider"],
        "model": value["model"],
        "immutable_version": value["immutable_version"],
        "parameters_sha256": sha256(value["parameters"]),
    }


def parse_action(value):
    if not isinstance(value, dict):
        raise ToolAgentError("adapter response must be object")
    action = value.get("action")
    common = {"provider", "model", "immutable_version", "parameters", "action"}
    if action == "tool_call":
        _exact(value, common | {"call_id", "tool", "arguments"}, "adapter response")
    elif action == "final":
        _exact(value, common | {"response_text"}, "adapter response")
    else:
        raise ToolAgentError("adapter response action invalid")
    _text(value["provider"], "adapter.provider")
    _text(value["model"], "adapter.model")
    if value["immutable_version"] is not None:
        _text(value["immutable_version"], "adapter.immutable_version")
    if not isinstance(value["parameters"], dict):
        raise ToolAgentError("adapter.parameters must be object")
    if action == "tool_call":
        _text(value["call_id"], "adapter.call_id")
        _text(value["tool"], "adapter.tool")
        if not isinstance(value["arguments"], dict):
            raise ToolAgentError("adapter.arguments must be object")
    else:
        if not isinstance(value["response_text"], str):
            raise ToolAgentError("adapter.response_text must be string")
    return json.loads(json.dumps(value))


def _request(spec, spec_hash, history, step):
    return {
        "protocol_version": 1,
        "kind": "mgtest.ai.offline-tool-subject",
        "step": step,
        "session": {
            "profile": PROFILE_ID,
            "spec_sha256": spec_hash,
            "task": spec["task"],
            "max_steps": spec["max_steps"],
            "allowed_tools": ["kv.get", "kv.put", "counter.increment"],
        },
        "history": history,
    }


def run_tool_session(spec_path, model_cmd, *, output_dir, timeout, model_env, mgtest_commit=None):
    spec_path = Path(spec_path).resolve()
    try:
        raw = json.loads(spec_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ToolAgentError("spec unreadable/invalid JSON") from exc
    spec = validate_spec(raw)
    spec_hash = sha256(spec)
    root = Path(__file__).resolve().parents[1]
    commit = resolve_commit(mgtest_commit, root)
    if commit is not None and not HEX40.fullmatch(commit):
        raise ToolAgentError("MGnarfTest commit invalid")
    adapter = command_binding(model_cmd, root)
    if not adapter["content_bound"]:
        raise ToolAgentError("MODEL_ADAPTER_UNBOUND")

    state = json.loads(json.dumps(spec["initial_state"]))
    history = []
    transcript_steps = []
    tool_receipts = []
    seen_call_ids = set()
    subject_binding = None
    limitations = set()
    final_response = None
    out = Path(output_dir)

    for step in range(1, spec["max_steps"] + 1):
        if command_binding(model_cmd, root) != adapter:
            raise ToolAgentError("MODEL_ADAPTER_DRIFT")
        value, meta = invoke(model_cmd, _request(spec, spec_hash, history, step), timeout, model_env)
        if command_binding(model_cmd, root) != adapter:
            raise ToolAgentError("MODEL_ADAPTER_DRIFT")
        if value is None:
            raise ToolAgentError(f"MODEL_{meta['kind']}")
        action = parse_action(value)
        identity = _identity(action)
        if subject_binding is None:
            subject_binding = identity
            if identity["immutable_version"] is None:
                limitations.add("SUBJECT_MODEL_VERSION_MUTABLE_OR_UNAVAILABLE")
        elif identity != subject_binding:
            raise ToolAgentError("SUBJECT_IDENTITY_OR_PARAMETER_DRIFT")

        if action["action"] == "final":
            final_response = action["response_text"]
            transcript_steps.append({"step": step, "action": action, "tool_result": None, "tool_receipt_sha256": None})
            history.append({"step": step, "action": "final", "response_text": final_response})
            break

        call_id = action["call_id"]
        if call_id in seen_call_ids:
            raise ToolAgentError("DUPLICATE_TOOL_CALL_ID")
        seen_call_ids.add(call_id)
        plan = {
            "schema_version": 1,
            "profile": PROFILE_ID,
            "calls": [{"call_id": call_id, "tool": action["tool"], "arguments": action["arguments"]}],
        }
        before_state = json.loads(json.dumps(state))
        try:
            state, tool_receipt = execute_plan(plan, state)
            verify_execution(plan, tool_receipt, before_state)
        except ToolProfileError as exc:
            raise ToolAgentError(f"TOOL_CALL_BLOCKED: {exc}") from exc
        result = tool_receipt["executions"][0]["result"]
        tool_path = out / "tool-receipts" / f"call-{len(tool_receipts)+1:04d}.json"
        tool_path.parent.mkdir(parents=True, exist_ok=True)
        tool_path.write_text(json.dumps(tool_receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        tool_receipts.append(tool_receipt["receipt_sha256"])
        transcript_steps.append({"step": step, "action": action, "tool_result": result, "tool_receipt_sha256": tool_receipt["receipt_sha256"]})
        history.append({
            "step": step,
            "action": "tool_call",
            "call_id": call_id,
            "tool": action["tool"],
            "arguments": action["arguments"],
            "result": result,
            "tool_receipt_sha256": tool_receipt["receipt_sha256"],
        })

    if final_response is None:
        raise ToolAgentError("MAX_STEPS_EXHAUSTED_WITHOUT_FINAL")

    transcript = {
        "schema_version": 1,
        "profile": PROFILE_ID,
        "spec_sha256": spec_hash,
        "steps": transcript_steps,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "transcript.json").write_text(json.dumps(transcript, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    receipt = seal({
        "schema_version": 1,
        "receipt_type": "mgtest.ai.offline-tool-session",
        "profile": PROFILE_ID,
        "mgtest_commit": commit,
        "runner_sha256": sha256(Path(__file__).read_bytes()),
        "adapter_binding": adapter,
        "spec_sha256": spec_hash,
        "subject_binding": subject_binding,
        "transcript_sha256": sha256(transcript),
        "tool_receipts": tool_receipts,
        "final_state_sha256": sha256(state),
        "final_response_sha256": sha256(final_response.encode()),
        "limitations": sorted(limitations),
        "status": "COMPLETED",
    })
    verify(receipt)
    (out / "session.json").write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return receipt


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description="Run a subject adapter against the deterministic offline tool profile.")
    p.add_argument("--spec", required=True)
    p.add_argument("--model-adapter-json", required=True)
    p.add_argument("--output-dir", required=True)
    p.add_argument("--adapter-timeout", type=int, default=120)
    p.add_argument("--model-env", action="append", default=[])
    p.add_argument("--mgtest-commit")
    args = p.parse_args(argv)
    try:
        model_cmd = json.loads(args.model_adapter_json)
        if not isinstance(model_cmd, list) or not model_cmd or not all(isinstance(x, str) and x for x in model_cmd):
            raise ToolAgentError("--model-adapter-json must be non-empty JSON string array")
        receipt = run_tool_session(
            args.spec, model_cmd, output_dir=args.output_dir, timeout=args.adapter_timeout,
            model_env=args.model_env, mgtest_commit=args.mgtest_commit,
        )
    except (json.JSONDecodeError, ToolAgentError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"status": receipt["status"], "receipt_sha256": receipt["receipt_sha256"], "limitations": receipt["limitations"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
