# MGnarfTest (MGTest)

MGnarfTest is MGnarf's external, versioned test registry and evidence layer.

It answers a simple question:

> Who defined this test, which exact target did it measure, what evidence was produced, and who accepted it into the stable test set?

MGnarfTest does **not** replace MGnarf's repository-owned tests. It adds an external/versioned layer for adversarial tests, frozen target bindings, execution receipts, review state, and later STABLE promotion.

## Two test planes

MGnarfTest keeps two distinct test planes:

```text
Gate tests        -> does MGnarf enforce the protected-effect contract?
AI behavior tests -> does an AI/agent preserve truth, evidence, authority and scope under pressure?
```

Gate tests live under `tests/` and bind to exact MGnarf source commits. AI behavior scenarios live under `ai-tests/` and bind execution evidence to the actual provider/model identity, parameters, scenario hash and response hash. A mutable model alias is never treated as equivalent to an immutable source commit.

The two planes produce different claims. An AI behavior PASS does not prove the MGnarf gate, and a gate PASS does not prove model behavior.

See [AI-BEHAVIOR-SPEC.md](AI-BEHAVIOR-SPEC.md).

## Current MGnarf baseline

Published stable release: **MGnarf v1.70**

Exact stable source commit:

```text
b811a13eab9cacd9f922b1f15097aa6bf700fc01
```

A gate-test result must bind to an exact MGnarf commit. `main` alone is never sufficient evidence. MGnarf is only the frozen target here; this AI-plane work changes MGnarfTest, not MGnarf.

## Development versus STABLE

```text
DEV / PROPOSED
  -> executable/scenario test definition
  -> frozen target identity
  -> isolated execution
  -> bound receipt
  -> receipt verification
  -> tamper rejection
  -> merge PROPOSED test to main
  -> successful main push evidence

STABLE promotion (separate PR)
  -> no test/workflow/tool changes
  -> reference successful main-push receipt artifact
  -> trusted base-branch promotion verifier
  -> authenticated review A
  -> authenticated review B
  -> STABLE
```

Two-review enforcement applies to STABLE promotion, not normal development. AI behavior STABLE promotion additionally requires at least one declared external reviewer among reviewer A/B.

The STABLE gate uses verifier code from the trusted base branch. It does **not** execute the promotion PR's code. A PR-generated receipt cannot be used as STABLE evidence; the evidence must come from a successful `main` push run for the exact tested subject commit.

## Trust-root status

Repository-local execution, receipt and promotion controls are evidence-tested for the existing gate-test plane. GitHub branch metadata currently reports `main` as **unprotected**, so MGnarfTest deliberately blocks STABLE promotion and does not claim that the trusted base branch is tamper-proof.

Repository visibility and repository trust-root enforcement are separate states. Making the repository public does not by itself authorize STABLE promotion or strengthen any evidence claim.

The AI behavior plane includes deterministic offline tool execution, receipt verification, provider adapters, repeated dual-evaluator aggregation, multi-subject orchestration, cross-model comparison and readiness checks. These are harness/protocol results. No credentialed real-provider AI behavior PASS or STABLE claim exists yet.

See [TRUST-BOUNDARY.md](TRUST-BOUNDARY.md) for the exact limitation and the requirements for a stronger STABLE trust claim.

## Current status

Twenty-six external MGnarf gate tests are currently `PROPOSED`: stage ordering, same-operation replay resistance, builder/verifier identity separation, post-PASS frozen-state drift, post-PASS revocation, authenticated verifier-evidence tampering, frozen effect-binding substitution, post-PASS authority availability fail-closed behavior, authenticated final-decision tampering, frozen-task substitution, verifier binding/result fail-closed behavior, verifier producer crash/partial-execution fail-closed behavior, frozen-contract tamper resistance, frozen evidence-coverage completeness, host inhibitor invalidation before effect execution, trusted state-probe availability fail-closed behavior, post-PASS identity-probe continuity, protected-effect callback failure/retry at-most-once consumption, transient state drift during verifier execution, revocation arriving during verifier execution, identity principal/trust-domain drift during verifier execution, inhibitor dominance when introduced during verifier execution, verifier-profile drift in the trusted identity view or host binding during verifier execution, concurrent same-contract protected-effect race resistance, concurrent race resistance when the sole winning callback crashes, and multi-process same-filesystem effect-consumption race resistance.

The AI behavior registry contains **24 versioned scenarios across 11 test IDs**, all still `PROPOSED`. Nine prompt/no-tool test IDs preserve their original v1 semantics and add v2 variants requiring `distinct-provider-v1` evaluator independence. `TOOLHONESTY` and `TOOLFABRICATION` preserve prompt-only v1, add receipt-backed offline-tool v2, and add deterministic final-claim / distinct-provider-evaluator v3 semantics.

For scenario versions that declare `distinct-provider-v1`, Evaluator A and Evaluator B coming from the same provider is a blocking condition. The dual runner records `EVALUATOR_PROVIDER_COLLISION`, and the independent dual-evidence verifier recomputes that condition rather than trusting the aggregate receipt. Historical v1 no-tool semantics are not silently reinterpreted.

Tool-enabled v2/v3 scenarios and the provider-neutral multi-subject path are executable against local/mock adapters and their evidence machinery is CI-tested. Real provider/model behavior evidence remains `UNVERIFIED`, credentialed live provider execution remains `BLOCKED`, and no AI behavior test is `STABLE`.

No external test is `STABLE` yet.

## License and security

MGnarfTest is licensed under the [Apache License 2.0](LICENSE).

For vulnerability reporting and disclosure guidance, see [SECURITY.md](SECURITY.md). Do not place credentials, private exploit details or other secrets in a public issue.

NARF principle: **no PASS without executed evidence; unavailable authority, state or identity is not permission; a stale or tampered decision is not authority; user preference does not alter truth or acceptance; an AI must not fabricate tool execution, independent review or evidence; verified work authorizes only the exact frozen task, verifier contract, identity context and authenticated frozen contract; missing, duplicate or unknown evidence cannot satisfy frozen coverage; a verifier crash cannot be reinterpreted as PASS evidence; transient state, revocation, identity or verifier-profile drift during verification overrides producer PASS and cannot be erased afterward; a trusted inhibitor dominates verifier PASS evidence whether introduced before, during or after verification; a failed effect callback does not restore consumed effect authority; concurrent sessions or local processes sharing one frozen contract and receipt filesystem cannot multiply local effect authority, even when the sole winning callback crashes; no STABLE test without frozen identity, target, receipt, review evidence and an enforceable repository trust root.**
