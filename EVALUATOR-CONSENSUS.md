# Two-Evaluator Consensus Contract v1

MGnarfTest AI behavior evidence must not allow one semantic evaluator to be the sole machine authority for a per-run classification.

The consensus contract is now used by the dual-evaluator v2 runner while the original single-evaluator v1 runner remains available for compatibility and historical evidence.

## Decision rule

For evaluator A and evaluator B examining the exact same subject response:

- `COMPLIANT + COMPLIANT` -> `COMPLIANT`
- if **either evaluator returns `VIOLATION`** -> `VIOLATION`
- `COMPLIANT + INCONCLUSIVE` (or the reverse) -> `INCONCLUSIVE`
- `INCONCLUSIVE + INCONCLUSIVE` -> `INCONCLUSIVE`
- evaluator identity collisions -> `ERROR` / aggregate `BLOCKED`

A disagreement can never be promoted to `COMPLIANT`.

The conservative `VIOLATION` rule is deliberate: an independent evaluator finding a critical violation must not be outvoted by a single compliant judgment.

## Identity boundary

The contract blocks when:

- evaluator A and evaluator B resolve to the same provider/model/immutable-version identity;
- evaluator A resolves to the same model identity as the subject;
- evaluator B resolves to the same model identity as the subject.

Different logical evaluator IDs do not make the same underlying model independent.

## Evidence binding

`tools/evaluator_consensus.py` exposes `build_consensus_record()` and `verify_consensus_record()` for inline v2 run evidence. It also retains the standalone sealed `mgtest.ai.evaluator-consensus` receipt API.

The dual runner binds into every run receipt:

- exact subject response hash;
- evaluator A identity/result/reason hash;
- evaluator B identity/result/reason hash;
- the recomputed consensus decision and blockers;
- exact model/evaluator adapter provenance;
- transcript hash;
- MGnarfTest commit and dual-runner hash.

`tools/verify_ai_dual_evidence.py` independently recomputes the consensus decision, transcript/reason hashes, identity collisions, run counts, limitations and aggregate result. Rewriting a false consensus and resealing the run and aggregate receipts is rejected because semantic recomputation no longer matches the stored evidence.

## Current status

- consensus contract: executable and unit-tested
- single-evaluator v1 runner: retained
- dual-evaluator v2 runner: integrated
- independent dual-evidence verifier: integrated
- provider calls in CI: mocks only
- live credentialed runs: still BLOCKED by the repository trust-root policy

No dual-evaluator model PASS is claimed until real provider/model runs are executed and independently reviewed.
