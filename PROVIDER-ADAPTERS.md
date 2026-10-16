# Provider Adapters v1

MGnarfTest AI behavior runs use provider-specific adapters behind the provider-neutral runner protocol.

Included adapters:

- `adapters/openai_adapter.py` — OpenAI Responses API
- `adapters/gemini_adapter.py` — Google Gemini `generateContent`

Both are Python-standard-library only. Scenario data cannot choose an arbitrary provider URL. Credentials are read only from the provider environment variable explicitly passed to the runner (`OPENAI_API_KEY` or `GEMINI_API_KEY`) and are never returned in adapter JSON or receipts.

## Subject capability boundary

Provider subject adapters v1 intentionally support only frozen subject scenarios whose execution contract is:

```text
tools = none
network = false
```

Here `network=false` means no network capability is exposed to the tested model/agent. HTTPS transport used by the adapter to reach the selected provider is a separate transport boundary. A subject scenario requesting model tools or model network access fails closed instead of silently changing the test.

Receipt-backed tool-enabled **subject** execution therefore still uses the local/mock offline tool-agent protocol. Live OpenAI/Gemini subject tool calling is not enabled by this adapter change.

## Evaluator capability

Evaluator adapters accept both:

```text
mgtest.ai.evaluator
mgtest.ai.tool-evaluator
```

For a normal evaluator request, the provider receives the frozen scenario rubric and exact subject response.

For a tool evaluator request, MGnarfTest additionally supplies only already-verified tool evidence:

- exact subject binding
- scenario receipt SHA-256
- session receipt SHA-256
- verified tool trace (tool, arguments, actual result and tool-receipt hash)

The adapter validates the tool-evidence shape before any provider request is made. Missing or malformed receipt evidence fails closed.

The evaluator is instructed to classify the subject response against both the frozen rubric and the receipt-backed tool evidence. It does not execute tools or modify the tool trace.

Evaluator output remains exactly:

```json
{"result":"COMPLIANT|VIOLATION|INCONCLUSIVE","reason":"..."}
```

Anything else is rejected as an adapter error.

## Immutable model identity

Adapters never infer an immutable model version from a mutable alias. `--immutable-version` is optional and must be supplied only when an immutable provider snapshot/build identity is actually known. Without that evidence the runner preserves `immutable_version = null`; scenarios requiring immutable identity therefore cannot receive a strong aggregate PASS and are limited by runner policy.

## Security boundary

Supporting `mgtest.ai.tool-evaluator` does **not** grant provider models a tool capability. Tool execution remains inside MGnarfTest's deterministic offline executor. The provider evaluator receives a serialized, already-verified evidence trace as data only.

No repository workflow currently exposes provider secrets for live tool-behavior execution while the repository trust root is `UNPROTECTED`.

## Testing

`tools/test_provider_adapters.py` uses mocked provider calls. It verifies:

- payload shape and authentication-header selection
- strict evaluator JSON handling
- immutable-version non-inference
- fail-closed rejection of unsupported subject tool/network capability
- OpenAI and Gemini tool-evaluator prompt inclusion of receipt-backed tool evidence
- rejection of malformed/missing tool-evaluator evidence before transport

CI performs no paid/live model calls and requires no provider secret.

Real provider/model behavior evidence remains `UNVERIFIED` until the applicable runner is executed against real provider models with credentials, exact frozen scenario and independently verified evidence.
