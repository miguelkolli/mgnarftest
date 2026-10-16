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

`NEEDS-REVISION` and `REJECTED` are terminal/non-promoted states for a revision.

A material change to the evidence artifact changes its hash and therefore invalidates old review bindings.

## Review separation

For `REVIEW-A`, `REVIEW-B`, and `ACCEPTED`:

- the author cannot be a reviewer;
- Reviewer A and Reviewer B must be different identities;
- each review binds the exact evidence SHA-256 and exact MGnarfTest commit;
- each review decision must be `APPROVED`.

`ACCEPTED` additionally requires:

- both reviewers;
- an external reviewer identity that is one of the two approvers;
- a positive accepted revision;
- a trust-root receipt SHA-256.

## Important identity boundary

The standalone validator returns `STRUCTURALLY_VALID`. It **does not** claim that reviewer identities or review IDs were authenticated against GitHub.

That distinction is deliberate. A JSON file can describe reviewer identities, but it cannot prove that those people/accounts actually approved it.

When the repository trust root is later protected, a trusted promotion workflow must bind the acceptance record to real authenticated GitHub review state and produce the trust-root receipt required for `ACCEPTED`.

Until then, MGnarfTest must not claim that a structurally valid `ACCEPTED` record is independently authenticated acceptance.

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

Changing any field without recomputing the record hash is rejected. Recomputing the hash does not bypass semantic review-separation rules.

## Current repository status

No live-tool evidence artifact is being promoted to authenticated `ACCEPTED` in the current private/unprotected repository state. The contract and adversarial validator exist so that the later public/protected workflow has a frozen acceptance format to enforce.
