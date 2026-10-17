# Deferred work

These items are intentionally **not blockers** for continued MGnarfTest development. They become prerequisites only for the trust or execution claim they govern.

## Repository trust root

The public repository trust root is implemented as a protected `main` branch plus the active `MGnarfTest main protection` ruleset. Trust-policy changes and STABLE requests are verified against the live ruleset from trusted base-branch code. The policy requires no bypass actors, deletion/non-fast-forward restrictions, pull requests, resolved conversations, strict/up-to-date checks and the governed GitHub Actions checks.

Repository protection removes only the repository-trust blocker. Every STABLE promotion still requires its own exact main-push evidence plus two authenticated exact-head approvals, and AI behavior STABLE additionally requires the declared external-review boundary.

## Credentialed live provider execution

The readiness gate understands both normal no-tool subjects and the receipt-backed deterministic offline-tool subject mode. Repository trust protection does **not** itself authorize a provider call or prove model behavior.

Tool-enabled readiness v5 requires:

- governance authorization evidence for the exact MGnarfTest commit/provider/model/adapter/tool contract;
- provider/model capability evidence for the exact adapter + continuation contract;
- an `ACCEPTED` lifecycle record bound to the exact authorization evidence;
- an `ACCEPTED` lifecycle record bound to the exact capability evidence;
- authenticated acceptance identity proof from the protected trust root.

The first four structural contracts are implemented. Authenticated acceptance identity proof is still deliberately unavailable, so tool-enabled live readiness stays `BLOCKED` even after repository protection if someone manufactures structurally valid ACCEPTED JSON records.

Before credentialed provider-tool execution can become `READY`:

- authenticated GitHub review state must prove the acceptance records' reviewer identities/review IDs;
- exact MGnarfTest commit, evidence hashes, scenario hash, readiness-gate hash and provider/evaluator adapter hashes must remain bound;
- stale reviews must become invalid after evidence/acceptance revision;
- required provider secret **names** may be planned, but secret values must not enter readiness evidence;
- immutable provider model snapshot/version/build identifiers must be captured when exposed; otherwise record the limitation;
- real repeated model executions must be independently verified before any live AI behavior claim;
- provider-neutral multi-subject orchestration must remain bound to the same frozen scenario, evaluator pair and exact MGnarfTest commit; this contract is implemented and mock-tested, but credentialed runs remain deferred.

## Evidence acceptance authentication

The structural acceptance validator enforces author/reviewer separation, two distinct reviewers, exact evidence/commit review binding, an external approver for `ACCEPTED`, accepted revision, trust-root receipt and record hashing.

Repository-wide status-lattice v2 additionally proves that weaker lifecycle states cannot become effective authenticated acceptance authority, malformed/resealed status upgrades are rejected, and even a structurally valid `ACCEPTED` record remains non-authoritative while `authenticated_identity_verified=false`.

Still deferred after repository trust-root protection:

- verify reviewer identities and review IDs against authenticated GitHub review state;
- generate/verify the live-tool acceptance trust-root receipt from a protected workflow;
- prove the external reviewer is outside the author's control rather than trusting a self-declared relation;
- reject stale approvals automatically after any evidence/record revision using authenticated review state.

Therefore `STRUCTURALLY_VALID` is not authenticated acceptance, and readiness v5 treats it accordingly.

## Provider continuation status

OpenAI/Gemini provider-native continuation state is hash-bound into offline tool session evidence and mock-tested:

- OpenAI output/reasoning/function-call items are preserved and replayed before receipt-backed `function_call_output`.
- Gemini model content/Parts, including returned thought-signature fields, are preserved and replayed before receipt-backed `functionResponse`.
- The session verifier independently recomputes the provider-context chain and checks provider-native call semantics.

This removes the previous continuation-reconstruction gap, but **does not authorize credentialed live execution**.

## Final-claim semantics

The v3 tool-honesty and tool-fabrication scenarios provide a narrow deterministic `claims-only-v1` binding. For those exact scenarios, the independent verifier can prove that the machine-readable final observed claim equals the receipt-backed tool result.

Still deferred:

- generalized claim-to-receipt entailment for unrestricted natural-language answers;
- safe deterministic interpretation of negation, hedging, units, transformed values and multi-sentence conclusions;
- extending deterministic claim binding beyond explicitly versioned scenarios without silently changing old evidence semantics.

Semantic evaluators remain necessary outside the frozen claims-only contract.

## Evaluator independence

Scenario-bound `distinct-provider-v1` is implemented for the nine no-tool v2 scenarios and the two tool v3 scenarios. Same-provider evaluator pairs are recorded as `EVALUATOR_PROVIDER_COLLISION`, the aggregate remains `BLOCKED`, and the independent dual-evidence verifier recomputes the collision from verified evaluator bindings. Historical no-tool v1 semantics remain unchanged.

Still deferred:

- proving organizational or training-data independence between providers;
- measuring correlated evaluator error empirically across larger judge ensembles;
- changing historical v1 scenario semantics, which is intentionally avoided rather than treated as unfinished work.

## Test awareness / benchmark contamination

A subject can potentially recognize a scenario as a benchmark and behave differently from production use. MGnarfTest currently cannot prove the absence of test awareness or training/benchmark contamination.

Possible future mitigations include:

- private challenge sets;
- paraphrase families generated independently from the public scenario text;
- held-out scenario variants;
- delayed publication of some challenge material;
- production-shadow comparisons where permitted and privacy-safe.

Until then, a behavior PASS is evidence only for the frozen tested boundary and must not be represented as proof of identical production behavior.

## Status monotonicity

Repository-wide status-lattice verifier v2 is implemented and CI-covered. It independently exercises the current single-evaluator aggregate, dual-evaluator aggregate, receipt-backed tool aggregate, cross-model comparison, evidence acceptance lifecycle, live-readiness plan and STABLE-promotion trust-root guard. Degraded, weaker or unauthenticated inputs are required to remain non-promoting; they may not become `PASS`, `READY`, `STRONG`, authenticated `ACCEPTED` or `STABLE` authority.

See [STATUS-LATTICE.md](STATUS-LATTICE.md) for the exact v2 coverage boundary.

Still deferred:

- automatic discovery of every future status-bearing runner, comparator, readiness path, acceptance state and promotion mechanism;
- machine-checking newly introduced result states/transitions without explicitly adding them to the verifier and CI.

Any downstream component that receives a blocking state must fail closed; it must never reinterpret `BLOCKED` as `PASS`, `READY` or authenticated `ACCEPTED`.

## External acceptance

- Obtain two authenticated reviewers for each STABLE promotion.
- Ensure at least one verified external reviewer is outside the test author's control for AI behavior tests.
- Keep scenario acceptance (`STABLE`) separate from execution result (`PASS`/`FAIL`/`BLOCKED`/`UNVERIFIED`).

## Future effect profiles

- Keep real network-enabled tools deferred until a separate isolated network policy, destination allowlist, effect boundary and evidence contract exist.
- Add additional providers only behind the same adapter provenance, readiness and evidence-verification boundaries.
- Add any future real-effect tool class only as a separate profile/version; never reinterpret the deterministic offline profile as permission for production effects.
