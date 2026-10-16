# Provider Adapters v1

MGnarfTest AI behavior runs use provider-specific adapters behind the provider-neutral runner protocol.

Included adapters:

- `adapters/openai_adapter.py` — OpenAI Responses API
- `adapters/gemini_adapter.py` — Google Gemini `generateContent`

Both are Python-standard-library only. Scenario data cannot choose an arbitrary provider URL. Credentials are read only from the provider environment variable explicitly passed to the runner (`OPENAI_API_KEY` or `GEMINI_API_KEY`) and are never returned in adapter JSON or receipts.

## Initial capability boundary

Provider adapters v1 intentionally support only subject scenarios whose frozen execution contract is:

```text
tools = none
network = false
```

Here `network=false` means no network capability is exposed to the tested model/agent. HTTPS transport used by the adapter to reach the selected provider is a separate transport boundary. A scenario requesting model tools or model network access fails closed instead of silently changing the test.

## Immutable model identity

Adapters never infer an immutable model version from a mutable alias. `--immutable-version` is optional and must be supplied only when an immutable provider snapshot/build identity is actually known. Without that evidence the runner preserves `immutable_version = null`; scenarios requiring immutable identity therefore cannot receive a strong aggregate PASS and are limited by the runner policy.

## Subject examples

OpenAI:

```text
python3 tools/run_ai_behavior.py \
  --scenario ai-tests/MGTEST-AI-FALSEPASS-001/v1/scenario.json \
  --model-adapter-json '["python3","adapters/openai_adapter.py","--model","<model>"]' \
  --evaluator-adapter-json '["python3","adapters/gemini_adapter.py","--model","<model>","--evaluator-id","external-evaluator","--evaluator-version","1"]' \
  --model-env OPENAI_API_KEY \
  --evaluator-env GEMINI_API_KEY \
  --output-dir /tmp/mgtest-ai
```

The example deliberately uses different provider adapters for subject and evaluator. A separate provider is not by itself proof of epistemic independence, but it avoids the runner's exact subject/evaluator identity collision and creates a clearer review boundary.

## Evaluator contract

Evaluator adapters receive the frozen scenario purpose, stimulus, rubric, limits and exact subject response. The model is instructed to return exactly:

```json
{"result":"COMPLIANT|VIOLATION|INCONCLUSIVE","reason":"..."}
```

Anything else is rejected as an adapter error; malformed semantic evidence is never coerced into PASS.

## Testing

`tools/test_provider_adapters.py` uses mocked provider calls. It verifies payload shape, authentication header selection, strict evaluator JSON handling, immutable-version non-inference, and fail-closed rejection of unsupported tool/network scenarios. CI performs no paid/live model calls and requires no provider secret.

Real AI behavior evidence remains `UNVERIFIED` until the runner is executed against real provider models with the applicable credentials and frozen scenario.
