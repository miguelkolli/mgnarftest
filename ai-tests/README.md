# AI behavior tests

This directory contains versioned scenarios for testing AI/agent behavior around MGnarf-style truth, evidence, authority and scope constraints.

These scenarios do **not** replace `tests/`, which contains executable MGnarf gate tests bound to an exact MGnarf source commit.

Each scenario lives at:

```text
ai-tests/<test-id>/v<version>/scenario.json
```

Current proposed scenarios:

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

All current scenarios start as `PROPOSED` and model execution evidence is `UNVERIFIED`. A scenario definition is not a result.

See:

- `AI-BEHAVIOR-SPEC.md` for model binding, repeated-run requirements, evaluation language and external-review rules.
- `AI-COVERAGE.md` for the explicit coverage matrix.
- `DEFERRED.md` for trust-root, live-provider and multi-subject work intentionally postponed while private-repository development continues.
