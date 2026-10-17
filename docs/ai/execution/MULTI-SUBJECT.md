# Multi-subject AI behavior orchestration

MGnarfTest can orchestrate the same frozen AI behavior scenario across two or more subject adapters without weakening the existing dual-evaluator or cross-model evidence boundaries.

The private-repository flow is:

```text
frozen scenario
  -> subject A + frozen evaluator pair -> dual evidence -> independent verify
  -> subject B + frozen evaluator pair -> dual evidence -> independent verify
  -> ...
  -> evidence-only cross-model comparison -> independent recomputation
  -> sealed multi-subject orchestration receipt
  -> independent orchestration verifier
```

`tools/run_ai_multi_subject.py` performs orchestration. `tools/verify_ai_multi_subject.py` independently re-verifies every subject bundle, recomputes the cross-model comparison and reconstructs the orchestration receipt.

## Configuration boundary

The configuration contains adapter command arrays and a list of environment-variable **names** that each adapter is allowed to receive. Secret values are never written into MGnarfTest evidence by the orchestrator. The existing adapter runner constructs a minimal environment and reads allowed values only at execution time.

At least two uniquely labelled subjects are required. All subjects use the same frozen evaluator A/B commands, run count, scenario and MGnarfTest commit. The cross-model comparator independently checks those bindings before it can produce `STRONG` comparability.

## Claims

A `STRONG` comparison means the verified evidence bundles satisfy the frozen comparison contract. It is not an overall model ranking, a scientific independence claim, or a production-safety guarantee.

A duplicate subject identity or any comparison blocker yields `BLOCKED`. Mutable model versions, input limitations or other supported limitations yield `LIMITED` where the comparator contract permits it.

## Current trust boundary

This orchestration path is provider-neutral and mock/local CI testable. Credentialed live provider execution remains `BLOCKED` while the repository trust root is unprotected. Implementing orchestration does not make real OpenAI/Gemini model behavior verified and does not enable STABLE promotion.
