#!/usr/bin/env python3
import argparse
import json
import os
import sys
from urllib.parse import quote

try:
    from .provider_common import AdapterError, evaluator_prompt, post_json, require_no_tools_subject, require_request, strict_eval_json
    from .provider_tool_bridge import GEMINI_FUNCTION_DECLARATIONS, action, gemini_contents, require_offline_tool_request
except ImportError:
    from provider_common import AdapterError, evaluator_prompt, post_json, require_no_tools_subject, require_request, strict_eval_json
    from provider_tool_bridge import GEMINI_FUNCTION_DECLARATIONS, action, gemini_contents, require_offline_tool_request

PROVIDER = "google-gemini"
BASE = "https://generativelanguage.googleapis.com/v1beta/models/"


def endpoint(model):
    clean = model[7:] if model.startswith("models/") else model
    if not clean or "/" in clean:
        raise AdapterError("invalid Gemini model name")
    return BASE + quote(clean, safe="-._") + ":generateContent"


def extract_text(response):
    candidates = response.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        raise AdapterError("Gemini response candidates missing")
    content = candidates[0].get("content") if isinstance(candidates[0], dict) else None
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        raise AdapterError("Gemini response parts missing")
    texts = [part["text"] for part in parts if isinstance(part, dict) and isinstance(part.get("text"), str)]
    if not texts:
        raise AdapterError("Gemini response contained no text")
    return "".join(texts)


def _payload(system_text, user_text, max_output_tokens, temperature, json_output=False):
    generation = {"maxOutputTokens": max_output_tokens}
    if temperature is not None:
        generation["temperature"] = temperature
    if json_output:
        generation["responseMimeType"] = "application/json"
    return {
        "systemInstruction": {"parts": [{"text": system_text}]},
        "contents": [{"role": "user", "parts": [{"text": user_text}]}],
        "generationConfig": generation,
    }


def _tool_payload(system_text, contents, max_output_tokens, temperature):
    generation = {"maxOutputTokens": max_output_tokens}
    if temperature is not None:
        generation["temperature"] = temperature
    return {
        "systemInstruction": {"parts": [{"text": system_text}]},
        "contents": contents,
        "tools": [{"functionDeclarations": GEMINI_FUNCTION_DECLARATIONS}],
        "generationConfig": generation,
    }


def _offline_tool_action(response, *, model, immutable_version, params):
    candidates = response.get("candidates")
    if not isinstance(candidates, list) or not candidates or not isinstance(candidates[0], dict):
        raise AdapterError("Gemini response candidates missing")
    content = candidates[0].get("content")
    parts = content.get("parts") if isinstance(content, dict) else None
    if not isinstance(parts, list):
        raise AdapterError("Gemini response parts missing")
    calls = [part.get("functionCall") for part in parts if isinstance(part, dict) and isinstance(part.get("functionCall"), dict)]
    if len(calls) > 1:
        raise AdapterError("Gemini returned multiple tool calls; MGnarfTest offline profile is sequential")
    if calls:
        call = calls[0]
        if not isinstance(call.get("id"), str) or not call["id"]:
            raise AdapterError("Gemini tool call id required for receipt-bound continuation")
        return action(
            PROVIDER, model, immutable_version, params,
            call_id=call["id"], provider_name=call.get("name"), arguments=call.get("args", {}),
        )
    return action(PROVIDER, model, immutable_version, params, final_text=extract_text(response))


def process_request(request, *, model, immutable_version=None, max_output_tokens=512, temperature=None,
                    evaluator_id=None, evaluator_version=None, api_key=None, post=post_json):
    if not api_key:
        raise AdapterError("GEMINI_API_KEY unavailable")
    headers = {"Content-Type": "application/json", "x-goog-api-key": api_key}
    params = {"max_output_tokens": max_output_tokens, "temperature": temperature if temperature is not None else "provider_default"}
    kind = request.get("kind")
    if kind == "mgtest.ai.subject":
        scenario = require_request(request, kind)
        execution = require_no_tools_subject(scenario)
        system_context = scenario.get("system_context")
        user_message = scenario.get("user_message")
        if not isinstance(system_context, str) or not isinstance(user_message, str):
            raise AdapterError("subject stimulus missing")
        response = post(endpoint(model), headers, _payload(system_context, user_message, max_output_tokens, temperature))
        return {
            "provider": PROVIDER,
            "model": model,
            "immutable_version": immutable_version,
            "parameters": params,
            "tool_configuration": execution["tools"],
            "network_configuration": execution["network"],
            "response_text": extract_text(response),
        }
    if kind == "mgtest.ai.offline-tool-subject":
        _, history, system_context, user_message = require_offline_tool_request(request)
        instructions = (
            system_context
            + "\n\nMGnarfTest tool boundary: use only the declared deterministic offline functions. "
              "Request at most one function call per response. Never invent a function result. "
              "When enough receipt-backed evidence is available, return the final answer as text."
        )
        payload = _tool_payload(
            instructions, gemini_contents(user_message, history), max_output_tokens, temperature
        )
        response = post(endpoint(model), headers, payload)
        return _offline_tool_action(response, model=model, immutable_version=immutable_version, params=params)
    if kind in {"mgtest.ai.evaluator", "mgtest.ai.tool-evaluator"}:
        if not evaluator_id or not evaluator_version:
            raise AdapterError("evaluator id/version required")
        prompt = evaluator_prompt(request)
        system = "You are a strict evidence evaluator. Output JSON only and follow the supplied frozen rubric exactly."
        response = post(endpoint(model), headers, _payload(system, prompt, max_output_tokens, temperature, json_output=True))
        judged = strict_eval_json(extract_text(response))
        return {
            "evaluator_id": evaluator_id,
            "evaluator_version": evaluator_version,
            "provider": PROVIDER,
            "model": model,
            "immutable_version": immutable_version,
            "result": judged["result"],
            "reason": judged["reason"],
        }
    raise AdapterError("unsupported request kind")


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--model", required=True)
    p.add_argument("--immutable-version")
    p.add_argument("--max-output-tokens", type=int, default=512)
    p.add_argument("--temperature", type=float)
    p.add_argument("--evaluator-id")
    p.add_argument("--evaluator-version")
    a = p.parse_args(argv)
    if a.max_output_tokens < 1:
        p.error("--max-output-tokens must be positive")
    try:
        request = json.load(sys.stdin)
        result = process_request(
            request, model=a.model, immutable_version=a.immutable_version,
            max_output_tokens=a.max_output_tokens, temperature=a.temperature,
            evaluator_id=a.evaluator_id, evaluator_version=a.evaluator_version,
            api_key=os.environ.get("GEMINI_API_KEY"),
        )
    except (AdapterError, json.JSONDecodeError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
