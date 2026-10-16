# MGnarfTest AI Runner v1

`tools/run_ai_behavior.py` executes one frozen AI behavior scenario repeatedly through two separate out-of-process adapters: a subject-model adapter and an evaluator adapter.

```text
scenario.json
  -> subject adapter
  -> model response
  -> evaluator adapter
  -> per-run receipt + transcript hash
  -> aggregate receipt
```

The runner never executes code from `scenario.json`. Adapter commands are supplied separately and are invoked without a shell.

## Example

```text
python3 tools/run_ai_behavior.py \
  --scenario ai-tests/MGTEST-AI-FALSEPASS-001/v1/scenario.json \
  --model-adapter-json '["python3","path/to/model_adapter.py"]' \
  --evaluator-adapter-json '["python3","path/to/evaluator_adapter.py"]' \
  --output-dir /tmp/mgtest-ai-falsepass
```

The default number of runs is the scenario's frozen `minimum_runs`. `--runs` may increase it but cannot lower it.

## Subject adapter response

The model adapter receives one JSON request on stdin and returns one JSON object on stdout with exactly these fields:

```text
provider
model
immutable_version       # string or null
parameters              # actual material generation parameters
tool_configuration
network_configuration   # boolean
response_text
```

Provider/model pins, tool configuration and network configuration must match the frozen scenario. Identity or material parameter drift across runs blocks the aggregate.

## Evaluator adapter response

The evaluator receives the frozen scenario/rubric plus the exact subject response and returns:

```text
evaluator_id
evaluator_version
provider
model
immutable_version       # string or null
result                   # COMPLIANT / VIOLATION / INCONCLUSIVE
reason
```

If the evaluator has the exact same provider/model/version tuple as the subject, the runner marks `EVALUATOR_IDENTITY_COLLISION` and blocks the aggregate. This is a mechanical separation check, not proof of real-world independence.

## Aggregate semantics

- critical violations above the frozen tolerance -> `FAIL`
- adapter errors or identity/configuration drift -> `BLOCKED`
- any inconclusive run -> `UNVERIFIED`
- all compliant but required immutable subject-model version unavailable -> `LIMITATION_CONFIRMED`
- only evidence-complete, stable-configuration runs can produce `PASS`

## Evidence binding

Each per-run receipt binds scenario ID/version, scenario SHA-256, context SHA-256, subject response SHA-256, evaluator reason SHA-256, model/evaluator identity, material parameter hash, tool/network configuration, transcript SHA-256, exact MGnarfTest commit when available, and the runner-file SHA-256.

`aggregate.json` binds every per-run receipt hash and the frozen aggregation policy. If the runner cannot bind to an exact MGnarfTest commit, an otherwise compliant result is limited to `LIMITATION_CONFIRMED`.

These hashes are tamper-evident bindings, not a third-party signature. STABLE acceptance still requires the repository evidence/promotion path and the external-review rule.

## Secrets and adapters

Adapters inherit only a small safe environment by default. Credentials must be explicitly passed by variable name using `--model-env NAME` or `--evaluator-env NAME`; credential values are not written to receipts.

Runner v1 does not sandbox adapter filesystem or provider-transport network access. Adapters are trusted execution components and need separate review/isolation before STABLE evidence can rely on them.
