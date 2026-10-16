# AI behavior coverage

`PROPOSED` means a scenario exists and validates; it does **not** mean a live model passed.

| Area | Scenario | Status |
|---|---|---|
| False PASS resistance | `MGTEST-AI-FALSEPASS-001/v1` | PROPOSED |
| Truth under user-pleasing pressure | `MGTEST-AI-PLEASURE-001/v1` | PROPOSED |
| Stale evidence recognition | `MGTEST-AI-STALEEVIDENCE-001/v1` | PROPOSED |
| Self-approval / independence claims | `MGTEST-AI-SELFAPPROVAL-001/v1` | PROPOSED |
| Tool-use honesty, prompt baseline | `MGTEST-AI-TOOLHONESTY-001/v1` | PROPOSED |
| Tool-use honesty, receipt-backed offline tools | `MGTEST-AI-TOOLHONESTY-001/v2` | PROPOSED / EXECUTABLE |
| Authority / bypass pressure | `MGTEST-AI-AUTHORITY-001/v1` | PROPOSED |
| Scope drift | `MGTEST-AI-SCOPE-001/v1` | PROPOSED |
| Instruction conflict | `MGTEST-AI-CONFLICT-001/v1` | PROPOSED |
| Hidden-state assumptions | `MGTEST-AI-HIDDENSTATE-001/v1` | PROPOSED |
| Agent handoff integrity | `MGTEST-AI-HANDOFF-001/v1` | PROPOSED |
| Tool-result fabrication, prompt baseline | `MGTEST-AI-TOOLFABRICATION-001/v1` | PROPOSED |
| Tool-result fabrication, receipt-backed offline tools | `MGTEST-AI-TOOLFABRICATION-001/v2` | PROPOSED / EXECUTABLE |

Current scenario versions: **13** across **11** test IDs.

## Execution infrastructure

| Capability | Status |
|---|---|
| Single-evaluator repeated-run path | IMPLEMENTED / compatibility |
| Dual-evaluator fail-closed path | IMPLEMENTED |
| Independent dual-evidence verifier | IMPLEMENTED |
| Evidence-only cross-model comparison | IMPLEMENTED |
| Live-readiness plan v3 | IMPLEMENTED / fail-closed |
| No-tool provider readiness | IMPLEMENTED / BLOCKED by current trust root |
| Receipt-backed provider tool-subject readiness | IMPLEMENTED / BLOCKED by authority + capability + trust root |
| Deterministic offline tool execution profile | IMPLEMENTED |
| Offline subject tool-call orchestration | IMPLEMENTED |
| Independent offline tool-session verifier | IMPLEMENTED |
| Frozen scenario -> tool spec -> tool session binding | IMPLEMENTED |
| Tool-enabled repeated-run + dual-evaluator aggregate | IMPLEMENTED / mock-local subject |
| Independent tool-behavior aggregate verifier | IMPLEMENTED |
| OpenAI/Gemini normal evaluator support | IMPLEMENTED / mock-tested |
| OpenAI/Gemini receipt-backed tool-evaluator support | IMPLEMENTED / mock-tested |
| OpenAI/Gemini offline-tool subject translation bridge | IMPLEMENTED / mock-tested |
| Provider-native continuation evidence binding | IMPLEMENTED / mock-tested |
| Credentialed live provider subject tool execution | DEFERRED / readiness BLOCKED |
| Real network-enabled effect profile | DEFERRED |

Readiness v3 binds the exact scenario hash, readiness-gate hash and provider/evaluator adapter hashes. For tool-enabled scenarios it also freezes the provider-specific tool-subject contract and the `provider-native-context-chain-v1` continuation evidence contract.

A tool-enabled plan cannot become `READY` merely because the repository trust root is later protected. It additionally requires explicit governance authorization for live provider tool-subject execution and verification of the exact provider/model tool capability. These are separate fail-closed blockers.

The provider subject bridge binds exact provider-native continuation context into the offline tool transcript and session receipt. OpenAI output/reasoning items and Gemini returned model Parts are preserved rather than reconstructed before receipt-backed tool results are returned.

This is still protocol/evidence infrastructure. Live provider tool behavior remains `UNVERIFIED` until credentialed repeated execution is governed and independently verified.

See `PROVIDER-ADAPTERS.md`, `TOOL-BEHAVIOR-AGGREGATE.md`, and `DEFERRED.md` for the trust boundaries.
