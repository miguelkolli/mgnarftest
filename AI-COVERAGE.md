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

## Tool-enabled scenario contract

A scenario is tool-enabled only when:

- `execution.tools = offline-deterministic-tools-v1`
- `execution.network = false`
- a closed `tool_profile` object is present
- `tool_profile.profile = offline-deterministic-tools-v1`
- `tool_profile.max_steps` is 1..16
- `tool_profile.initial_state` matches the deterministic `kv` / `counters` state schema

`tools/tool_enabled_scenario.py` derives the offline tool-agent session spec directly from the frozen scenario, executes it through the existing receipt-backed tool agent, and writes a separate scenario receipt binding:

- exact scenario ID/version/hash
- exact derived tool-spec hash
- exact offline tool-session receipt hash
- MGnarfTest commit

The independent verifier rebuilds the tool spec from the scenario and verifies the underlying tool session before accepting the wrapper receipt. A scenario receipt cannot make a fabricated tool result valid.

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
| Tool-honesty v2 executable scenario | IMPLEMENTED / model evidence UNVERIFIED |
| Tool-fabrication v2 executable scenario | IMPLEMENTED / model evidence UNVERIFIED |
| OpenAI/Gemini live tool-calling adapters | DEFERRED |
| Real network-enabled tool profile | DEFERRED |

The cross-model comparator requires independently verified dual-evaluator bundles and does not produce a global PASS or automatic winner.

The offline tool path forces tool requests through MGnarfTest's deterministic executor. Tool results returned to the subject are bound to replay-verifiable receipts, and the standalone session verifier rejects fabricated/resealed transcript results that do not match the underlying tool receipts.

Executable means the scenario can traverse the deterministic tool path with a local/mock subject adapter and produce independently verifiable evidence. It does **not** mean GPT, Gemini, Claude or another live model passed the scenario.

See `DEFERRED.md` for trust-root and credentialed/live execution work intentionally postponed while private-repository development continues.
