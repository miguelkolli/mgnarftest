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

- GitHub branch metadata for `main` reported `protected: false`;
- the same branch response reported `protection.enabled: false` and required-status-check enforcement `off`;
- the repository-rulesets API returned HTTP 403 and stated that the feature requires a GitHub plan upgrade or a public repository;
- the classic branch-protection detail endpoint returned HTTP 403 (`Resource not accessible by integration`).

The branch metadata is sufficient to classify the current trust root as **UNPROTECTED**. MGnarfTest therefore must not claim that its trusted base branch is tamper-proof or that direct administrative mutation of `main` is technically prevented.

## Machine-enforced current state

The trusted `pull_request_target` workflow runs `tools/enforce_trust_root.py` from the exact base SHA before the STABLE promotion verifier.

Current constants are deliberately fail-closed:

```text
TRUST_ROOT_STATUS = UNPROTECTED
STABLE_PROMOTION_ENABLED = false
```

A normal PROPOSED/DEV pull request is allowed to continue. A pull request whose head requests `status=STABLE` is blocked before STABLE evidence/review acceptance while this trust-root state remains unresolved.

This lock prevents accidental STABLE acceptance through the normal workflow. It is not a substitute for protected `main`: an administrator capable of directly replacing trusted base code could also replace the lock. That is the unresolved external authority boundary.

## Security consequence

The STABLE promotion workflow correctly uses `pull_request_target`, checks out the exact base SHA and never executes promotion-PR code. However, that protection ultimately trusts the verifier and workflow already present on `main`.

Because `main` is currently unprotected, repository-local checks cannot prove that this trusted control-plane code cannot be replaced directly by an administrator.

Current classification:

```text
development / execution evidence     PASS-capable
receipt / tamper controls            PASS-capable
trusted promotion implementation     PASS-capable
normal STABLE promotion              BLOCKED
protected-main trust root             UNPROTECTED
strong tamper-proof STABLE claim      BLOCKED
```

No external test is currently `STABLE`.

## Required before enabling STABLE promotion

Use at least one independently enforceable trust-root control, for example:

1. enable GitHub branch/ruleset protection on `main` requiring pull requests and the required checks, with direct/force pushes restricted; or
2. move the trusted control plane to a separately governed repository/authority whose policy cannot be modified by the same unreviewed path as the test proposal.

Then record the exact enforcement configuration and evidence, change the trust-root classification to VERIFIED, enable STABLE promotion, and run the trusted control-plane tests before accepting any STABLE manifest.

NARF rule: absent enforcement is not converted into PASS.
