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

A test result must bind to an exact MGnarf commit. `main` alone is never sufficient evidence. The registry runner now prepares each runnable manifest's exact target independently, so future MGnarf releases can coexist without sharing a moving checkout.

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

Repository-local execution, receipt and promotion controls are evidence-tested. The private repository's protected-`main` trust root is **not currently independently verified** through the available GitHub controls, so MGnarfTest does not claim that the trusted base branch is tamper-proof.

See [TRUST-BOUNDARY.md](TRUST-BOUNDARY.md) for the exact limitation and the requirements for a stronger STABLE trust claim.

## Current status

Two external tests are currently `PROPOSED`. No external test is `STABLE` yet.

NARF principle: **no PASS without executed evidence; no STABLE test without frozen identity, target, receipt and review evidence.**
