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

## Remaining trust-root gaps

The trusted STABLE verifier runs as job `trusted-promotion-gate` from `.github/workflows/two-review-gate.yml` using `pull_request_target` and the exact base SHA. It requires two authenticated exact-head approvals for STABLE promotion.

Two conditions still have to be completed in order:

1. the trusted workflow launcher on `main` must execute the Python package modules correctly; and
2. after that trusted-base job is observed PASS on a normal non-STABLE PR, `trusted-promotion-gate` must be added to the ruleset's required status checks.

RECON of run `39039267813` found that the previous launcher used `python3 tools/enforce_trust_root.py`, which failed before policy evaluation with `ModuleNotFoundError: No module named 'tools'`. The trusted workflow is therefore changed to module execution:

```text
python3 -m tools.enforce_trust_root
python3 -m tools.verify_stable_promotion_pr
```

Until this launcher fix is merged to `main` and a subsequent trusted-base run succeeds, making `trusted-promotion-gate` merge-required would risk blocking all pull requests rather than strengthening the trust root.

## Live ruleset verification

`tools/enforce_trust_root.py` contains a live GitHub ruleset verifier. For a STABLE request or any change to the trusted policy code itself, it requires all of the following before repository policy can be considered `PROTECTED`:

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

A normal development PR that does not request STABLE and does not change the trusted policy code does not need the live ruleset lookup. A PR that changes `tools/enforce_trust_root.py` or `.github/workflows/two-review-gate.yml` must pass the live ruleset verification from trusted base code before it can be treated as an authorized trust-policy change.

Unit regressions explicitly reject at least:

- an unprotected `main` branch;
- a missing `trusted-promotion-gate` requirement;
- any configured bypass actor;
- a non-strict status-check policy;
- live ruleset drift even if repository-local constants were hypothetically enabled;
- trust-policy changes while the live ruleset is incomplete.

## Machine-enforced current state

The repository-local activation constants intentionally remain:

```text
TRUST_ROOT_STATUS = UNPROTECTED
STABLE_PROMOTION_ENABLED = false
```

This is deliberate. The live validator and trusted launcher fix are being added before policy activation, so a partially configured trust root cannot become STABLE authority by documentation or assumption.

Normal PROPOSED/DEV pull requests remain allowed. A STABLE transition remains BLOCKED.

## Activation sequence

Before changing the constants above:

1. merge the live ruleset verifier and trusted module-launcher fix through the current protected PR path with `validate`, `ai-runner-selftest`, and `history-secret-scan` passing;
2. open the separate trust-root activation PR against the updated `main`; the fixed trusted-base job must execute and is expected to remain BLOCKED until the ruleset is complete;
3. add `trusted-promotion-gate` as a required GitHub Actions status check in the active `MGnarfTest main protection` ruleset;
4. rerun or retrigger the activation PR's trusted gate and require PASS, proving the four-check live policy from trusted base code;
5. confirm the ruleset still has no bypass actors, targets the default branch, and contains all four required checks;
6. only then merge the activation change that sets repository policy to `PROTECTED` and enables STABLE promotion;
7. rerun trusted control-plane tests, main-push evidence, and status-lattice regressions on the exact activation commit.

No external test is currently `STABLE`.

NARF rule: configuration that is missing, stale, bypassable, broken at launch, or not merge-enforced is not authority.
