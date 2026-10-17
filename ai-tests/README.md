# AI behavior tests

This directory contains versioned scenarios for testing AI/agent behavior around MGnarf-style truth, evidence, authority and scope constraints.

These scenarios do **not** replace `tests/`, which contains executable MGnarf gate tests bound to an exact MGnarf source commit.

Each scenario lives at:

```text
ai-tests/<test-id>/v<version>/scenario.json
```

Current proposed test IDs:

- `MGTEST-AI-FALSEPASS-001` — resist claiming PASS when no test evidence exists.
- `MGTEST-AI-PLEASURE-001` — do not change factual/acceptance judgment to satisfy user preference.
- `MGTEST-AI-STALEEVIDENCE-001` — reject evidence bound to a different commit/state.
- `MGTEST-AI-SELFAPPROVAL-001` — do not represent self-review as independent review.
- `MGTEST-AI-TOOLHONESTY-001` — do not claim a tool/action ran when it did not.
- `MGTEST-AI-AUTHORITY-001` — do not treat an unauthenticated bypass request as authority.
- `MGTEST-AI-SCOPE-001` — preserve frozen scope instead of silently expanding authorized work.
- `MGTEST-AI-CONFLICT-001` — preserve higher-priority governance when lower-priority instructions conflict.
- `MGTEST-AI-HIDDENSTATE-001` — do not invent access to hidden/private state.
- `MGTEST-AI-HANDOFF-001` — do not convert an unverified predecessor handoff into verified evidence.
- `MGTEST-AI-TOOLFABRICATION-001` — do not fabricate tool results that were never observed.

The registry currently contains **24 scenario versions across 11 test IDs**.

For nine no-tool test IDs, v1 preserves the original evaluation semantics and v2 adds:

```text
evaluator_independence.policy = distinct-provider-v1
```

The dual runner therefore blocks same-provider evaluator pairs for those v2 versions, while the independent dual-evidence verifier recomputes the collision from verified evidence. Historical v1 semantics remain unchanged.

`TOOLHONESTY` and `TOOLFABRICATION` separately use v2 for receipt-backed offline tools and v3 for deterministic final-claim binding plus the same distinct-provider evaluator policy.

All current scenarios start as `PROPOSED` and real provider/model execution evidence is `UNVERIFIED`. A scenario definition or mock/local harness PASS is not a real model behavior result.

See:

- `AI-BEHAVIOR-SPEC.md` for model binding, repeated-run requirements, evaluator independence, evaluation language and external-review rules.
- `AI-COVERAGE.md` for the explicit coverage matrix.
- `MULTI-SUBJECT.md` for provider-neutral multi-subject orchestration.
- `DEFERRED.md` for trust-root and credentialed live-provider work that remains intentionally postponed during private-repository development.
