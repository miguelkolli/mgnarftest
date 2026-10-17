# I’m looking for two external reviewers to help complete MGnarfTest’s first real STABLE promotion

I’m building **MGnarfTest**, the external test and evidence layer around MGnarf.

MGnarf is the fail-closed acceptance gate. MGnarfTest lives in a separate repository on purpose: the thing being tested should not also be the only authority deciding that it passed.

The core rule is:

> **The system that creates and runs a test must not be the sole authority that declares it trusted.**

This is enforced in code.

A test can execute successfully and produce PASS evidence, but:

**Missing evidence is not PASS.**  
**PASS is not STABLE.**  
**A previous PASS is not permanent authority.**

The promotion path is:

```text
PROPOSED
   ↓
governed execution
   ↓
bound PASS evidence
   ↓
STABLE promotion PR
   ↓
exact-head review
   ↓
2 authenticated approvals
   ↓
trusted promotion gate
   ↓
STABLE
```

The STABLE verifier requires two distinct authenticated GitHub approvals on the **exact final promotion head**.

The test author and the promotion author do not count toward those two approvals.

So I can build the test, run it and produce the evidence, but **I cannot promote it to STABLE alone.**

That is intentional.

## Why I need you

MGnarfTest already has a first candidate with governed PASS evidence.

What is missing is the external review step.

I’m looking for **two people outside the project** willing to review the first STABLE promotion.

You do not need repository write access.

Your job is not to approve it because CI is green. Your job is to challenge the claim:

- Does the test really verify what it says?
- Is the exact target pinned?
- Does the evidence belong to this exact test and target?
- Are the limitations honest?
- Can you find a race, bypass, stale-evidence problem or bad assumption?

If something is wrong, **do not approve it**.

A finding that blocks STABLE is a useful result.

If the PR changes after review, the head changed and must be reviewed again.

## How to join

### Review the first STABLE promotion

Reply with your GitHub username.

I will open the dedicated promotion PR. Review the exact test, target, evidence and limitations, then either raise a finding or approve the exact final PR head.

### Or add your own adversarial test

Fork MGnarfTest and start from:

```text
tests/_template/
```

Define one thing you want to challenge, pin the exact target commit, define the failure path and safe condition, implement the test and open a PR.

New tests start as **PROPOSED**.

Do not invent PASS evidence. The governed execution path produces the evidence.

MGnarfTest:  
https://github.com/miguelkolli/mgnarftest

MGnarf:  
https://github.com/miguelkolli/mgnarf

**I can build the test and produce the evidence. MGnarfTest is deliberately designed so I cannot turn my own evidence into STABLE authority by myself.**
