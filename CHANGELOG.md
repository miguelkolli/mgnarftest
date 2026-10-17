# Changelog

All notable MGnarfTest release-level changes are recorded here.

## [1.0.0-rc1] - Unreleased

This release candidate establishes the first public, governed MGnarfTest release line. It is a release of the **test registry, evidence machinery and repository governance**, not a claim that any AI provider/model has passed the behavior plane and not a promotion of any external test to STABLE.

### Included

- public Apache-2.0 repository with security reporting guidance;
- 26 PROPOSED external MGnarf gate tests bound to exact MGnarf v1.70 source commit `b811a13eab9cacd9f922b1f15097aa6bf700fc01`;
- AI behavior plane with 24 versioned scenarios across 11 test IDs, all PROPOSED;
- deterministic offline tool execution and receipt-backed tool evidence;
- single- and dual-evaluator evidence paths with independent verification;
- distinct-provider evaluator collision checks for declared scenario versions;
- cross-model comparison and multi-subject orchestration with independent recomputation;
- OpenAI and Gemini provider adapters for deferred credentialed/live execution;
- exact-SHA subject binding, isolated registry execution, bound receipts and tamper rejection;
- repository-wide fail-closed status-lattice verification;
- full Git-history high-confidence credential scanning;
- public protected `main` trust root with live ruleset verification and no bypass actors;
- required GitHub Actions checks: `validate`, `ai-runner-selftest`, `history-secret-scan`, and `trusted-promotion-gate`;
- fail-closed STABLE promotion path using trusted base-branch verifier code and exact-head authenticated review evidence.

### Explicit limits

- no external test is STABLE yet;
- credentialed real-provider AI behavior remains UNVERIFIED;
- real network-enabled effects remain DEFERRED;
- harness/protocol PASS results do not imply GPT, Gemini, Claude or any other model has passed behavior evaluation;
- repository trust-root protection does not by itself prove model behavior;
- `v1.0.0-rc1` is a release candidate, not the final `v1.0.0` acceptance point.

### Release condition

The `v1.0.0-rc1` tag must point to the protected-`main` merge commit of the RC1 preparation PR, and that exact resulting `main` commit must complete the governed post-merge registry validation successfully before the prerelease is published.
