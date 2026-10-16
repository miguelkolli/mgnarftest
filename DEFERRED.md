# Deferred work

These items are intentionally **not blockers** for continued private-repository development of MGnarfTest. They become prerequisites only for the trust or execution claim they govern.

## Repository trust root

- Make `miguelkolli/mgnarftest` public when the test system is mature enough for external use.
- Enable enforceable `main` protection/rulesets when the repository/account plan supports it.
- Require pull requests, two authenticated approvals, stale-approval dismissal and conversation resolution for governed promotion.
- Re-run trust-root RECON after those controls exist; do not flip `STABLE_PROMOTION_ENABLED` merely because the repository becomes public.

## Credentialed live provider execution

The readiness gate understands both normal no-tool subjects and the receipt-backed deterministic offline-tool subject mode. This does **not** authorize live tool execution.

Tool-enabled readiness v5 requires:

- governance authorization evidence for the exact MGnarfTest commit/provider/model/adapter/tool contract;
- provider/model capability evidence for the exact adapter + continuation contract;
- an `ACCEPTED` lifecycle record bound to the exact authorization evidence;
- an `ACCEPTED` lifecycle record bound to the exact capability evidence;
- authenticated acceptance identity proof from the protected trust root.

The first four contracts are implemented. The last item remains deliberately unavailable in the current private/unprotected phase, so tool-enabled live readiness stays `BLOCKED` even if someone manufactures structurally valid ACCEPTED JSON records.

Before credentialed provider-tool execution can become `READY`:

- repository trust root must be `PROTECTED`/`ENFORCED` and governed promotion enabled;
- authenticated GitHub review state must prove the acceptance records' reviewer identities/review IDs;
- exact MGnarfTest commit, evidence hashes, scenario hash, readiness-gate hash and provider/evaluator adapter hashes must remain bound;
- stale reviews must become invalid after evidence/acceptance revision;
- required provider secret **names** may be planned, but secret values must not enter readiness evidence;
- immutable provider model snapshot/version/build identifiers must be captured when exposed; otherwise record the limitation;
- real repeated model executions must be independently verified before any live AI behavior claim;
- credentialed multi-subject orchestration is still required for real cross-model runs.

## Evidence acceptance authentication

The structural acceptance validator enforces author/reviewer separation, two distinct reviewers, exact evidence/commit review binding, an external approver for `ACCEPTED`, accepted revision, trust-root receipt and record hashing.

Still deferred until the trust root is protected:

- verify reviewer identities and review IDs against authenticated GitHub review state;
- generate/verify the trust-root receipt from a protected promotion workflow;
- prove the external reviewer is outside the author's control rather than trusting a self-declared relation;
- reject stale approvals automatically after any evidence/record revision.

Therefore `STRUCTURALLY_VALID` is not authenticated acceptance, and readiness v5 treats it accordingly.

## Provider continuation status

OpenAI/Gemini provider-native continuation state is hash-bound into offline tool session evidence and mock-tested:

- OpenAI output/reasoning/function-call items are preserved and replayed before receipt-backed `function_call_output`.
- Gemini model content/Parts, including returned thought-signature fields, are preserved and replayed before receipt-backed `functionResponse`.
- The session verifier independently recomputes the provider-context chain and checks provider-native call semantics.

This removes the previous continuation-reconstruction gap, but **does not authorize credentialed live execution**.

## External acceptance

- Obtain two authenticated reviewers for STABLE promotion.
- Ensure at least one verified external reviewer is outside the test author's control for AI behavior tests.
- Keep scenario acceptance (`STABLE`) separate from execution result (`PASS`/`FAIL`/`BLOCKED`/`UNVERIFIED`).

## Future effect profiles

- Keep real network-enabled tools deferred until a separate isolated network policy, destination allowlist, effect boundary and evidence contract exist.
- Add additional providers only behind the same adapter provenance, readiness and evidence-verification boundaries.
- Add any future real-effect tool class only as a separate profile/version; never reinterpret the deterministic offline profile as permission for production effects.
