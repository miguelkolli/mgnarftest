# MGnarfTest

**External tests, evidence, and acceptance for MGnarf and AI behavior.**

MGnarfTest is a public test registry designed to answer four questions:

> **What was tested? Against which exact target? What evidence was produced? Who accepted it?**

The repository is intentionally separate from MGnarf itself. MGnarf is the frozen target; MGnarfTest defines external tests, runs them against exact versions, records evidence, and keeps test acceptance separate from test execution.

## Why this exists

A test result such as “PASS” is weak if nobody can prove which code was tested, which test definition ran, whether the evidence was changed later, or who accepted the test into the trusted set.

MGnarfTest makes those boundaries explicit:

```text
test definition
    -> exact target identity
    -> isolated execution
    -> bound evidence / receipt
    -> independent verification
    -> review / acceptance
    -> optional STABLE promotion
```

A later change does not inherit an earlier PASS automatically. Missing authority or missing evidence fails closed.

## Two independent test planes

| Plane | Question | Location |
| --- | --- | --- |
| **MGnarf gate tests** | Does MGnarf enforce the protected-effect contract? | `tests/` |
| **AI behavior tests** | Does an AI/agent preserve truth, evidence, authority and scope under pressure? | `ai-tests/` |

These planes make different claims. A gate-test PASS does **not** prove model behavior. An AI-behavior PASS does **not** prove the MGnarf gate.

See [AI-BEHAVIOR-SPEC.md](AI-BEHAVIOR-SPEC.md) for the AI test contract.

## Current baseline

MGnarf gate tests currently target the published **MGnarf v1.70** source commit:

```text
b811a13eab9cacd9f922b1f15097aa6bf700fc01
```

A mutable branch name such as `main` is never sufficient target identity for evidence.

Current registry state:

| Area | State |
| --- | --- |
| External MGnarf gate tests | **26 PROPOSED** |
| AI behavior registry | **24 scenario versions / 11 test IDs, all PROPOSED** |
| Repository trust root | **PROTECTED** |
| STABLE promotion path | **enabled and fail-closed** |
| External tests currently STABLE | **0** |
| Credentialed real-provider AI behavior | **UNVERIFIED** |
| Real network-enabled effects | **DEFERRED** |

`PROTECTED` describes repository governance. It does **not** mean GPT, Gemini, Claude, or any other model has passed these tests.

## How a test becomes official

Normal development and STABLE acceptance are intentionally separate.

### 1. Propose a test

Anyone may fork this repository and propose a test through a pull request.

```text
fork
  -> add or version a test
  -> pull request
  -> required GitHub Actions checks
  -> maintainer decision
  -> merge as PROPOSED
```

Public does **not** mean writable. The official `miguelkolli/mgnarftest` repository has a protected `main` branch. External contributors cannot directly change `main`.

The active ruleset requires pull requests, an up-to-date branch, resolved review conversations, and these required checks:

- `validate`
- `ai-runner-selftest`
- `history-secret-scan`
- `trusted-promotion-gate`

Force-pushes and branch deletion are restricted, and the ruleset has no bypass actors.

### 2. Produce evidence on `main`

A PROPOSED gate test can run in the isolated registry harness. Evidence is bound to the exact MGnarfTest commit, exact target commit, test files, runtime contract, result, and receipt hash.

PR-generated evidence is not sufficient for STABLE promotion. STABLE evidence must come from the governed `main` path.

### 3. Promote separately to STABLE

STABLE promotion uses a dedicated PR with stricter rules:

```text
successful governed main evidence
    -> dedicated promotion PR
    -> trusted verifier from base main
    -> live repository-ruleset verification
    -> exact-head authenticated review A
    -> exact-head authenticated review B
    -> STABLE
```

The promotion PR may not silently change the test semantics it is promoting. If the repository trust root drifts, required checks disappear, or evidence/review bindings do not match, promotion is blocked.

See [TRUST-BOUNDARY.md](TRUST-BOUNDARY.md) for the exact trust model.

## What MGnarfTest verifies

The gate-test plane includes adversarial checks around areas such as replay resistance, frozen-state drift, revocation, identity and verifier drift, evidence tampering, effect binding, callback failure, concurrent races, and multi-process effect consumption.

The AI behavior plane includes scenarios for false PASS pressure, user-pleasing versus truth, stale evidence, self-approval, authority/scope conflicts, hidden state, handoff integrity, tool honesty, and tool-result fabrication. Some scenario versions add receipt-backed offline tools, deterministic final-claim binding, independent evidence verification, and distinct-provider evaluator requirements.

The repository also contains:

- exact-SHA target preparation and isolated execution;
- bound execution receipts and tamper rejection;
- repository-wide fail-closed status-lattice verification;
- dual-evaluator evidence verification;
- cross-model and multi-subject comparison tooling;
- OpenAI and Gemini provider adapters for the deferred/live evidence path;
- full Git-history high-confidence credential scanning;
- live GitHub ruleset verification before repository trust is used as authority.

## What a PASS does not mean

MGnarfTest deliberately keeps claims narrow.

A PASS does not automatically prove that:

- a different commit behaves the same way;
- a mutable model alias is equivalent to the tested model/version;
- a public benchmark reflects production behavior;
- two providers are epistemically or organizationally independent;
- structurally valid review JSON is authenticated human approval;
- offline deterministic tool tests authorize real network effects;
- repository protection alone proves AI behavior.

When required evidence is unavailable, the correct result is `BLOCKED`, `UNVERIFIED`, `FAIL`, or a documented limitation — not an invented PASS.

## Repository map

```text
tests/                     external MGnarf gate tests
tests/_template/           copyable external gate-test starter
ai-tests/                  AI behavior scenarios
adapters/                  provider adapters and tool bridges
tools/                     runners, validators and independent verifiers
evidence/                  generated/bound execution evidence
.github/workflows/         governed CI and promotion gates
EXTERNAL-TEST-QUICKSTART.md first external-contribution walkthrough
REGISTRY.md                 registry status and evidence summary
AI-BEHAVIOR-SPEC.md         AI behavior test contract
TRUST-BOUNDARY.md           repository trust-root model
STATUS-LATTICE.md           fail-closed status transition coverage
DEFERRED.md                 intentionally unresolved / future work
CONTRIBUTING.md             contribution rules
SECURITY.md                 vulnerability reporting
```

## Contributing external tests

External tests are welcome. **First contribution? Start with [EXTERNAL-TEST-QUICKSTART.md](EXTERNAL-TEST-QUICKSTART.md) and copy [`tests/_template/`](tests/_template/).**

The preferred model is:

1. fork the repository;
2. add a new test or a new version of an existing test;
3. bind it to an exact target and frozen expected semantics;
4. open a pull request;
5. let the required checks run;
6. respond to review;
7. the maintainer decides whether the proposal enters the official registry.

Do not treat a pull request, CI PASS, or fork as automatic acceptance into the official STABLE set. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License and security

MGnarfTest is licensed under the [Apache License 2.0](LICENSE). You may use, copy, modify, and redistribute the code under that license. That permission applies to your copies and forks; it does not grant write access to the official repository.

For vulnerability reporting, see [SECURITY.md](SECURITY.md). Do not place credentials, private exploit details, or other secrets in a public issue.

## Core rule

> **No PASS without executed evidence. No STABLE without frozen identity, exact target, verified evidence, authenticated review, and an enforceable repository trust root.**

That rule is the point of MGnarfTest.