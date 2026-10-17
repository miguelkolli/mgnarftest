#!/usr/bin/env python3
import copy
import json
from pathlib import Path

try:
    from .ai_runner_protocol import canonical, seal, sha256, verify
except ImportError:
    from ai_runner_protocol import canonical, seal, sha256, verify

PROFILE_ID = "offline-deterministic-tools-v1"
MAX_CALLS = 32


class ToolProfileError(ValueError):
    pass


def _exact(obj, keys, where):
    if not isinstance(obj, dict) or set(obj) != set(keys):
        raise ToolProfileError(f"{where}: fields invalid")


def _text(value, where):
    if not isinstance(value, str) or not value:
        raise ToolProfileError(f"{where}: non-empty string required")
    return value


def _state(value):
    if value is None:
        return {"kv": {}, "counters": {}}
    if not isinstance(value, dict):
        raise ToolProfileError("initial_state: object required")
    _exact(value, {"kv", "counters"}, "initial_state")
    if not isinstance(value["kv"], dict) or not isinstance(value["counters"], dict):
        raise ToolProfileError("initial_state: kv/counters objects required")
    for key, item in value["kv"].items():
        _text(key, "initial_state.kv key")
        if not isinstance(item, str):
            raise ToolProfileError("initial_state.kv values must be strings")
    for key, item in value["counters"].items():
        _text(key, "initial_state.counters key")
        if not isinstance(item, int) or isinstance(item, bool) or item < 0:
            raise ToolProfileError("initial_state.counters values must be non-negative integers")
    return copy.deepcopy(value)


def validate_plan(plan):
    if not isinstance(plan, dict):
        raise ToolProfileError("plan: object required")
    _exact(plan, {"schema_version", "profile", "calls"}, "plan")
    if plan["schema_version"] != 1 or plan["profile"] != PROFILE_ID:
        raise ToolProfileError("plan: schema/profile invalid")
    calls = plan["calls"]
    if not isinstance(calls, list) or not calls:
        raise ToolProfileError("plan.calls: non-empty list required")
    if len(calls) > MAX_CALLS:
        raise ToolProfileError(f"plan.calls: maximum {MAX_CALLS}")
    ids = set()
    normalized = []
    for index, call in enumerate(calls):
        where = f"plan.calls[{index}]"
        _exact(call, {"call_id", "tool", "arguments"}, where)
        call_id = _text(call["call_id"], f"{where}.call_id")
        if call_id in ids:
            raise ToolProfileError("plan.calls: duplicate call_id")
        ids.add(call_id)
        tool = _text(call["tool"], f"{where}.tool")
        args = call["arguments"]
        if not isinstance(args, dict):
            raise ToolProfileError(f"{where}.arguments: object required")
        if tool == "kv.get":
            _exact(args, {"key"}, f"{where}.arguments")
            _text(args["key"], f"{where}.arguments.key")
        elif tool == "kv.put":
            _exact(args, {"key", "value"}, f"{where}.arguments")
            _text(args["key"], f"{where}.arguments.key")
            if not isinstance(args["value"], str):
                raise ToolProfileError(f"{where}.arguments.value: string required")
        elif tool == "counter.increment":
            _exact(args, {"name"}, f"{where}.arguments")
            _text(args["name"], f"{where}.arguments.name")
        else:
            raise ToolProfileError(f"{where}.tool: unsupported tool")
        normalized.append(copy.deepcopy(call))
    return {"schema_version": 1, "profile": PROFILE_ID, "calls": normalized}


def _execute_call(state, call):
    tool, args = call["tool"], call["arguments"]
    if tool == "kv.get":
        key = args["key"]
        return {"found": key in state["kv"], "value": state["kv"].get(key)}
    if tool == "kv.put":
        state["kv"][args["key"]] = args["value"]
        return {"stored": True}
    if tool == "counter.increment":
        name = args["name"]
        state["counters"][name] = state["counters"].get(name, 0) + 1
        return {"value": state["counters"][name]}
    raise ToolProfileError("unsupported tool")


def execute_plan(plan, initial_state=None):
    frozen = validate_plan(plan)
    state = _state(initial_state)
    initial = copy.deepcopy(state)
    executions = []
    for call in frozen["calls"]:
        before = sha256(state)
        result = _execute_call(state, call)
        executions.append({
            "call_id": call["call_id"],
            "tool": call["tool"],
            "arguments_sha256": sha256(call["arguments"]),
            "before_state_sha256": before,
            "result": result,
            "result_sha256": sha256(result),
            "after_state_sha256": sha256(state),
        })
    receipt = {
        "schema_version": 1,
        "receipt_type": "mgtest.ai.offline-tool-execution",
        "profile": PROFILE_ID,
        "network": False,
        "shell": False,
        "plan_sha256": sha256(frozen),
        "initial_state_sha256": sha256(initial),
        "executions": executions,
        "final_state_sha256": sha256(state),
        "call_count": len(executions),
        "status": "EXECUTED",
    }
    return state, seal(receipt)


def verify_execution(plan, receipt, initial_state=None):
    try:
        verify(receipt)
    except ValueError as exc:
        raise ToolProfileError(str(exc)) from exc
    expected_state, expected = execute_plan(plan, initial_state)
    if canonical(receipt) != canonical(expected):
        raise ToolProfileError("tool execution receipt semantic mismatch")
    return {"status": "VERIFIED", "final_state": expected_state, "receipt_sha256": receipt["receipt_sha256"]}


def main(argv=None):
    import argparse
    p = argparse.ArgumentParser(description="Execute a deterministic offline MGnarfTest tool plan.")
    p.add_argument("--plan", required=True)
    p.add_argument("--initial-state")
    p.add_argument("--output")
    args = p.parse_args(argv)
    try:
        plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        initial = None if args.initial_state is None else json.loads(Path(args.initial_state).read_text(encoding="utf-8"))
        final_state, receipt = execute_plan(plan, initial)
        verify_execution(plan, receipt, initial)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ToolProfileError) as exc:
        print(f"BLOCKED: {exc}")
        return 1
    output = {"final_state": final_state, "receipt": receipt}
    text = json.dumps(output, sort_keys=True, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
