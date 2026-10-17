# Contribution and Review Policy

MGnarfTest accepts proposed tests from maintainers, external contributors, researchers, automated systems and AI-assisted workflows.

## Development flow

`PROPOSED`, `REVIEW-A`, `REVIEW-B`, `BLOCKED`, `REJECTED` and `NEEDS-REVISION` may be developed without the two-review gate blocking normal work.

Every test must declare a unique test ID/version, exact target repository and 40-hex commit SHA, frozen expected safe behavior, execution requirements, limitations and evidence state.

Missing execution, missing authority, missing dependencies or incomplete evidence is `BLOCKED`/`UNVERIFIED`, never PASS.

A PR execution may be useful development evidence, but it is not eligible STABLE evidence. A proposed test must first be merged without STABLE status and then execute successfully in the registry workflow from a `main` push.

## STABLE promotion

STABLE is an acceptance state, not a test result. Promotion is a separate PR after the tested PROPOSED version already exists on `main`.

A STABLE promotion PR may change only:

- the promoted test manifest(s); and
- [REGISTRY.md](../REGISTRY.md).

It may not change `test.py`, workflows, verifier tools, schemas, target assumptions or other executable code. The trusted promotion gate rejects mixed promotion/development PRs.

A STABLE promotion requires:

- exact target SHA;
- executed PASS evidence from a successful `main` push registry run;
- a bound receipt and GitHub artifact digest;
- tested subject commit recorded separately from the promotion commit;
- unchanged test semantics and unchanged `test.py` since the evidenced subject commit;
- trusted promotion verification using verifier code from the base branch, not the PR head;
- two authenticated GitHub approvals on the exact current promotion PR head;
- promotion author/test author excluded from the two counted approvals;
- manifest reviewer A and reviewer B matching authenticated exact-head approvers;
- no unresolved required findings.

Any new promotion commit invalidates prior exact-head approvals for MGnarfTest purposes.

The two-review rule is authorization evidence; it does not by itself prove scientific or organizational independence.

## Stable test changes

Material changes to attack logic, expected condition, evidence interpretation, target assumptions or trust boundaries require a new test version. Documentation-only corrections may retain a version only when semantics are unchanged.
