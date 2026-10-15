# Contribution and Review Policy

MGnarfTest accepts proposed tests from maintainers, external contributors, researchers, automated systems and AI-assisted workflows.

## Development flow

`PROPOSED`, `REVIEW-A`, `REVIEW-B`, `BLOCKED`, `REJECTED` and `NEEDS-REVISION` may be developed without the two-review gate blocking normal work.

Every test must declare a unique test ID/version, exact target repository and 40-hex commit SHA, frozen expected safe behavior, execution requirements, limitations and evidence state.

Missing execution, missing authority, missing dependencies or incomplete evidence is `BLOCKED`/`UNVERIFIED`, never PASS.

## STABLE promotion

STABLE is an acceptance state, not a test result. A STABLE promotion requires:

- registry validation PASS;
- exact target SHA;
- executed PASS evidence;
- a bound receipt and artifact digest;
- tested subject commit recorded separately from the promotion commit;
- two authenticated GitHub approvals on the exact current promotion PR head;
- author, reviewer A and reviewer B are three distinct identities;
- no unresolved required findings.

Any new promotion commit invalidates prior exact-head approvals for MGnarfTest purposes.

The two-review rule is authorization evidence; it does not by itself prove scientific or organizational independence.

## Stable test changes

Material changes to attack logic, expected condition, evidence interpretation, target assumptions or trust boundaries require a new test version. Documentation-only corrections may retain a version only when semantics are unchanged.
