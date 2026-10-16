# Deferred work

These items are intentionally **not blockers** for continuing private-repository development of MGnarfTest. They become prerequisites only for the trust or execution claim they govern.

## Repository trust root

- Make `miguelkolli/mgnarftest` public when the test system is mature enough for external use.
- Enable enforceable `main` protection/rulesets when the repository/account plan supports it.
- Require pull requests, two authenticated approvals, stale-approval dismissal and conversation resolution for governed promotion.
- Re-run trust-root RECON after those controls exist; do not flip `STABLE_PROMOTION_ENABLED` merely because the repository becomes public.

## Live provider execution

- Do not wire OpenAI/Gemini provider secrets into repository workflows while the canonical trust root remains `UNPROTECTED`.
- After trust-root enforcement exists, add a credentialed live-run workflow that checks out an exact trusted commit and runs the existing readiness gate before provider access.
- Capture immutable provider model snapshot/version/build identifiers when the provider exposes them; otherwise record the limitation.
- Run real repeated model executions and verify every evidence bundle independently before making any AI behavior result claim.

## External acceptance

- Obtain the required two authenticated reviewers for STABLE promotion.
- Ensure at least one declared external reviewer is outside the test author's control for AI behavior tests.
- Keep scenario acceptance (`STABLE`) separate from execution result (`PASS`/`FAIL`/`BLOCKED`/`UNVERIFIED`).

## Later execution capabilities

- Build a multi-subject cross-model comparison harness. Current runner semantics test one subject model plus a separate evaluator, so cross-model comparison must not be represented as an ordinary single-subject scenario.
- Add isolated tool-enabled and network-enabled AI execution profiles before scenarios are allowed to exercise real tools or external network effects.
- Add additional providers only behind the same adapter provenance, readiness and evidence-verification boundaries.
