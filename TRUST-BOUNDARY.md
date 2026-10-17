# MGnarfTest Trust Boundary

This document separates controls that MGnarfTest verifies inside the repository from controls enforced by GitHub as the repository trust root.

## Repository-local controls

The current development/evidence pipeline verifies, fail-closed:

- exact MGnarf target commit identity per runnable manifest;
- isolated no-network, read-only, non-root gate-test execution;
- frozen expected-result semantics;
- bound execution receipts and tamper rejection;
- exact MGnarfTest subject commit identity;
- successful `main`-push evidence for STABLE eligibility;
- trusted STABLE verifier execution from the pull request base SHA;
- exact-head authenticated reviewer state for STABLE promotion;
- STABLE manifest immutability through the normal promotion path.

These controls still depend on the GitHub `main` branch and its policy being an enforceable authority.

## GitHub trust-root RECON — 2026-10-17

The repository is public and GitHub currently reports `main` as `protected: true`.

Ruleset `MGnarfTest main protection` (observed ruleset id `25304585`) is active and targets the default branch. The observed configuration includes:

- no bypass actors;
- branch deletion restriction;
- non-fast-forward / force-push restriction;
- pull requests required before merge;
- conversation resolution required;
- strict/up-to-date required status checks;
- required GitHub Actions checks `validate`, `ai-runner-selftest`, and `history-secret-scan`.

This is materially stronger than the former private/unprotected state, but it is not yet sufficient for STABLE promotion authority.

## Remaining trust-root gap

The trusted STABLE verifier runs as job `trusted-promotion-gate` from `.github/workflows/two-review-gate.yml` using `pull_request_target` and the exact base SHA. It requires two authenticated exact-head approvals for STABLE promotion.

That job is not yet one of the ruleset's required status checks. Therefore GitHub does not yet require its PASS result as a merge condition.

MGnarfTest must remain fail-closed until `trusted-promotion-gate` is added to the ruleset's required checks.

## Live ruleset verification

`tools/enforce_trust_root.py` contains a live GitHub ruleset verifier. For a STABLE request it requires all of the following before repository policy can be considered `PROTECTED`:

```text
main protected = true
ruleset name = MGnarfTest main protection
ruleset enforcement = active
target = default branch
branch exclusions = none
bypass actors = none
deletions restricted = true
non-fast-forward pushes restricted = true
pull request rule present = true
conversation resolution = required
strict/up-to-date status policy = true
status checks enforced on creation = true
required GitHub Actions checks:
  validate
  ai-runner-selftest
  history-secret-scan
  trusted-promotion-gate
```

The verifier binds the required check source to the GitHub Actions integration id observed for the repository policy. Missing or weakened rules fail closed.

Unit regressions explicitly reject at least:

- an unprotected `main` branch;
- a missing `trusted-promotion-gate` requirement;
- any configured bypass actor;
- a non-strict status-check policy;
- live ruleset drift even if repository-local constants were hypothetically enabled.

## Machine-enforced current state

The repository-local activation constants intentionally remain:

```text
TRUST_ROOT_STATUS = UNPROTECTED
STABLE_PROMOTION_ENABLED = false
```

This is deliberate. The live validator is being added before policy activation, so a partially configured trust root cannot become STABLE authority by documentation or assumption.

Normal PROPOSED/DEV pull requests remain allowed. A STABLE transition remains BLOCKED.

## Activation sequence

Before changing the constants above:

1. add `trusted-promotion-gate` as a required GitHub Actions status check in the active `MGnarfTest main protection` ruleset;
2. confirm the ruleset still has no bypass actors and still targets the default branch;
3. merge the live ruleset verifier through the protected PR path with all required checks passing;
4. re-read the live ruleset and `main` branch metadata;
5. in a separate activation change, set the repository policy to `PROTECTED` and enable STABLE promotion;
6. rerun trusted control-plane tests and status-lattice regressions on the exact activation commit.

No external test is currently `STABLE`.

NARF rule: configuration that is missing, stale, bypassable, or not merge-enforced is not authority.
