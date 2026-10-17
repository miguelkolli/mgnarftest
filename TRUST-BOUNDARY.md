# MGnarfTest Trust Boundary

This document separates controls that MGnarfTest verifies inside the repository from controls enforced by GitHub as the repository trust root.

## Repository-local controls

The development/evidence pipeline verifies, fail-closed:

- exact MGnarf target commit identity per runnable manifest;
- isolated no-network, read-only, non-root gate-test execution;
- frozen expected-result semantics;
- bound execution receipts and tamper rejection;
- exact MGnarfTest subject commit identity;
- successful `main`-push evidence for STABLE eligibility;
- trusted STABLE verifier execution from the pull request base SHA;
- exact-head authenticated reviewer state for STABLE promotion;
- STABLE manifest immutability through the normal promotion path.

## GitHub trust root

The repository is public and `main` is protected by the repository ruleset `MGnarfTest main protection` (observed ruleset id `25304585`). MGnarfTest does not infer authority from visibility alone.

The trusted base-branch verifier requires the live ruleset to remain active and to enforce:

```text
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

The required check source is bound to the GitHub Actions integration id observed for this repository policy. Missing or weakened rules fail closed.

A normal development PR that does not request STABLE and does not change trusted policy code may proceed through the normal required checks. A PR that changes `tools/enforce_trust_root.py` or `.github/workflows/two-review-gate.yml` must additionally pass live ruleset verification from trusted base code. A STABLE request must pass the same live verification and the separate evidence/review promotion verifier.

## Activation authority

Repository policy is configured as:

```text
TRUST_ROOT_STATUS = PROTECTED
STABLE_PROMOTION_ENABLED = true
```

These constants are not self-authenticating. A change to them is itself a trust-policy change, so the trusted base workflow checks the live four-check ruleset before GitHub can merge the activation PR. If the ruleset later drifts, future STABLE requests and future trust-policy changes fail closed even though the constants still say `PROTECTED`.

The activation claim is limited to repository governance. It does not prove any AI provider/model behavior and does not authenticate the still-deferred live-tool evidence-acceptance records.

## STABLE promotion boundary

A STABLE promotion is a separate PR. The trusted workflow checks out the exact base SHA rather than the promotion PR's code. The promotion verifier requires successful main-push evidence for the exact subject commit plus two authenticated exact-head approvals excluding the test author and PR author. AI behavior STABLE additionally requires the declared external-review boundary.

No external test is automatically promoted by repository activation. At activation time, all existing external tests remain `PROPOSED` until an independent STABLE promotion satisfies the full promotion contract.

## Residual trust assumptions

GitHub remains the hosting and identity authority for branch rules, check identities and authenticated reviews. Required status checks are bound to check context plus GitHub Actions integration; they are not a cryptographic identity for the workflow file itself. The trusted `pull_request_target` job reduces untrusted-head influence by checking out exact trusted base code, but repository-owner control of GitHub settings remains an ultimate administrative authority.

NARF rule: configuration that is missing, stale, bypassable, broken at launch, or not merge-enforced is not authority.
