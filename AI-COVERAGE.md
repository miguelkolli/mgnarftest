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

`tools/tool_enabled_scenario.py` derives the offline tool-agent session spec directly from the frozen scenario, executes it through the receipt-backed tool agent, and writes a separate scenario receipt binding the exact scenario, derived spec, tool session and MGnarfTest commit.

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
| Tool-enabled repeated-run + dual-evaluator aggregate path | IMPLEMENTED / mock-local adapters only |
| Independent tool-behavior aggregate verifier | IMPLEMENTED |
| OpenAI/Gemini live tool-calling adapters | DEFERRED |
| Real network-enabled tool profile | DEFERRED |

The repeated tool-behavior path runs the same frozen scenario at least its `minimum_runs`, verifies every tool/session/scenario bundle before semantic evaluation, sends the same final response and verified tool trace to Evaluator A and Evaluator B, applies fail-closed consensus, and seals an aggregate receipt.

A `PASS` from that aggregate is meaningful only for the exact bound scenario, adapters, evaluator identities, MGnarfTest commit and subject model identity. Current CI uses local/mock subject and evaluator adapters; it is not live GPT/Gemini/Claude evidence.

The independent aggregate verifier re-verifies every underlying tool session, tool trace, response hash, evaluator reason hash, consensus decision, run count, identity binding, limitation set and final aggregate result. Resealing a false aggregate result is rejected.

See `TOOL-BEHAVIOR-AGGREGATE.md` for the execution/evidence contract and `DEFERRED.md` for trust-root and credentialed/live execution work.
