# Deferred work

These items are intentionally **not blockers** for continued private-repository development of MGnarfTest. They become prerequisites only for the trust or execution claim they govern.

## Repository trust root

- Make `miguelkolli/mgnarftest` public when the test system is mature enough for external use.
- Enable enforceable `main` protection/rulesets when the repository/account plan supports it.
- Require pull requests, two authenticated approvals, stale-approval dismissal and conversation resolution for governed promotion.
- Re-run trust-root RECON after those controls exist; do not flip `STABLE_PROMOTION_ENABLED` merely because the repository becomes public.

## Credentialed live provider execution

The readiness gate understands both normal no-tool subjects and the receipt-backed deterministic offline-tool subject mode. This does **not** authorize live tool execution.

Tool-enabled readiness now requires two separate hash-bound evidence artifacts instead of caller-supplied boolean flags:

- governance authorization evidence for the exact MGnarfTest commit/provider/model/adapter/tool contract;
- provider/model capability evidence for the exact adapter + continuation contract, with verifier identity and verification method.

Before credentialed provider-tool execution can become `READY`:

- repository trust root must be `PROTECTED`/`ENFORCED` and governed promotion enabled;
- both evidence artifacts must validate against the exact readiness target;
- exact MGnarfTest commit, scenario hash, readiness-gate hash and provider/evaluator adapter hashes must remain bound;
- required provider secret **names** may be planned, but secret values must not enter readiness evidence;
- immutable provider model snapshot/version/build identifiers must be captured when exposed; otherwise record the limitation;
- real repeated model executions must be independently verified before any live AI behavior claim;
- credentialed multi-subject orchestration is still required for real cross-model runs.

Under the current private/unprotected trust root, live readiness therefore remains intentionally `BLOCKED`.

The evidence file format itself is not sufficient authority while the repository trust root is unprotected. Once the trust root is enforced, acceptance of authorization/capability evidence must be governed by the protected review/promotion process.

## Provider continuation status

OpenAI/Gemini provider-native continuation state is hash-bound into offline tool session evidence and mock-tested:

- OpenAI output/reasoning/function-call items are preserved and replayed before receipt-backed `function_call_output`.
- Gemini model content/Parts, including returned thought-signature fields, are preserved and replayed before receipt-backed `functionResponse`.
- The session verifier independently recomputes the provider-context chain and checks provider-native call semantics.

This removes the previous continuation-reconstruction gap, but **does not authorize credentialed live execution**.

## External acceptance

- Obtain two authenticated reviewers for STABLE promotion.
- Ensure at least one declared external reviewer is outside the test author's control for AI behavior tests.
- Keep scenario acceptance (`STABLE`) separate from execution result (`PASS`/`FAIL`/`BLOCKED`/`UNVERIFIED`).

## Future effect profiles

- Keep real network-enabled tools deferred until a separate isolated network policy, destination allowlist, effect boundary and evidence contract exist.
- Add additional providers only behind the same adapter provenance, readiness and evidence-verification boundaries.
- Add any future real-effect tool class only as a separate profile/version; never reinterpret the deterministic offline profile as permission for production effects.
