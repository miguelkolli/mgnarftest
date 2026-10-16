# Provider Adapters v1

MGnarfTest uses provider-specific adapters behind provider-neutral runner protocols.

Included:

- `adapters/openai_adapter.py` — OpenAI Responses API
- `adapters/gemini_adapter.py` — Google Gemini `generateContent`
- `adapters/provider_tool_bridge.py` — closed translation between provider function calls and the deterministic MGnarfTest offline tool profile

Credentials are read only from explicitly passed provider environment variables and are never returned in adapter JSON or receipts. Scenario data cannot choose arbitrary provider URLs.

## Normal subject boundary

Normal `mgtest.ai.subject` requests still require:

```text
tools = none
network = false
```

Provider HTTPS transport is separate from model network capability.

## Receipt-backed tool evaluator support

OpenAI and Gemini evaluator adapters accept both normal and tool-evaluator requests. A tool evaluator receives only already-verified evidence data: subject binding, scenario/session receipt hashes and the verified tool trace. Missing or malformed receipt evidence fails closed before provider transport.

The evaluator does not execute tools.

## Offline-tool subject translation bridge

The adapters now also understand `mgtest.ai.offline-tool-subject` in mock-tested form.

The bridge exposes exactly three provider function names, mapped to the existing deterministic tools:

```text
mgtest_kv_get              -> kv.get
mgtest_kv_put              -> kv.put
mgtest_counter_increment   -> counter.increment
```

No provider-selected arbitrary tool name is accepted.

The adapter:

1. validates the closed MGnarfTest offline-tool request and allowlist;
2. reconstructs the frozen system/user task;
3. sends only the three declared deterministic functions;
4. accepts at most one function/tool call per provider response;
5. maps the provider call ID, name and arguments into the MGnarfTest subject-action protocol;
6. after MGnarfTest executes the tool, round-trips the receipt-backed result using the same call ID;
7. returns final provider text only when no function call is present.

OpenAI uses Responses API function tools plus `function_call` / `function_call_output` items. Gemini uses `functionDeclarations` plus `functionCall` / `functionResponse` parts.

Tool results are executed only by MGnarfTest's deterministic offline executor. Provider code never executes them.

## Fail-closed rules

The bridge rejects before execution/continuation when it sees:

- an undeclared provider function name
- more than one tool call in a single subject step
- malformed tool arguments
- malformed or mismatched offline-tool history
- missing receipt hashes in prior tool results
- a Gemini function call without an ID

Subject tool history includes the MGnarfTest tool receipt hash alongside the actual result returned to the provider.

## Live-readiness limitation

This subject bridge is **mock-tested protocol infrastructure, not credentialed live-provider evidence**.

Before live use, provider continuation state must be bound sufficiently for the selected provider/model family. In particular, provider-returned continuation/reasoning/context items that must be round-tripped must not be silently discarded. The repository trust root must also be enforceable before provider secrets are wired into a workflow.

Until those conditions are satisfied, live OpenAI/Gemini tool behavior remains `UNVERIFIED` and credentialed execution remains blocked.

## Immutable model identity

Adapters never infer an immutable model version from a mutable alias. `--immutable-version` may be supplied only when an immutable provider snapshot/build identity is actually known. Otherwise it remains `null` and strong-comparison policy records the limitation.

## Testing

`tools/test_provider_adapters.py` uses mocked provider transport and covers:

- normal subject/evaluator payloads
- receipt-backed tool evaluators
- OpenAI offline-tool subject call + result round-trip
- Gemini offline-tool subject call + result round-trip
- strict one-call-per-step behavior
- unknown-tool rejection
- Gemini call-ID requirement
- malformed history/receipt rejection before transport
- strict evaluator JSON handling

CI performs no paid/live model calls and requires no provider secret.
