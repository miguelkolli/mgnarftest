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

A test result must bind to an exact MGnarf commit. `main` alone is never sufficient evidence.

## Development versus STABLE

```text
DEV / PROPOSED
  -> executable test
  -> exact target SHA
  -> CI execution
  -> bound receipt
  -> receipt verification
  -> tamper rejection
  -> evidence artifact

STABLE promotion
  -> verified subject evidence
  -> promotion commit
  -> authenticated review A
  -> authenticated review B
  -> STABLE
```

Two-review enforcement applies to STABLE promotion, not normal development.

## Current status

Repository bootstrap is in progress. No external test is STABLE yet.

NARF principle: **no PASS without executed evidence; no STABLE test without frozen identity, target, receipt and review evidence.**
