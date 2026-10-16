# AI behavior tests

This directory contains versioned scenarios for testing AI/agent behavior around MGnarf-style truth, evidence, authority and scope constraints.

These scenarios do **not** replace `tests/`, which contains executable MGnarf gate tests bound to an exact MGnarf source commit.

Each scenario lives at:

```text
ai-tests/<test-id>/v<version>/scenario.json
```

Current initial core scenarios:

- `MGTEST-AI-FALSEPASS-001` — resist claiming PASS when no test evidence exists.
- `MGTEST-AI-PLEASURE-001` — do not change factual/acceptance judgment to satisfy user preference.
- `MGTEST-AI-STALEEVIDENCE-001` — reject evidence bound to a different commit/state.
- `MGTEST-AI-SELFAPPROVAL-001` — do not represent self-review as independent review.
- `MGTEST-AI-TOOLHONESTY-001` — do not claim a tool/action ran when it did not.
- `MGTEST-AI-AUTHORITY-001` — do not treat an unauthenticated bypass request as authority.

All six start as `PROPOSED` and `UNVERIFIED` with no execution evidence. A scenario definition is not a result.

See `AI-BEHAVIOR-SPEC.md` for model binding, repeated-run requirements, evaluation language and external-review rules.
