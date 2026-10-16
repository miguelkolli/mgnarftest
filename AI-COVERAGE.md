# AI behavior coverage

This matrix tracks scenario-definition coverage only. `PROPOSED` means the scenario exists and validates; it does **not** mean the model behavior passed.

| Area | Scenario | Status |
|---|---|---|
| False PASS resistance | `MGTEST-AI-FALSEPASS-001/v1` | PROPOSED |
| Truth under user-pleasing pressure | `MGTEST-AI-PLEASURE-001/v1` | PROPOSED |
| Stale evidence recognition | `MGTEST-AI-STALEEVIDENCE-001/v1` | PROPOSED |
| Self-approval / independence claims | `MGTEST-AI-SELFAPPROVAL-001/v1` | PROPOSED |
| Tool-use honesty | `MGTEST-AI-TOOLHONESTY-001/v1` | PROPOSED |
| Authority / bypass pressure | `MGTEST-AI-AUTHORITY-001/v1` | PROPOSED |
| Scope drift | `MGTEST-AI-SCOPE-001/v1` | PROPOSED |
| Instruction conflict | `MGTEST-AI-CONFLICT-001/v1` | PROPOSED |
| Hidden-state assumptions | `MGTEST-AI-HIDDENSTATE-001/v1` | PROPOSED |
| Agent handoff integrity | `MGTEST-AI-HANDOFF-001/v1` | PROPOSED |
| Tool-result fabrication | `MGTEST-AI-TOOLFABRICATION-001/v1` | PROPOSED |

Current defined scenario count: **11**.

## Execution infrastructure

| Capability | Status |
|---|---|
| Single-evaluator repeated-run path | IMPLEMENTED / compatibility |
| Dual-evaluator fail-closed path | IMPLEMENTED |
| Independent dual-evidence verifier | IMPLEMENTED |
| Evidence-only cross-model comparison | IMPLEMENTED |
| Dual-evaluator live-readiness contract | IMPLEMENTED / live execution BLOCKED by trust root |
| Deterministic offline tool execution profile | IMPLEMENTED |
| Offline subject tool-call orchestration loop | IMPLEMENTED / mock-local adapters only |
| Independent offline tool-session verifier | IMPLEMENTED |
| OpenAI/Gemini live tool-calling adapters | DEFERRED |
| Real network-enabled tool profile | DEFERRED |

The cross-model comparator requires independently verified dual-evaluator bundles and does not produce a global PASS or automatic winner.

The offline tool path forces tool requests through MGnarfTest's deterministic executor. Tool results returned to the subject are bound to replay-verifiable receipts, and the standalone session verifier rejects fabricated/resealed transcript results that do not match the underlying tool receipts.

This is still execution infrastructure rather than live model evidence: the current OpenAI/Gemini provider adapters remain `tools=none`, and all current scenarios remain `PROPOSED` with model execution evidence `UNVERIFIED` until real repeated runs are executed and independently verified.

See `DEFERRED.md` for trust-root and credentialed/live execution work intentionally postponed while private-repository development continues.
