# AI Live-Run Readiness Gate v1

MGnarfTest must not expose provider credentials to mutable/untrusted workflow code. Before any live AI behavior run can be authorized, `tools/check_ai_live_readiness.py` validates the frozen scenario and produces a non-secret execution plan.

The readiness gate reuses the same canonical trust-root authority as STABLE promotion: `tools/enforce_trust_root.py`.

Current repository truth is intentionally fail-closed:

```text
TRUST_ROOT_STATUS = UNPROTECTED
STABLE_PROMOTION_ENABLED = false
```

Therefore current live-run readiness is `BLOCKED` even when the scenario, providers and run count are otherwise valid.

## What is checked

The gate requires:

- exact 40-hex MGnarfTest commit
- versioned AI scenario that passes the normal AI scenario validator
- requested runs >= frozen `minimum_runs`
- provider adapter supported by this repository
- provider-adapter v1 capability boundary: `tools=none`, model `network=false`
- obvious subject/evaluator same-provider+same-model alias collision is blocked before execution
- repository trust root must be explicitly enabled by the canonical trust-root authority

The plan records only provider/model names, adapter paths and the **names** of required secret environment variables. It never accepts or writes provider credential values.

## Manual readiness workflow

`.github/workflows/ai-live-readiness.yml` is a `workflow_dispatch` workflow with **no secrets**. It can be used to ask whether a proposed live run would be allowed by the current repository policy.

It writes `live-readiness.json` and uploads it even when readiness is BLOCKED, then fails the job if the gate did not return READY. This makes BLOCKED an auditable result instead of silently skipping the check.

This workflow is not a live model runner. No OpenAI/Gemini call is made and no API credential is referenced.

## Why live provider secrets are not wired yet

A live provider workflow would execute repository-controlled adapter/workflow code while holding credentials. With an unprotected trust root, a repository change could alter that code before a credentialed run. MGnarfTest therefore does not add the credentialed live-run workflow until the trust root is enforceable.

When the trust root is legitimately upgraded, the same canonical trust-root authority must be changed through its governed process. The readiness gate will then become eligible to return READY; that change alone still does not make any AI test STABLE.
