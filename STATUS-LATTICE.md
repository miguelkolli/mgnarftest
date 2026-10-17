# Repository-wide status lattice verifier

MGnarfTest uses several independent execution and governance paths. A local PASS or structurally valid record in one layer must never erase a blocking, unverified or unauthenticated state from another layer.

`tools/status_lattice_verifier.py` is an independent fail-closed regression verifier. It does not provide a shared status-policy function to the components it checks. Instead, it invokes their existing decision paths with synthetic degraded inputs and verifies that the result cannot become stronger.

Covered paths in v2:

- single-evaluator AI aggregate
- dual-evaluator AI aggregate
- receipt-backed tool-behavior aggregate
- cross-model comparison
- evidence acceptance lifecycle
- live-readiness planning
- STABLE-promotion trust-root guard

The verifier requires blocking aggregate conditions to remain `BLOCKED`, evaluator/runtime errors to remain non-PASS, inconclusive evidence to remain `UNVERIFIED`, critical violations to remain `FAIL`, comparison inputs that are blocked/unverified to remain `BLOCKED` or `LIMITED`, missing live-tool evidence to block `READY`, and an unprotected trust root to keep STABLE promotion disabled.

## Acceptance lifecycle boundary

The v2 verifier additionally exercises:

```text
PROPOSED
REVIEW-A
REVIEW-B
NEEDS-REVISION
REJECTED
ACCEPTED
```

`PROPOSED`, `REVIEW-A`, `REVIEW-B`, `NEEDS-REVISION` and `REJECTED` must remain non-authoritative. Synthetic attempts to relabel incomplete records as `ACCEPTED` are resealed and must still fail structural validation.

A fully formed `ACCEPTED` record may be `STRUCTURALLY_VALID`, but the current structural validator deliberately returns:

```text
authenticated_identity_verified = false
```

Therefore structural acceptance alone remains non-authoritative and is treated as `BLOCKED` by the lattice verifier. Only a future protected trust-root component may establish authenticated acceptance identity proof.

The prohibited strengthening set is:

```text
PASS
READY
STRONG
ACCEPTED
STABLE
```

when the tested input already contains a blocking, weaker-evidence or unauthenticated state.

This verifier is a regression boundary, not proof that every future status-bearing component is automatically covered. A new runner, comparator, readiness path, acceptance state or promotion mechanism must be added explicitly to the verifier and CI before it can claim repository-wide monotonicity coverage.

Current private-repository trust limits remain unchanged. Passing this verifier does not make live provider behavior verified, authenticate reviewers, or enable STABLE promotion.
