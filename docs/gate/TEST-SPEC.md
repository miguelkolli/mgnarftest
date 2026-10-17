# MGnarfTest Test Specification v1

Each test pack lives under `tests/<test-id>/v<version>/` and contains at minimum `manifest.json` plus its executable entrypoint.

The canonical schema is `schema/mgtest-manifest-v1.schema.json`. CI also runs `tools/validate_registry.py` fail-closed using only Python standard library. The executable validator mirrors the schema's closed-object policy: unknown top-level or nested manifest fields are rejected rather than silently ignored.

## Binding model

A stable result binds at minimum:

```text
test_id + test_version
+ test content / manifest hashes
+ exact MGnarf target commit
+ frozen expected condition
+ frozen allowed result set
+ successful main-push execution receipt
+ GitHub Actions run ID
+ artifact digest
+ tested subject commit
+ promotion PR number
+ exact promotion PR head approvals
+ reviewer A + reviewer B identities
```

`evidence.mgtest_commit` means the tested MGnarfTest subject commit that produced the receipt. STABLE evidence is eligible only when that exact commit was executed by the registry workflow from a successful `main` push.

`review.promotion_pr` means the separate GitHub pull-request number that requests STABLE acceptance. The exact reviewed head SHA is intentionally **not embedded in the manifest**, because embedding a commit's own SHA would create a self-referential hash cycle. GitHub's authenticated review history is the authority for the exact approved promotion head.

## Exact target preparation

The workflow does not select a single global MGnarf version. Each runnable manifest supplies its own exact `target.commit`.

Before any external test executes, `tools/prepare_targets.py` collects the unique runnable target SHAs, accepts only repository `miguelkolli/mgnarf`, fetches each exact 40-hex commit without using a branch as evidence identity, verifies `HEAD` equals the requested SHA, and prepares:

```text
targets/<exact-sha>/src
```

The isolated runner then mounts only the matching manifest target source read-only at `/target-src`. Tests targeting different MGnarf releases therefore cannot silently share a moving checkout. Duplicate manifests for the same exact commit reuse the one prepared target only after that preparation succeeded.

## Expected-result contract

Expected outcomes are frozen before execution. The current isolated runner maps a successful test-process exit (`0`) to the execution result `PASS`, so every runnable manifest must explicitly include `PASS` in `expected.allowed_results` before the test starts.

Execution receipts mirror the frozen `expected.allowed_results` list. Receipt verification requires that list to match the bound manifest exactly and rejects any receipt whose reported result is outside the frozen allowed set. Recomputing the receipt hash after changing the result does not bypass this semantic check.

## Manifest exactness

Manifest objects are closed contracts. Unknown fields are rejected at the top level and inside `target`, `expected`, `execution`, `review`, and `evidence`. The standard-library validator also enforces the schema's basic string/list/integer shapes so a field cannot be accepted merely because later code ignores it.

A future extension therefore requires an explicit schema/validator version change instead of an unreviewed extra field.

## Promotion separation

A test is first merged to `main` as non-STABLE and executed there. STABLE is requested later in a separate PR.

The promotion PR may change only the promoted manifest(s) plus [REGISTRY.md](../../REGISTRY.md). It may not change test code, workflow code, verifier code, target assumptions, expected conditions or other test semantics.

The trusted STABLE gate executes verifier code from the base branch and reads the promotion head through the GitHub API. It never executes code from the promotion PR.

## STABLE immutability

Once a manifest is `STABLE` on the base branch, an ordinary development or promotion PR may not modify it or move it back to another lifecycle state. This closes downgrade/demotion paths that would otherwise bypass the trusted promotion checks.

Retirement is intentionally not implemented as `STABLE -> RETIRED` through the normal development path. A future retirement mechanism must be its own trusted transition with explicit authority and evidence.

## IDs and versions

Recommended ID: `MGTEST-<PROJECT>-<AREA>-NNN`.

Increment `test_version` when attack logic, expected condition, evidence interpretation, privilege/trust assumptions or other material semantics change.

## Fail closed

Harness errors, missing dependencies, missing evidence, skipped required paths, invalid or structurally ambiguous manifests, duplicate IDs/versions, mutable or missing target identities, PR-only execution evidence, results outside the frozen allowed set, attempted STABLE downgrade or incomplete STABLE authorization are never automatically PASS.
