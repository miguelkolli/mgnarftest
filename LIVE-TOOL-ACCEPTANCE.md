# Live Tool Evidence Acceptance v1

This contract governs the **lifecycle of an evidence artifact**. It is separate from the artifact's technical contents.

Authorization evidence answers whether a live provider tool-subject target is authorized. Capability evidence answers whether the exact provider/model/adapter contract was verified. An acceptance record answers whether that exact evidence artifact has progressed through the required review lifecycle.

## Lifecycle

```text
PROPOSED
   ↓
REVIEW-A
   ↓
REVIEW-B
   ↓
ACCEPTED
```

`NEEDS-REVISION` and `REJECTED` are non-promoted states for a revision. A material evidence change changes its hash and invalidates old review bindings.

## Review separation

For reviewed states:

- the author cannot be a reviewer;
- Reviewer A and Reviewer B must be different identities;
- each review binds the exact evidence SHA-256 and exact MGnarfTest commit;
- each review decision must be `APPROVED`.

`ACCEPTED` additionally requires both reviewers, an external reviewer identity among them, a positive accepted revision and a trust-root receipt SHA-256.

## Readiness v5 integration

Tool-enabled live readiness consumes two acceptance records:

- authorization-evidence acceptance record;
- capability-evidence acceptance record.

Each record must bind the exact raw evidence-file SHA-256, canonical evidence SHA-256 and target MGnarfTest commit. Missing records, non-`ACCEPTED` lifecycle states or binding mismatches fail closed.

A structurally valid `ACCEPTED` record is still **not sufficient for live READY** today. The standalone validator intentionally returns:

```text
STRUCTURALLY_VALID
authenticated_identity_verified = false
```

Therefore readiness v5 adds `...ACCEPTANCE_RECORD_IDENTITY_UNVERIFIED` blockers until a protected trust-root component verifies the referenced GitHub identities/reviews.

This prevents a self-authored JSON file from becoming live authority merely because it contains two reviewer names and a recomputed hash.

## Frozen record binding

The record binds:

- evidence kind (`authorization` or `capability`)
- exact evidence file SHA-256
- exact canonical evidence SHA-256
- exact target MGnarfTest commit
- author identity
- review A / review B identity + review ID + evidence/commit binding
- external reviewer identity for `ACCEPTED`
- accepted revision
- trust-root receipt hash
- canonical acceptance-record SHA-256

Changing any field without recomputing the record hash is rejected. Recomputing the hash does not bypass semantic review-separation or readiness binding rules.

## Current repository status

No live-tool evidence artifact is authenticated as accepted in the current private/unprotected repository state. The contract and readiness integration exist so that the later public/protected workflow has a frozen acceptance format and fail-closed boundary to enforce.
