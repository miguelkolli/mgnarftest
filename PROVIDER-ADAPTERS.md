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

Provider-native continuation context is part of the MGnarfTest evidence boundary.

Every OpenAI/Gemini offline-tool subject action carries a closed `provider_context` object containing provider, context kind, exact provider-native payload and a SHA-256 binding.

The offline tool runner stores these contexts in the transcript and seals a `provider_context_chain_sha256` into the session receipt. The standalone session verifier recomputes the chain instead of trusting the reported hash.

For known provider subjects (`openai`, `google-gemini`), missing continuation context is fail-closed.

### OpenAI

The adapter preserves the exact Responses API `output` items from the tool-calling response, plus the response ID, inside the bound continuation context.

On the next subject step it replays the preserved output items unchanged before appending the receipt-backed `function_call_output`. This preserves applicable reasoning/function-call items rather than reconstructing a weaker synthetic history.

`parallel_tool_calls` is explicitly disabled for the deterministic sequential offline profile.

### Gemini

The adapter preserves the exact returned model `content` object and all of its `parts`.

On the next subject step it replays that exact model content before the receipt-backed `functionResponse`. This retains provider-returned fields such as `thoughtSignature` in their original Part and preserves the exact function call ID used by the matching function response.

## Live-readiness v3

The live-readiness planner now understands the receipt-backed deterministic tool-subject mode without enabling it.

A readiness plan binds:

- exact MGnarfTest commit
- exact scenario hash
- readiness-gate hash
- subject/evaluator adapter hashes
- provider/model aliases
- required secret environment-variable **names** only
- frozen tool configuration and network=false
- provider-specific tool-subject continuation contract
- `provider-native-context-chain-v1` evidence contract

Tool-subject readiness has three independent authority conditions:

1. repository trust root enforced;
2. live provider tool-subject execution explicitly authorized by governance;
3. exact provider/model tool capability verified against the frozen adapter contract.

The second and third conditions are not CLI force flags. Under the current repository state the plan remains `BLOCKED`.

## Fail-closed rules

The bridge/readiness boundary rejects when it sees:

- an undeclared provider function name
- more than one tool call in a single subject step
- malformed tool arguments
- malformed or mismatched offline-tool history
- missing or invalid tool receipt hashes
- missing, resealed or cross-provider continuation context
- provider continuation whose function call does not match the executed MGnarfTest call
- a Gemini function call without an ID
- missing continuation context from a known OpenAI/Gemini offline-tool subject action
- unsupported subject tool configuration or model network capability
- missing live tool-subject authority or unverified exact model capability

## Live-execution limitation

Continuation binding and readiness planning are implemented and mock-tested, but credentialed live-provider execution is still intentionally blocked.

No live GPT/Gemini behavior result exists yet. Real provider/model behavior remains `UNVERIFIED` until the trust/authority/capability blockers are removed through governed evidence and real repeated executions are independently verified.

## Immutable model identity

Adapters never infer an immutable model version from a mutable alias. `--immutable-version` may be supplied only when an immutable provider snapshot/build identity is actually known. Otherwise it remains `null` and strong-comparison policy records the limitation.

## Testing

Mock/unit coverage includes normal subject/evaluator payloads, receipt-backed tool evaluators, exact provider continuation replay, continuation tamper/cross-provider rejection, offline session context-chain verification, readiness authority separation and strict evaluator JSON handling.

CI performs no paid/live model calls and requires no provider secret.
