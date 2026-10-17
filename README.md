# MGnarfTest

**Evidence first. Acceptance separately.**

MGnarfTest is the external test and evidence registry for [MGnarf](https://github.com/miguelkolli/mgnarf) and for AI behavior tests around truth, evidence, authority, scope, and tool use.

MGnarf and MGnarfTest have different jobs: **MGnarf is the fail-closed acceptance gate; MGnarfTest is the independent test registry around it.** MGnarfTest binds tests and evidence to exact targets, keeps test execution separate from acceptance, and fails closed when identity, evidence, authority, or repository trust is missing.

## Try it locally (no API keys)

Clone the public registry and run its local validation and promotion-gate regression tests:

```bash
git clone https://github.com/miguelkolli/mgnarftest.git
cd mgnarftest
python3 tools/validate_registry.py
python3 tools/validate_ai_behavior.py
python3 -m unittest -v tools.test_verify_stable_promotion_pr
```

These commands check manifests, AI scenarios, and **mocked promotion-policy attack cases**. They do **not** execute all 26 MGnarf gate tests, authenticate real external reviewers, or certify any AI model. The [registry CI workflow](.github/workflows/registry-validate.yml) runs the isolated target-bound gate tests and independently verifies execution receipts.

**One concrete attack/control example:** [MGTEST-NARF-EVIDENCE-001/v1](tests/MGTEST-NARF-EVIDENCE-001/v1/test.py) checks that a tampered verifier receipt produces `BLOCKED / INVALID_EVIDENCE` and never reaches the protected effect, while an untampered control produces `PASS` and reaches the effect exactly once. These are frozen test expectations; an actual PASS requires executed evidence.

**Want to submit a new adversarial test?** Follow the [external contributor quickstart](docs/contributing/EXTERNAL-TEST-QUICKSTART.md) (fork → versioned test → PR). Proposed tests and CI PASS results are not automatically STABLE.

## Start here

| I want to... | Read |
| --- | --- |
| see the current registry state | [REGISTRY.md](REGISTRY.md) |
| browse all technical documentation | [docs/README.md](docs/README.md) |
| add an external MGnarf test | [EXTERNAL-TEST-QUICKSTART.md](docs/contributing/EXTERNAL-TEST-QUICKSTART.md) |
| understand AI behavior tests | [AI-BEHAVIOR-SPEC.md](docs/ai/behavior/AI-BEHAVIOR-SPEC.md) |
| understand the repository trust boundary | [TRUST-BOUNDARY.md](docs/governance/TRUST-BOUNDARY.md) |
| understand fail-closed status transitions | [STATUS-LATTICE.md](docs/governance/STATUS-LATTICE.md) |
| see intentionally unresolved work | [DEFERRED.md](docs/governance/DEFERRED.md) |
| contribute safely | [CONTRIBUTING.md](.github/CONTRIBUTING.md) |
| report a vulnerability | [SECURITY.md](.github/SECURITY.md) |

## How MGnarf and MGnarfTest fit together

```text
AI / automation
      |
      v
produces candidate
      |
      v
verification / tests
      |
      v
    MGNARF
      |
      v
real effect

MGnarfTest
      |
      +--> external MGnarf gate tests
      +--> AI behavior tests
      +--> exact target identity
      +--> bound evidence
      +--> independent verification
      +--> review / acceptance
```

MGnarfTest is intentionally outside the MGnarf implementation. A test result is not inherited by a later commit, a mutable branch name is not a frozen target, and a CI PASS is not the same thing as acceptance into the STABLE set.

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

See [AI-BEHAVIOR-SPEC.md](docs/ai/behavior/AI-BEHAVIOR-SPEC.md) for the AI test contract.

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

See [TRUST-BOUNDARY.md](docs/governance/TRUST-BOUNDARY.md) for the exact trust model.

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
docs/contributing/EXTERNAL-TEST-QUICKSTART.md  external-contribution walkthrough
REGISTRY.md                 registry status and evidence summary
docs/ai/behavior/AI-BEHAVIOR-SPEC.md         AI behavior test contract
docs/governance/TRUST-BOUNDARY.md           repository trust-root model
docs/governance/STATUS-LATTICE.md           fail-closed status transition coverage
docs/governance/DEFERRED.md                 intentionally unresolved / future work
.github/CONTRIBUTING.md    contribution rules
.github/SECURITY.md        vulnerability reporting
```

## Contributing external tests

External tests are welcome. **First contribution? Start with [EXTERNAL-TEST-QUICKSTART.md](docs/contributing/EXTERNAL-TEST-QUICKSTART.md) and copy [`tests/_template/`](tests/_template/).**

The preferred model is:

1. fork the repository;
2. add a new test or a new version of an existing test;
3. bind it to an exact target and frozen expected semantics;
4. open a pull request;
5. let the required checks run;
6. respond to review;
7. the maintainer decides whether the proposal enters the official registry.

Do not treat a pull request, CI PASS, or fork as automatic acceptance into the official STABLE set. See [CONTRIBUTING.md](.github/CONTRIBUTING.md).

## License and security

MGnarfTest is licensed under the [Apache License 2.0](LICENSE). You may use, copy, modify, and redistribute the code under that license. That permission applies to your copies and forks; it does not grant write access to the official repository.

For vulnerability reporting, see [SECURITY.md](.github/SECURITY.md). Do not place credentials, private exploit details, or other secrets in a public issue.

## Core rule

> **No PASS without executed evidence. No STABLE without frozen identity, exact target, verified evidence, authenticated review, and an enforceable repository trust root.**

That rule is the point of MGnarfTest.