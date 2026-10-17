# Repository-wide status lattice verifier

MGnarfTest uses several independent execution and governance paths. A local PASS in one layer must never erase a blocking or unverified state from another layer.

`tools/status_lattice_verifier.py` is an independent fail-closed regression verifier. It does not provide a shared status-policy function to the components it checks. Instead, it invokes their existing decision paths with synthetic degraded inputs and verifies that the result cannot become stronger.

Covered paths in v1:

- single-evaluator AI aggregate
- dual-evaluator AI aggregate
- receipt-backed tool-behavior aggregate
- cross-model comparison
- live-readiness planning
- STABLE-promotion trust-root guard

The verifier requires blocking aggregate conditions to remain `BLOCKED`, evaluator/runtime errors to remain non-PASS, inconclusive evidence to remain `UNVERIFIED`, critical violations to remain `FAIL`, comparison inputs that are blocked/unverified to remain `BLOCKED` or `LIMITED`, missing live-tool evidence to block `READY`, and an unprotected trust root to keep STABLE promotion disabled.

The prohibited strengthening set is:

```text
PASS
READY
STRONG
ACCEPTED
STABLE
```

when the tested input already contains a blocking or weaker-evidence state.

This verifier is a regression boundary, not proof that every future status-bearing component is automatically covered. A new runner, comparator, readiness path, acceptance state or promotion mechanism must be added explicitly to the verifier and CI before it can claim repository-wide monotonicity coverage.

Current private-repository trust limits remain unchanged. Passing this verifier does not make live provider behavior verified and does not enable STABLE promotion.
