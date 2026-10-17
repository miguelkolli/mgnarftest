# Cross-Model Evidence Comparison v1

MGnarfTest can compare multiple AI subject models against the **same frozen behavior scenario** without collapsing their evidence into one overall PASS.

The comparison layer consumes already-created **dual-evaluator v2 evidence bundles**. It does not call model providers and does not require credentials.

## Required equality boundary

A comparison is `STRONG` only when every subject bundle has:

- the exact same scenario binding and scenario hash;
- the exact same MGnarfTest commit;
- the exact same dual-runner hash;
- the exact same Evaluator A identity and adapter binding;
- the exact same Evaluator B identity and adapter binding;
- the exact same consensus policy;
- the exact same requested run count, minimum run count and violation tolerance;
- a distinct subject model identity.

This prevents a model from appearing better because it was tested against a different prompt, different judges, a different runner or fewer runs.

## Comparison status

The comparison produces a sealed `mgtest.ai.cross-model-comparison` receipt.

- `STRONG` — all required equality constraints hold and no material limitation is present.
- `LIMITED` — evidence is structurally comparable, but limitations such as mutable model versions or parameter variance are recorded.
- `BLOCKED` — the evidence sets are not safely comparable.

The comparison receipt contains each subject's verified aggregate result, run counts, rates, limitations, subject binding and aggregate receipt hash.

## No overall PASS and no automatic winner

The comparison layer deliberately does **not** produce:

- an overall AI PASS;
- a winner;
- a leaderboard rank;
- a claim that one model is universally safer.

`PASS`, `FAIL`, `BLOCKED`, `UNVERIFIED` and `LIMITATION_CONFIRMED` remain properties of each subject's own frozen-scenario execution evidence.

## Independent recomputation

`tools/compare_ai_dual_bundles.py` verifies every source bundle through `tools/verify_ai_dual_evidence.py` before comparison.

`verify_comparison_receipt()` then rebuilds the comparison from the source bundles. Editing a model's counts, rates, identity or comparability decision and merely resealing the receipt is rejected.

## Current trust status

This comparison layer works entirely on mock or previously produced evidence and therefore does not require live provider secrets.

Credentialed cross-model live execution remains deferred until the repository trust root is enforceable. Real model comparison claims remain `UNVERIFIED` until real provider runs exist.
