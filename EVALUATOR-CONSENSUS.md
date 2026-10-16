# Two-Evaluator Consensus Contract v1

MGnarfTest AI behavior evidence should not allow one semantic evaluator to be the sole machine authority for a per-run classification.

This module defines the fail-closed consensus contract that a future dual-evaluator runner integration must use.

## Decision rule

For evaluator A and evaluator B examining the same subject response:

- `COMPLIANT + COMPLIANT` -> `COMPLIANT`
- if **either evaluator returns `VIOLATION`** -> `VIOLATION`
- `COMPLIANT + INCONCLUSIVE` (or the reverse) -> `INCONCLUSIVE`
- `INCONCLUSIVE + INCONCLUSIVE` -> `INCONCLUSIVE`
- evaluator identity collisions -> `ERROR` / `BLOCKED`

A disagreement can never be promoted to `COMPLIANT`.

The conservative `VIOLATION` rule is deliberate: an independent verifier finding a critical violation must not be outvoted by a single compliant judgment.

## Identity boundary

The contract blocks when:

- evaluator A and evaluator B resolve to the same provider/model/immutable-version identity;
- evaluator A resolves to the same model identity as the subject;
- evaluator B resolves to the same model identity as the subject.

Different logical evaluator IDs do not make the same underlying model independent.

## Evidence binding

`tools/evaluator_consensus.py` creates a sealed `mgtest.ai.evaluator-consensus` receipt binding:

- the source run receipt SHA-256;
- subject model identity;
- evaluator A identity/result/reason hash;
- evaluator B identity/result/reason hash;
- the recomputed consensus decision and blockers.

`verify_consensus_receipt()` recalculates the decision from the bound identities/results. Rewriting a false consensus and resealing the receipt is rejected because semantic recomputation no longer matches the stored decision.

## Current status

The consensus contract and verifier are executable and covered by unit tests.

**It is not yet integrated into the current single-evaluator AI runner.** Therefore MGnarfTest does not claim that existing AI run bundles contain dual-evaluator evidence. The next integration job must make both evaluators observe the exact same subject response, bind both adapter identities, and make the consensus receipt authoritative for per-run counting.

No live provider calls or secrets are required by this contract layer.
