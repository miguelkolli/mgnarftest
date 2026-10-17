import hashlib
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

OPENAI_CONTEXT_KIND = "openai.response.output.v1"
GEMINI_CONTEXT_KIND = "gemini.candidate.content.v1"

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


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _context_sha(provider, kind, payload):
    return hashlib.sha256(
        _canonical({"provider": provider, "kind": kind, "payload": payload})
    ).hexdigest()


def make_provider_context(provider, kind, payload):
    if not isinstance(provider, str) or not provider:
        raise AdapterError("provider continuation provider invalid")
    if not isinstance(kind, str) or not kind:
        raise AdapterError("provider continuation kind invalid")
    if not isinstance(payload, (dict, list)):
        raise AdapterError("provider continuation payload must be object/list")
    value = {
        "provider": provider,
        "kind": kind,
        "payload": json.loads(json.dumps(payload)),
    }
    value["sha256"] = _context_sha(provider, kind, value["payload"])
    return value


def verify_provider_context(value, *, provider=None, kind=None):
    if not isinstance(value, dict) or set(value) != {"provider", "kind", "payload", "sha256"}:
        raise AdapterError("provider continuation context fields invalid")
    if not isinstance(value["provider"], str) or not value["provider"]:
        raise AdapterError("provider continuation provider invalid")
    if not isinstance(value["kind"], str) or not value["kind"]:
        raise AdapterError("provider continuation kind invalid")
    if not isinstance(value["payload"], (dict, list)):
        raise AdapterError("provider continuation payload invalid")
    if not isinstance(value["sha256"], str) or len(value["sha256"]) != 64:
        raise AdapterError("provider continuation hash invalid")
    expected = _context_sha(value["provider"], value["kind"], value["payload"])
    if value["sha256"] != expected:
        raise AdapterError("provider continuation hash mismatch")
    if provider is not None and value["provider"] != provider:
        raise AdapterError("provider continuation provider mismatch")
    if kind is not None and value["kind"] != kind:
        raise AdapterError("provider continuation kind mismatch")
    return json.loads(json.dumps(value))


def split_task(task):
    if not isinstance(task, str) or not task.startswith(TASK_PREFIX) or TASK_SPLIT not in task:
        raise AdapterError("offline tool task format invalid")
    body = task[len(TASK_PREFIX):]
    system_context, user_message = body.split(TASK_SPLIT, 1)
    if not system_context or not user_message:
        raise AdapterError("offline tool task system/user text required")
    return system_context, user_message


def require_offline_tool_request(request):
    if (
        not isinstance(request, dict)
        or request.get("protocol_version") != 1
        or request.get("kind") != "mgtest.ai.offline-tool-subject"
    ):
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
    base = {"step", "action", "call_id", "tool", "arguments", "result", "tool_receipt_sha256"}
    if not isinstance(item, dict):
        raise AdapterError(f"offline tool history[{index}] invalid")
    keys = set(item)
    if keys != base and keys != base | {"provider_context"}:
        raise AdapterError(f"offline tool history[{index}] invalid")
    if item.get("action") != "tool_call":
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
    if "provider_context" in item:
        verify_provider_context(item["provider_context"])
    return item


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


def _openai_context_items(item, index):
    if "provider_context" not in item:
        raise AdapterError(
            f"offline tool history[{index}] OpenAI continuation context required"
        )
    context = verify_provider_context(
        item["provider_context"], provider="openai", kind=OPENAI_CONTEXT_KIND
    )
    payload = context["payload"]
    if not isinstance(payload, dict) or set(payload) != {"response_id", "output"}:
        raise AdapterError("OpenAI continuation payload shape invalid")
    response_id = payload["response_id"]
    if response_id is not None and (
        not isinstance(response_id, str) or not response_id
    ):
        raise AdapterError("OpenAI continuation response_id invalid")
    output = payload["output"]
    if not isinstance(output, list) or not output:
        raise AdapterError("OpenAI continuation output invalid")
    calls = [
        value
        for value in output
        if isinstance(value, dict) and value.get("type") == "function_call"
    ]
    if len(calls) != 1:
        raise AdapterError("OpenAI continuation must bind exactly one function call")
    call = calls[0]
    if (
        call.get("call_id") != item["call_id"]
        or call.get("name") != INTERNAL_TO_PROVIDER[item["tool"]]
    ):
        raise AdapterError("OpenAI continuation function binding mismatch")
    if (
        _arguments(call.get("arguments"), "OpenAI continuation function")
        != item["arguments"]
    ):
        raise AdapterError("OpenAI continuation arguments mismatch")
    return json.loads(json.dumps(output))


def openai_input(user_message, history):
    items = [{"role": "user", "content": user_message}]
    for index, raw in enumerate(history):
        item = _history_item(raw, index)
        items.extend(_openai_context_items(item, index))
        items.append(
            {
                "type": "function_call_output",
                "call_id": item["call_id"],
                "output": json.dumps(
                    {
                        "result": item["result"],
                        "mgtest_tool_receipt_sha256": item[
                            "tool_receipt_sha256"
                        ],
                    },
                    sort_keys=True,
                    separators=(",", ":"),
                ),
            }
        )
    return items


def _gemini_context_content(item, index):
    if "provider_context" not in item:
        raise AdapterError(
            f"offline tool history[{index}] Gemini continuation context required"
        )
    context = verify_provider_context(
        item["provider_context"],
        provider="google-gemini",
        kind=GEMINI_CONTEXT_KIND,
    )
    payload = context["payload"]
    if not isinstance(payload, dict) or set(payload) != {"content"}:
        raise AdapterError("Gemini continuation payload shape invalid")
    content = payload["content"]
    if (
        not isinstance(content, dict)
        or content.get("role") != "model"
        or not isinstance(content.get("parts"), list)
    ):
        raise AdapterError("Gemini continuation content invalid")
    calls = [
        part.get("functionCall")
        for part in content["parts"]
        if isinstance(part, dict)
        and isinstance(part.get("functionCall"), dict)
    ]
    if len(calls) != 1:
        raise AdapterError("Gemini continuation must bind exactly one function call")
    call = calls[0]
    if (
        call.get("id") != item["call_id"]
        or call.get("name") != INTERNAL_TO_PROVIDER[item["tool"]]
    ):
        raise AdapterError("Gemini continuation function binding mismatch")
    if (
        _arguments(call.get("args", {}), "Gemini continuation function")
        != item["arguments"]
    ):
        raise AdapterError("Gemini continuation arguments mismatch")
    return json.loads(json.dumps(content))


def gemini_contents(user_message, history):
    contents = [{"role": "user", "parts": [{"text": user_message}]}]
    for index, raw in enumerate(history):
        item = _history_item(raw, index)
        name = INTERNAL_TO_PROVIDER[item["tool"]]
        contents.append(_gemini_context_content(item, index))
        contents.append(
            {
                "role": "user",
                "parts": [
                    {
                        "functionResponse": {
                            "id": item["call_id"],
                            "name": name,
                            "response": {
                                "result": item["result"],
                                "mgtest_tool_receipt_sha256": item[
                                    "tool_receipt_sha256"
                                ],
                            },
                        }
                    }
                ],
            }
        )
    return contents


def action(
    provider,
    model,
    immutable_version,
    parameters,
    *,
    call_id=None,
    provider_name=None,
    arguments=None,
    final_text=None,
    provider_context=None,
):
    common = {
        "provider": provider,
        "model": model,
        "immutable_version": immutable_version,
        "parameters": parameters,
    }
    if provider_context is not None:
        common["provider_context"] = verify_provider_context(
            provider_context, provider=provider
        )
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
