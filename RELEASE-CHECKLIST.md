# RC1 Release Checklist

Candidate: `v1.0.0-rc1`

Status: **RELEASED — GitHub prerelease published 2026-10-17**

## Verified release readback

- Immutable release tag: `v1.0.0-rc1`.
- Exact tag target: `07beb66fe2be05963f5c8799afe2b9a5bdfbe750` (protected-`main` commit).
- Post-merge registry validation: **PASS**, run `#241` (GitHub Actions run `39042323878`).
- GitHub release: https://github.com/miguelkolli/mgnarftest/releases/tag/v1.0.0-rc1 — marked **prerelease**, not final.
- All external gate tests remain **PROPOSED** unless separately promoted through STABLE.
- Later commits on `main` do **not** alter the frozen RC1 tag or retroactively extend its test coverage.

The checklist below records the **historical prerelease acceptance requirements**. It is not an instruction to move or republish the immutable RC1 tag.

Preparation base commit: `0bccdd7079b229f5a5b9c889f452fa0542c17a72`

The release tag target is intentionally **not** frozen to the preparation base. The tag must point to the protected-`main` merge commit produced by the RC1 preparation PR after the repository's required checks succeed.

## Preconditions already satisfied

- repository is public;
- Apache-2.0 license is present;
- `SECURITY.md` is present;
- default branch is `main` and is protected;
- active repository ruleset targets the default branch;
- ruleset bypass list is empty;
- deletion and non-fast-forward protection are enforced;
- pull requests and resolved conversations are required;
- branches must be up to date before merge;
- required checks are `validate`, `ai-runner-selftest`, `history-secret-scan`, and `trusted-promotion-gate`;
- repository trust-root state is PROTECTED;
- STABLE promotion path is enabled and fail-closed;
- latest pre-preparation protected-main registry validation passed on commit `0bccdd7079b229f5a5b9c889f452fa0542c17a72` (run #239).

## RC1 release gate

RC1 may be published only when all of the following are true for the preparation PR and its resulting protected-main commit:

1. The PR changes release metadata only; no test semantics, runner, verifier, schema, workflow or MGnarf target code changes are mixed in.
2. The exact PR head passes all four required GitHub Actions checks.
3. The PR merges through the active ruleset without bypass.
4. The resulting protected `main` commit is recorded as the RC1 tag target.
5. The post-merge registry validation for that exact `main` commit completes successfully, including isolated tests, bound receipt verification and fail-closed tamper checks.
6. `VERSION` at the tag reads `1.0.0-rc1`.
7. `CHANGELOG.md` at the tag describes the candidate and its explicit claim limits.
8. The GitHub Release is created as a **prerelease**, not a final release.
9. The release body records the exact tag-target SHA and states that all external tests remain PROPOSED unless separately promoted through the STABLE process.
10. A final readback confirms the tag/release points to the intended commit and no later mutable branch name is substituted for the exact identity.

## Claim boundary

Publishing RC1 means the MGnarfTest registry/harness/governance release candidate completed its release gate. It does **not** mean:

- MGnarf itself was modified;
- all MGnarf behavior is proven correct;
- any AI provider/model has passed the behavior test plane;
- any external test has automatically become STABLE;
- deferred real-provider or network-enabled execution has been completed.

Final `v1.0.0` should wait for at least one real end-to-end STABLE promotion through the protected trust-root path.
