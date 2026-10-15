# MGnarfTest Test Specification v1

Each test pack lives under `tests/<test-id>/v<version>/` and contains at minimum `manifest.json` plus its executable entrypoint.

The canonical schema is `schema/mgtest-manifest-v1.schema.json`. CI also runs `tools/validate_registry.py` fail-closed using only Python standard library.

## Binding model

A stable result binds at minimum:

```text
test_id + test_version
+ test content / manifest hashes
+ exact MGnarf target commit
+ frozen expected condition
+ execution receipt
+ GitHub Actions run ID
+ artifact digest
+ tested subject commit
+ promotion commit
+ reviewer A + reviewer B identities
```

`evidence.mgtest_commit` means the tested MGnarfTest subject commit that produced the receipt.

`review.accepted_commit` means the later STABLE promotion PR head approved by reviewers. These are intentionally separate identities.

## IDs and versions

Recommended ID: `MGTEST-<PROJECT>-<AREA>-NNN`.

Increment `test_version` when attack logic, expected condition, evidence interpretation, privilege/trust assumptions or other material semantics change.

## Fail closed

Harness errors, missing dependencies, missing evidence, skipped required paths, invalid manifests, duplicate IDs/versions or incomplete STABLE authorization are never automatically PASS.
