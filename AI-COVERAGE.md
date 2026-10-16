# AI behavior coverage

This matrix tracks scenario-definition coverage only. `PROPOSED` means the scenario exists and validates; it does **not** mean the model behavior passed.

| Area | Scenario | Status |
|---|---|---|
| False PASS resistance | `MGTEST-AI-FALSEPASS-001/v1` | PROPOSED |
| Truth under user-pleasing pressure | `MGTEST-AI-PLEASURE-001/v1` | PROPOSED |
| Stale evidence recognition | `MGTEST-AI-STALEEVIDENCE-001/v1` | PROPOSED |
| Self-approval / independence claims | `MGTEST-AI-SELFAPPROVAL-001/v1` | PROPOSED |
| Tool-use honesty, prompt-only baseline | `MGTEST-AI-TOOLHONESTY-001/v1` | PROPOSED |
| Tool-use honesty, receipt-backed offline tool path | `MGTEST-AI-TOOLHONESTY-001/v2` | PROPOSED / EXECUTABLE |
| Authority / bypass pressure | `MGTEST-AI-AUTHORITY-001/v1` | PROPOSED |
| Scope drift | `MGTEST-AI-SCOPE-001/v1` | PROPOSED |
| Instruction conflict | `MGTEST-AI-CONFLICT-001/v1` | PROPOSED |
| Hidden-state assumptions | `MGTEST-AI-HIDDENSTATE-001/v1` | PROPOSED |
| Agent handoff integrity | `MGTEST-AI-HANDOFF-001/v1` | PROPOSED |
| Tool-result fabrication, prompt-only baseline | `MGTEST-AI-TOOLFABRICATION-001/v1` | PROPOSED |
| Tool-result fabrication, receipt-backed offline tool path | `MGTEST-AI-TOOLFABRICATION-001/v2` | PROPOSED / EXECUTABLE |

Current defined scenario versions: **13** across **11** test IDs.

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
| Frozen scenario -> tool-spec -> tool-session binding | IMPLEMENTED |
| Tool-enabled repeated-run + dual-evaluator aggregate path | IMPLEMENTED / mock-local adapters only |
| Independent tool-behavior aggregate verifier | IMPLEMENTED |
| OpenAI/Gemini normal evaluator support | IMPLEMENTED / mock-tested |
| OpenAI/Gemini receipt-backed tool-evaluator support | IMPLEMENTED / mock-tested |
| OpenAI/Gemini live subject tool-calling adapters | DEFERRED |
| Real network-enabled tool profile | DEFERRED |

Tool-enabled semantic evaluators receive only a serialized tool trace reconstructed from already verified MGnarfTest evidence. They do not execute or alter tools.

The repeated tool-behavior path runs the same frozen scenario at least its `minimum_runs`, verifies every tool/session/scenario bundle before semantic evaluation, sends the same final response and verified tool trace to Evaluator A and Evaluator B, applies fail-closed consensus, and seals an aggregate receipt.

Current provider-evaluator tests use mocked OpenAI/Gemini transport. No paid/live calls or provider secrets are used in CI. Live provider/model evidence remains `UNVERIFIED`.

See `TOOL-BEHAVIOR-AGGREGATE.md`, `PROVIDER-ADAPTERS.md`, and `DEFERRED.md` for the exact trust boundaries.
