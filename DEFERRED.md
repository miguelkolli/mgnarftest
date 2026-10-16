# Deferred work

These items are intentionally **not blockers** for continued private-repository development of MGnarfTest. They become prerequisites only for the trust or execution claim they govern.

## Repository trust root

- Make `miguelkolli/mgnarftest` public when the test system is mature enough for external use.
- Enable enforceable `main` protection/rulesets when the repository/account plan supports it.
- Require pull requests, two authenticated approvals, stale-approval dismissal and conversation resolution for governed promotion.
- Re-run trust-root RECON after those controls exist; do not flip `STABLE_PROMOTION_ENABLED` merely because the repository becomes public.

## Credentialed live provider execution

- Do not wire OpenAI/Gemini provider secrets into repository workflows while the canonical trust root remains `UNPROTECTED`.
- After trust-root enforcement exists, add a credentialed workflow that checks out an exact trusted commit and runs the readiness gate before provider access.
- Capture immutable provider model snapshot/version/build identifiers when exposed; otherwise record the limitation.
- Run real repeated model executions and independently verify every evidence bundle before making live AI behavior claims.
- Add credentialed multi-subject orchestration for real cross-model runs.

## Provider tool continuation hardening

The OpenAI/Gemini offline-tool subject translation bridge is implemented and mock-tested, but live credentialed subject-tool execution remains deferred.

Before live enablement:

- bind and preserve provider continuation state required by the selected model/API;
- preserve OpenAI response/reasoning items when required for continuation rather than silently reconstructing a weaker context;
- preserve Gemini returned parts/thought-signature/context fields when required by the selected model family;
- add live-readiness checks that explicitly authorize the provider tool-subject execution mode;
- verify exact provider/model capability against the frozen adapter contract.

## External acceptance

- Obtain two authenticated reviewers for STABLE promotion.
- Ensure at least one declared external reviewer is outside the test author's control for AI behavior tests.
- Keep scenario acceptance (`STABLE`) separate from execution result (`PASS`/`FAIL`/`BLOCKED`/`UNVERIFIED`).

## Future effect profiles

- Keep real network-enabled tools deferred until a separate isolated network policy, destination allowlist, effect boundary and evidence contract exist.
- Add additional providers only behind the same adapter provenance, readiness and evidence-verification boundaries.
- Add any future real-effect tool class only as a separate profile/version; never reinterpret the deterministic offline profile as permission for production effects.
