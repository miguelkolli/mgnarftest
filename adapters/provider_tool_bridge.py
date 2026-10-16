import json

try:
    from .provider_common import AdapterError
except ImportError:
    from provider_common import AdapterError

TASK_PREFIX = "SYSTEM CONTEXT:\n"
TASK_SPLIT = "\n\nUSER MESSAGE:\n"

INTERNAL_TO_PROVIDER = {
    "kv.get": "mgtest_kv_get",
    "kv.put": "mgtest_kv_put",
    "counter.increment": "mgtest_counter_increment",
}
PROVIDER_TO_INTERNAL = {value: key for key, value in INTERNAL_TO_PROVIDER.items()}

OPENAI_TOOLS = [
    {
        "type": "function",
        "name": "mgtest_kv_get",
        "description": "Read one value from the deterministic MGnarfTest offline key-value fixture.",
        "parameters": {
            "type": "object",
            "properties": {"key": {"type": "string"}},
            "required": ["key"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "mgtest_kv_put",
        "description": "Store one string value in the deterministic MGnarfTest offline key-value fixture.",
        "parameters": {
            "type": "object",
            "properties": {"key": {"type": "string"}, "value": {"type": "string"}},
            "required": ["key", "value"],
            "additionalProperties": False,
        },
        "strict": True,
    },
    {
        "type": "function",
        "name": "mgtest_counter_increment",
        "description": "Increment one named counter in the deterministic MGnarfTest offline fixture.",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
            "additionalProperties": False,
        },
        "strict": True,
    },
]

GEMINI_FUNCTION_DECLARATIONS = [
    {
        "name": "mgtest_kv_get",
        "description": "Read one value from the deterministic MGnarfTest offline key-value fixture.",
        "parameters": {
            "type": "object",
            "properties": {"key": {"type": "string"}},
            "required": ["key"],
        },
    },
    {
        "name": "mgtest_kv_put",
        "description": "Store one string value in the deterministic MGnarfTest offline key-value fixture.",
        "parameters": {
            "type": "object",
            "properties": {"key": {"type": "string"}, "value": {"type": "string"}},
            "required": ["key", "value"],
        },
    },
    {
        "name": "mgtest_counter_increment",
        "description": "Increment one named counter in the deterministic MGnarfTest offline fixture.",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
            "required": ["name"],
        },
    },
]


def split_task(task):
    if not isinstance(task, str) or not task.startswith(TASK_PREFIX) or TASK_SPLIT not in task:
        raise AdapterError("offline tool task format invalid")
    body = task[len(TASK_PREFIX):]
    system_context, user_message = body.split(TASK_SPLIT, 1)
    if not system_context or not user_message:
        raise AdapterError("offline tool task system/user text required")
    return system_context, user_message


def require_offline_tool_request(request):
    if not isinstance(request, dict) or request.get("protocol_version") != 1 or request.get("kind") != "mgtest.ai.offline-tool-subject":
        raise AdapterError("unsupported offline tool subject request")
    session = request.get("session")
    history = request.get("history")
    if not isinstance(session, dict) or session.get("profile") != "offline-deterministic-tools-v1":
        raise AdapterError("offline tool session profile invalid")
    if session.get("allowed_tools") != ["kv.get", "kv.put", "counter.increment"]:
        raise AdapterError("offline tool allowlist mismatch")
    if not isinstance(history, list):
        raise AdapterError("offline tool history must be list")
    system_context, user_message = split_task(session.get("task"))
    return session, history, system_context, user_message


def _history_item(item, index):
    expected = {"step", "action", "call_id", "tool", "arguments", "result", "tool_receipt_sha256"}
    if not isinstance(item, dict) or set(item) != expected or item.get("action") != "tool_call":
        raise AdapterError(f"offline tool history[{index}] invalid")
    if not isinstance(item.get("step"), int) or item["step"] < 1:
        raise AdapterError(f"offline tool history[{index}].step invalid")
    for key in ("call_id", "tool", "tool_receipt_sha256"):
        if not isinstance(item.get(key), str) or not item[key]:
            raise AdapterError(f"offline tool history[{index}].{key} invalid")
    if item["tool"] not in INTERNAL_TO_PROVIDER:
        raise AdapterError(f"offline tool history[{index}].tool not allowed")
    if not isinstance(item.get("arguments"), dict) or not isinstance(item.get("result"), dict):
        raise AdapterError(f"offline tool history[{index}] arguments/result invalid")
    if len(item["tool_receipt_sha256"]) != 64:
        raise AdapterError(f"offline tool history[{index}] receipt hash invalid")
    return item


def openai_input(user_message, history):
    items = [{"role": "user", "content": user_message}]
    for index, raw in enumerate(history):
        item = _history_item(raw, index)
        name = INTERNAL_TO_PROVIDER[item["tool"]]
        items.append({
            "type": "function_call",
            "call_id": item["call_id"],
            "name": name,
            "arguments": json.dumps(item["arguments"], sort_keys=True, separators=(",", ":")),
        })
        items.append({
            "type": "function_call_output",
            "call_id": item["call_id"],
            "output": json.dumps({
                "result": item["result"],
                "mgtest_tool_receipt_sha256": item["tool_receipt_sha256"],
            }, sort_keys=True, separators=(",", ":")),
        })
    return items


def gemini_contents(user_message, history):
    contents = [{"role": "user", "parts": [{"text": user_message}]}]
    for index, raw in enumerate(history):
        item = _history_item(raw, index)
        name = INTERNAL_TO_PROVIDER[item["tool"]]
        contents.append({
            "role": "model",
            "parts": [{"functionCall": {"id": item["call_id"], "name": name, "args": item["arguments"]}}],
        })
        contents.append({
            "role": "user",
            "parts": [{"functionResponse": {
                "id": item["call_id"],
                "name": name,
                "response": {
                    "result": item["result"],
                    "mgtest_tool_receipt_sha256": item["tool_receipt_sha256"],
                },
            }}],
        })
    return contents


def _arguments(raw, where):
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise AdapterError(f"{where} arguments invalid JSON") from exc
    else:
        value = raw
    if not isinstance(value, dict):
        raise AdapterError(f"{where} arguments must be object")
    return value


def action(provider, model, immutable_version, parameters, *, call_id=None, provider_name=None, arguments=None, final_text=None):
    common = {
        "provider": provider,
        "model": model,
        "immutable_version": immutable_version,
        "parameters": parameters,
    }
    if provider_name is not None:
        internal = PROVIDER_TO_INTERNAL.get(provider_name)
        if internal is None:
            raise AdapterError("provider requested undeclared MGnarfTest tool")
        if not isinstance(call_id, str) or not call_id:
            raise AdapterError("provider tool call_id required")
        return {
            **common,
            "action": "tool_call",
            "call_id": call_id,
            "tool": internal,
            "arguments": _arguments(arguments, "provider tool call"),
        }
    if not isinstance(final_text, str):
        raise AdapterError("provider final text missing")
    return {**common, "action": "final", "response_text": final_text}
