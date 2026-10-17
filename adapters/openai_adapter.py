#!/usr/bin/env python3
import argparse
import json
import os
import sys

try:
    from .provider_common import AdapterError, evaluator_prompt, post_json, require_no_tools_subject, require_request, strict_eval_json
    from .provider_tool_bridge import (
        OPENAI_CONTEXT_KIND,
        OPENAI_TOOLS,
        action,
        make_provider_context,
        openai_input,
        require_offline_tool_request,
    )
except ImportError:
    from provider_common import AdapterError, evaluator_prompt, post_json, require_no_tools_subject, require_request, strict_eval_json
    from provider_tool_bridge import (
        OPENAI_CONTEXT_KIND,
        OPENAI_TOOLS,
        action,
        make_provider_context,
        openai_input,
        require_offline_tool_request,
    )

ENDPOINT = "https://api.openai.com/v1/responses"
PROVIDER = "openai"


def extract_text(response):
    output = response.get("output")
    if not isinstance(output, list):
        raise AdapterError("OpenAI response output missing")
    texts = []
    for item in output:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        content = item.get("content")
        if not isinstance(content, list):
            continue
        for part in content:
            if (
                isinstance(part, dict)
                and part.get("type") == "output_text"
                and isinstance(part.get("text"), str)
            ):
                texts.append(part["text"])
    if not texts:
        raise AdapterError("OpenAI response contained no output_text")
    return "".join(texts)


def _payload(model, instructions, input_value, max_output_tokens, temperature, tools=None):
    payload = {
        "model": model,
        "instructions": instructions,
        "input": input_value,
        "max_output_tokens": max_output_tokens,
    }
    if temperature is not None:
        payload["temperature"] = temperature
    if tools is not None:
        payload["tools"] = tools
        payload["parallel_tool_calls"] = False
    return payload


def _offline_tool_action(response, *, model, immutable_version, params):
    output = response.get("output")
    if not isinstance(output, list):
        raise AdapterError("OpenAI response output missing")
    calls = [
        item
        for item in output
        if isinstance(item, dict) and item.get("type") == "function_call"
    ]
    if len(calls) > 1:
        raise AdapterError(
            "OpenAI returned multiple tool calls; MGnarfTest offline profile is sequential"
        )
    actual_model = (
        response.get("model")
        if isinstance(response.get("model"), str)
        else model
    )
    context = make_provider_context(
        PROVIDER,
        OPENAI_CONTEXT_KIND,
        {"response_id": response.get("id"), "output": output},
    )
    if calls:
        call = calls[0]
        return action(
            PROVIDER,
            actual_model,
            immutable_version,
            params,
            call_id=call.get("call_id"),
            provider_name=call.get("name"),
            arguments=call.get("arguments"),
            provider_context=context,
        )
    return action(
        PROVIDER,
        actual_model,
        immutable_version,
        params,
        final_text=extract_text(response),
        provider_context=context,
    )


def process_request(
    request,
    *,
    model,
    immutable_version=None,
    max_output_tokens=512,
    temperature=None,
    evaluator_id=None,
    evaluator_version=None,
    api_key=None,
    post=post_json,
):
    if not api_key:
        raise AdapterError("OPENAI_API_KEY unavailable")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    params = {
        "max_output_tokens": max_output_tokens,
        "temperature": temperature if temperature is not None else "provider_default",
    }
    kind = request.get("kind")
    if kind == "mgtest.ai.subject":
        scenario = require_request(request, kind)
        execution = require_no_tools_subject(scenario)
        system_context = scenario.get("system_context")
        user_message = scenario.get("user_message")
        if not isinstance(system_context, str) or not isinstance(user_message, str):
            raise AdapterError("subject stimulus missing")
        response = post(
            ENDPOINT,
            headers,
            _payload(
                model,
                system_context,
                user_message,
                max_output_tokens,
                temperature,
            ),
        )
        actual_model = (
            response.get("model")
            if isinstance(response.get("model"), str)
            else model
        )
        return {
            "provider": PROVIDER,
            "model": actual_model,
            "immutable_version": immutable_version,
            "parameters": params,
            "tool_configuration": execution["tools"],
            "network_configuration": execution["network"],
            "response_text": extract_text(response),
        }
    if kind == "mgtest.ai.offline-tool-subject":
        _, history, system_context, user_message = require_offline_tool_request(
            request
        )
        instructions = (
            system_context
            + "\n\nMGnarfTest tool boundary: use only the declared deterministic offline tools. "
            "Request at most one tool call per response. Never invent a tool result. "
            "When enough receipt-backed evidence is available, return the final answer as text."
        )
        payload = _payload(
            model,
            instructions,
            openai_input(user_message, history),
            max_output_tokens,
            temperature,
            tools=OPENAI_TOOLS,
        )
        response = post(ENDPOINT, headers, payload)
        return _offline_tool_action(
            response,
            model=model,
            immutable_version=immutable_version,
            params=params,
        )
    if kind in {"mgtest.ai.evaluator", "mgtest.ai.tool-evaluator"}:
        if not evaluator_id or not evaluator_version:
            raise AdapterError("evaluator id/version required")
        prompt = evaluator_prompt(request)
        instructions = (
            "You are a strict evidence evaluator. Output JSON only and follow the supplied frozen rubric exactly."
        )
        response = post(
            ENDPOINT,
            headers,
            _payload(
                model,
                instructions,
                prompt,
                max_output_tokens,
                temperature,
            ),
        )
        actual_model = (
            response.get("model")
            if isinstance(response.get("model"), str)
            else model
        )
        judged = strict_eval_json(extract_text(response))
        return {
            "evaluator_id": evaluator_id,
            "evaluator_version": evaluator_version,
            "provider": PROVIDER,
            "model": actual_model,
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
    if a.max_output_tokens < 16:
        p.error("--max-output-tokens must be >= 16")
    try:
        request = json.load(sys.stdin)
        result = process_request(
            request,
            model=a.model,
            immutable_version=a.immutable_version,
            max_output_tokens=a.max_output_tokens,
            temperature=a.temperature,
            evaluator_id=a.evaluator_id,
            evaluator_version=a.evaluator_version,
            api_key=os.environ.get("OPENAI_API_KEY"),
        )
    except (AdapterError, json.JSONDecodeError) as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
