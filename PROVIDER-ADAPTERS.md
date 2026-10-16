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

The adapters understand `mgtest.ai.offline-tool-subject` in mock-tested form.

The bridge exposes exactly three provider function names:

```text
mgtest_kv_get              -> kv.get
mgtest_kv_put              -> kv.put
mgtest_counter_increment   -> counter.increment
```

No provider-selected arbitrary tool name is accepted. Tool results are executed only by MGnarfTest's deterministic offline executor.

## Provider continuation evidence binding

Provider-native continuation context is now part of the MGnarfTest evidence boundary.

Every OpenAI/Gemini offline-tool subject action carries a closed `provider_context` object:

```text
provider
context kind
exact provider-native payload
SHA-256(provider + kind + payload)
```

The offline tool runner stores these contexts in the transcript and seals a `provider_context_chain_sha256` into the session receipt. The standalone session verifier recomputes the chain instead of trusting the reported hash.

For known provider subjects (`openai`, `google-gemini`), missing continuation context is fail-closed.

### OpenAI

The adapter preserves the exact Responses API `output` items from the tool-calling response, plus the response ID, inside the bound continuation context.

On the next subject step it replays the preserved output items **unchanged** before appending the receipt-backed `function_call_output`. This preserves applicable reasoning/function-call items rather than reconstructing a weaker synthetic tool-call history.

`parallel_tool_calls` is explicitly disabled for the deterministic sequential offline profile.

### Gemini

The adapter preserves the exact returned model `content` object and all of its `parts`.

On the next subject step it replays that exact model content before the receipt-backed `functionResponse`. This retains provider-returned fields such as `thoughtSignature` in their original Part and preserves the exact function call ID used by the matching function response.

## Fail-closed rules

The bridge rejects before provider continuation when it sees:

- an undeclared provider function name
- more than one tool call in a single subject step
- malformed tool arguments
- malformed or mismatched offline-tool history
- missing or invalid tool receipt hashes
- missing, resealed or cross-provider continuation context
- provider continuation whose function call does not match the executed MGnarfTest call
- a Gemini function call without an ID
- missing continuation context from a known OpenAI/Gemini offline-tool subject action

## Live-readiness limitation

Continuation binding is **implemented and mock-tested**, but it does not make credentialed live-provider execution ready.

Live execution remains blocked until:

- the repository trust root is enforceable;
- live-readiness explicitly authorizes the provider tool-subject mode;
- the selected exact provider/model capability is checked against this adapter contract;
- immutable model identity is captured when the provider exposes it;
- real repeated executions are independently verified.

Until then, live OpenAI/Gemini tool behavior remains `UNVERIFIED`.

## Immutable model identity

Adapters never infer an immutable model version from a mutable alias. `--immutable-version` may be supplied only when an immutable provider snapshot/build identity is actually known. Otherwise it remains `null` and strong-comparison policy records the limitation.

## Testing

`tools/test_provider_adapters.py` uses mocked provider transport and covers:

- normal subject/evaluator payloads
- receipt-backed tool evaluators
- OpenAI offline-tool subject call + receipt result round-trip
- exact OpenAI reasoning/output item replay
- Gemini offline-tool subject call + receipt result round-trip
- exact Gemini model-Part / thought-signature replay
- strict one-call-per-step behavior
- unknown-tool rejection
- Gemini call-ID requirement
- malformed history/receipt rejection before transport
- continuation tamper and cross-provider continuation rejection
- strict evaluator JSON handling

`tools/test_offline_tool_agent.py` and the standalone session verifier additionally cover semantic recomputation of the provider continuation chain.

CI performs no paid/live model calls and requires no provider secret.
