# MGnarfTest (MGTest)

MGnarfTest is the private development repository for MGnarf's external, versioned test registry and evidence layer.

It answers a simple question:

> Who defined this test, which exact MGnarf version did it target, what did it measure, what evidence was produced, and who accepted it into the stable test set?

MGnarfTest does **not** replace MGnarf's repository-owned tests. It adds an external/versioned layer for adversarial tests, frozen target bindings, execution receipts, review state, and later STABLE promotion.

## Current MGnarf baseline

Published stable release: **MGnarf v1.70**

Exact stable source commit:

```text
b811a13eab9cacd9f922b1f15097aa6bf700fc01
```

A test result must bind to an exact MGnarf commit. `main` alone is never sufficient evidence. The registry runner prepares each runnable manifest's exact target independently, so future MGnarf releases can coexist without sharing a moving checkout.

## Development versus STABLE

```text
DEV / PROPOSED
  -> executable test
  -> exact target SHA
  -> isolated CI execution
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

Two-review enforcement applies to STABLE promotion, not normal development.

The STABLE gate uses verifier code from the trusted base branch. It does **not** execute the promotion PR's code. A PR-generated receipt cannot be used as STABLE evidence; the evidence must come from a successful `main` push run for the exact tested subject commit.

## Trust-root status

Repository-local execution, receipt and promotion controls are evidence-tested. GitHub branch metadata currently reports `main` as **unprotected**, so MGnarfTest deliberately blocks STABLE promotion and does not claim that the trusted base branch is tamper-proof.

See [TRUST-BOUNDARY.md](TRUST-BOUNDARY.md) for the exact limitation and the requirements for a stronger STABLE trust claim.

## Current status

Twenty-six external tests are currently `PROPOSED`: stage ordering, same-operation replay resistance, builder/verifier identity separation, post-PASS frozen-state drift, post-PASS revocation, authenticated verifier-evidence tampering, frozen effect-binding substitution, post-PASS authority availability fail-closed behavior, authenticated final-decision tampering, frozen-task substitution, verifier binding/result fail-closed behavior, verifier producer crash/partial-execution fail-closed behavior, frozen-contract tamper resistance, frozen evidence-coverage completeness, host inhibitor invalidation before effect execution, trusted state-probe availability fail-closed behavior, post-PASS identity-probe continuity, protected-effect callback failure/retry at-most-once consumption, transient state drift during verifier execution, revocation arriving during verifier execution, identity principal/trust-domain drift during verifier execution, inhibitor dominance when introduced during verifier execution, verifier-profile drift in the trusted identity view or host binding during verifier execution, concurrent same-contract protected-effect race resistance, concurrent race resistance when the sole winning callback crashes, and multi-process same-filesystem effect-consumption race resistance. No external test is `STABLE` yet.

NARF principle: **no PASS without executed evidence; unavailable authority, state or identity is not permission; a stale or tampered decision is not authority; verified work authorizes only the exact frozen task, verifier contract, identity context and authenticated frozen contract; missing, duplicate or unknown evidence cannot satisfy frozen coverage; a verifier crash cannot be reinterpreted as PASS evidence; transient state, revocation, identity or verifier-profile drift during verification overrides producer PASS and cannot be erased afterward; a trusted inhibitor dominates verifier PASS evidence whether introduced before, during or after verification; a failed effect callback does not restore consumed effect authority; concurrent sessions or local processes sharing one frozen contract and receipt filesystem cannot multiply local effect authority, even when the sole winning callback crashes; no STABLE test without frozen identity, target, receipt, review evidence and an enforceable repository trust root.**
