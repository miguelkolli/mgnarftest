## MGnarfTest submission

### Change type

- [ ] DEV / PROPOSED test development
- [ ] STABLE promotion only

### Test identity

- Test ID:
- Test version:
- Current/requested status:

### Exact target

- Project/repository:
- Release/tag:
- Exact target commit SHA:

### What is being tested?

Describe the failure mode, attack, invariant, or boundary.

### Frozen expected outcome

State the expected safe behavior **before** interpreting run results.

### Execution / evidence

- Entrypoint/command:
- Required privileges:
- Network required: yes/no
- Main-push run ID (required for STABLE):
- Artifact SHA-256 (required for STABLE):
- Receipt SHA-256 (required for STABLE):
- Tested MGnarfTest subject SHA (required for STABLE):

### Limits

What does this test explicitly **not** prove?

### DEV declaration

- [ ] Missing/skipped/unexecutable required paths are not represented as PASS.
- [ ] Material test changes will create a new test version when required.

### STABLE promotion declaration

For a STABLE promotion:

- [ ] The test already exists on `main` as non-STABLE.
- [ ] Evidence comes from a successful `main` push, not a PR run.
- [ ] This PR changes only the promoted manifest(s) and `REGISTRY.md`.
- [ ] `review.promotion_pr` equals this GitHub PR number.
- [ ] Review A and Review B are authenticated approvals on the exact current PR head.
- [ ] Test author/promotion author do not count toward the two approvals.

Do not merge as STABLE until the trusted base-branch promotion gate passes.
