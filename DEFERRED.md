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
- Extend live-readiness to explicitly authorize the receipt-backed provider tool-subject mode; the current readiness contract still blocks subject tool capability.
- Verify the selected exact provider/model capability against the frozen adapter contract before live use.
- Capture immutable provider model snapshot/version/build identifiers when exposed; otherwise record the limitation.
- Run real repeated model executions and independently verify every evidence bundle before making live AI behavior claims.
- Add credentialed multi-subject orchestration for real cross-model runs.

## Provider continuation status

OpenAI/Gemini provider-native continuation state is now hash-bound into offline tool session evidence and mock-tested:

- OpenAI output/reasoning/function-call items are preserved and replayed before receipt-backed `function_call_output`.
- Gemini model content/Parts, including returned thought-signature fields, are preserved and replayed before receipt-backed `functionResponse`.
- The session verifier independently recomputes the provider-context chain.

This removes the previous continuation-reconstruction gap, but **does not authorize credentialed live execution**.

## External acceptance

- Obtain two authenticated reviewers for STABLE promotion.
- Ensure at least one declared external reviewer is outside the test author's control for AI behavior tests.
- Keep scenario acceptance (`STABLE`) separate from execution result (`PASS`/`FAIL`/`BLOCKED`/`UNVERIFIED`).

## Future effect profiles

- Keep real network-enabled tools deferred until a separate isolated network policy, destination allowlist, effect boundary and evidence contract exist.
- Add additional providers only behind the same adapter provenance, readiness and evidence-verification boundaries.
- Add any future real-effect tool class only as a separate profile/version; never reinterpret the deterministic offline profile as permission for production effects.
