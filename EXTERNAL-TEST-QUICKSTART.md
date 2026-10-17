# External Test Quickstart

This is the shortest supported path for an external contributor to propose a new MGnarf gate test without write access to the canonical repository.

## 1. Fork and branch

Fork `miguelkolli/mgnarftest` to your own GitHub account, then create a branch for one test only.

Example branch:

```text
test/replay-after-consumption
```

Do not request direct write access to the canonical repository. Contributions enter through pull requests.

## 2. Copy the template

Choose a unique test ID that matches the registry naming rule. Existing tests use names such as:

```text
MGTEST-NARF-EVIDENCE-001
```

Create version `v1` and copy the template files:

```bash
TEST_ID=MGTEST-NARF-YOURCASE-001
mkdir -p "tests/${TEST_ID}/v1"
cp tests/_template/manifest.template.json "tests/${TEST_ID}/v1/manifest.json"
cp tests/_template/test.template.py "tests/${TEST_ID}/v1/test.py"
```

Then replace every `MGTEST-NARF-YOURCASE-001` placeholder with your real test ID.

The template files themselves are intentionally named `*.template.*` so they are not discovered as runnable registry tests.

## 3. Freeze the target and expected safe behavior first

Before interpreting any result, edit `manifest.json` and record:

- a unique `test_id` and positive integer `test_version`;
- status `PROPOSED`;
- the exact target repository;
- the exact lower-case 40-hex target commit SHA;
- the failure mode or attack being tested;
- the safe condition that must hold;
- execution requirements and limitations.

For the current MGnarf v1.70 baseline, the frozen target is:

```text
repository: miguelkolli/mgnarf
release:    v1.70
commit:     b811a13eab9cacd9f922b1f15097aa6bf700fc01
```

A branch name such as `main` is not sufficient target identity.

For a new PROPOSED test, leave review promotion fields unset and evidence as:

```json
"result": "UNVERIFIED",
"run_id": null,
"artifact_hash": null,
"receipt_sha256": null,
"mgtest_commit": null,
"target_commit": null
```

Do not invent receipt hashes or main-run evidence in the proposal PR.

## 4. Implement the test

Replace the blocking skeleton in `test.py` with a real adversarial test.

A useful test normally contains both:

1. an attack/failure path that must not reach the protected effect; and
2. a control path showing that the expected valid case still works.

Exit with code `0` only when the test has actually verified its frozen safe condition. Missing dependencies, unsupported execution, incomplete assertions, or an unexecuted path must not be represented as PASS.

Prefer deterministic, offline tests. If your proposal needs network access, extra privileges, or external dependencies, declare them truthfully in the manifest. The repository may classify an unavailable execution path as BLOCKED/UNVERIFIED rather than PASS.

## 5. Run the local preflight

At minimum:

```bash
python3 tools/validate_registry.py
python3 -m py_compile "tests/${TEST_ID}/v1/test.py"
```

The GitHub registry workflow performs the authoritative isolated execution, receipt generation, receipt verification, tamper checks, and required repository checks.

## 6. Open the pull request

Push your branch to your fork and open a pull request against:

```text
miguelkolli/mgnarftest:main
```

Complete the repository pull-request template. Keep the change scoped to the proposed test and any documentation required to understand it.

A PR PASS is development evidence only. It is not STABLE evidence.

## 7. What happens after merge

If the maintainer accepts the proposal, it is merged as `PROPOSED`.

The test must then run successfully from the governed `main` push path. That run can produce the bound receipt and artifact evidence needed for a later STABLE decision.

STABLE is a separate acceptance step:

```text
external proposal
  -> PR
  -> merge as PROPOSED
  -> successful main-push evidence
  -> separate STABLE promotion PR
  -> trusted base verifier
  -> two authenticated exact-head approvals
  -> STABLE
```

The STABLE promotion PR may not change the test semantics or `test.py`; it is an evidence-and-acceptance transition, not another development PR.

See `CONTRIBUTING.md` and `TRUST-BOUNDARY.md` for the authoritative rules.
