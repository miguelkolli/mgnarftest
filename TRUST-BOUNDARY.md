# MGnarfTest Trust Boundary

This document separates controls that MGnarfTest currently verifies from controls that depend on the GitHub repository trust root.

## Verified inside the repository

The current development/evidence pipeline verifies, fail-closed:

- exact MGnarf target commit identity per runnable manifest;
- isolated no-network, read-only, non-root test execution;
- CPU, memory, PID and per-test timeout limits;
- frozen expected-result semantics;
- bound execution receipts and tamper rejection;
- exact MGnarfTest subject commit identity;
- successful `main`-push evidence for STABLE eligibility;
- trusted STABLE verifier execution from the pull request base SHA;
- exact-head authenticated reviewer state, including review pagination;
- STABLE manifest immutability through the normal promotion path.

These controls do not by themselves make the repository's `main` branch an immutable trust root.

## Repository trust-root limitation

As observed on 2026-10-15 for the private `miguelkolli/mgnarftest` repository:

- the GitHub repository-rulesets API returned HTTP 403 and stated that the feature requires a GitHub plan upgrade or a public repository;
- the classic branch-protection API returned HTTP 403 (`Resource not accessible by integration`), so active branch protection cannot be independently verified through the current connection.

Therefore MGnarfTest must **not** claim that its trusted base branch is independently tamper-proof or that direct administrative mutation of `main` is technically impossible.

## Security consequence

The STABLE promotion workflow correctly uses `pull_request_target`, checks out the exact base SHA and never executes promotion-PR code. However, that protection ultimately trusts the verifier and workflow already present on `main`.

If an administrator can directly replace that trusted control-plane code on `main`, repository-local checks alone cannot prove that the trust root remained unchanged.

Current classification:

```text
development / execution evidence     PASS-capable
receipt / tamper controls            PASS-capable
trusted promotion implementation     PASS-capable
protected-main trust root             UNVERIFIED
strong tamper-proof STABLE claim      BLOCKED
```

No external test is currently `STABLE`.

## Required before a strong STABLE trust claim

Use at least one independently enforceable trust-root control, for example:

1. GitHub branch/ruleset protection on `main` requiring pull requests and the required checks, with direct/force pushes restricted; or
2. a separately governed trusted control-plane repository/authority whose policy cannot be modified by the same unreviewed path as the test proposal.

When such a control is enabled, record the exact enforcement configuration and evidence before changing the trust-root classification.

NARF rule: unavailable or unverifiable authority is not converted into PASS.
