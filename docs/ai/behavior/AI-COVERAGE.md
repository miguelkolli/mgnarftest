# AI behavior coverage

`PROPOSED` means a scenario exists and validates; it does **not** mean a live model passed.

| Area | Scenario | Status |
|---|---|---|
| False PASS resistance, original semantics | `MGTEST-AI-FALSEPASS-001/v1` | PROPOSED |
| False PASS resistance, distinct-provider evaluators | `MGTEST-AI-FALSEPASS-001/v2` | PROPOSED / EXECUTABLE |
| Truth under user-pleasing pressure, original semantics | `MGTEST-AI-PLEASURE-001/v1` | PROPOSED |
| Truth under user-pleasing pressure, distinct-provider evaluators | `MGTEST-AI-PLEASURE-001/v2` | PROPOSED / EXECUTABLE |
| Stale evidence recognition, original semantics | `MGTEST-AI-STALEEVIDENCE-001/v1` | PROPOSED |
| Stale evidence recognition, distinct-provider evaluators | `MGTEST-AI-STALEEVIDENCE-001/v2` | PROPOSED / EXECUTABLE |
| Self-approval / independence claims, original semantics | `MGTEST-AI-SELFAPPROVAL-001/v1` | PROPOSED |
| Self-approval / independence claims, distinct-provider evaluators | `MGTEST-AI-SELFAPPROVAL-001/v2` | PROPOSED / EXECUTABLE |
| Tool-use honesty, prompt baseline | `MGTEST-AI-TOOLHONESTY-001/v1` | PROPOSED |
| Tool-use honesty, receipt-backed offline tools | `MGTEST-AI-TOOLHONESTY-001/v2` | PROPOSED / EXECUTABLE |
| Tool-use honesty, deterministic final claim binding | `MGTEST-AI-TOOLHONESTY-001/v3` | PROPOSED / EXECUTABLE |
| Authority / bypass pressure, original semantics | `MGTEST-AI-AUTHORITY-001/v1` | PROPOSED |
| Authority / bypass pressure, distinct-provider evaluators | `MGTEST-AI-AUTHORITY-001/v2` | PROPOSED / EXECUTABLE |
| Scope drift, original semantics | `MGTEST-AI-SCOPE-001/v1` | PROPOSED |
| Scope drift, distinct-provider evaluators | `MGTEST-AI-SCOPE-001/v2` | PROPOSED / EXECUTABLE |
| Instruction conflict, original semantics | `MGTEST-AI-CONFLICT-001/v1` | PROPOSED |
| Instruction conflict, distinct-provider evaluators | `MGTEST-AI-CONFLICT-001/v2` | PROPOSED / EXECUTABLE |
| Hidden-state assumptions, original semantics | `MGTEST-AI-HIDDENSTATE-001/v1` | PROPOSED |
| Hidden-state assumptions, distinct-provider evaluators | `MGTEST-AI-HIDDENSTATE-001/v2` | PROPOSED / EXECUTABLE |
| Agent handoff integrity, original semantics | `MGTEST-AI-HANDOFF-001/v1` | PROPOSED |
| Agent handoff integrity, distinct-provider evaluators | `MGTEST-AI-HANDOFF-001/v2` | PROPOSED / EXECUTABLE |
| Tool-result fabrication, prompt baseline | `MGTEST-AI-TOOLFABRICATION-001/v1` | PROPOSED |
| Tool-result fabrication, receipt-backed offline tools | `MGTEST-AI-TOOLFABRICATION-001/v2` | PROPOSED / EXECUTABLE |
| Tool-result fabrication, deterministic final claim binding | `MGTEST-AI-TOOLFABRICATION-001/v3` | PROPOSED / EXECUTABLE |

Current scenario versions: **24** across **11** test IDs.

## Execution infrastructure

| Capability | Status |
|---|---|
| Single-evaluator repeated-run path | IMPLEMENTED / compatibility |
| Dual-evaluator fail-closed path | IMPLEMENTED |
| Independent dual-evidence verifier | IMPLEMENTED |
| Scenario-bound distinct-provider evaluator rule | IMPLEMENTED / no-tool v2 + tool v3 |
| Independent provider-collision recomputation | IMPLEMENTED |
| Evidence-only cross-model comparison | IMPLEMENTED |
| Provider-neutral multi-subject orchestration | IMPLEMENTED / mock-local |
| Independent multi-subject evidence verifier | IMPLEMENTED |
| Live-readiness plan v5 | IMPLEMENTED / fail-closed |
| No-tool provider readiness | IMPLEMENTED / BLOCKED by current trust root |
| Receipt-backed provider tool-subject readiness | IMPLEMENTED / acceptance-auth BLOCKED |
| Live tool authorization evidence validator | IMPLEMENTED |
| Provider/model tool capability evidence validator | IMPLEMENTED |
| Evidence acceptance lifecycle validator | IMPLEMENTED / structural only |
| Acceptance-record binding in readiness | IMPLEMENTED |
| Authenticated GitHub acceptance proof | DEFERRED / trust-root dependent |
| Deterministic offline tool execution profile | IMPLEMENTED |
| Offline subject tool-call orchestration | IMPLEMENTED |
| Independent offline tool-session verifier | IMPLEMENTED |
| Frozen scenario -> tool spec -> tool session binding | IMPLEMENTED |
| Tool-enabled repeated-run + dual-evaluator aggregate | IMPLEMENTED / mock-local subject |
| Independent tool-behavior aggregate verifier | IMPLEMENTED |
| Deterministic receipt-result -> final-claim binding | IMPLEMENTED / v3 tool scenarios |
| BLOCKED-status monotonicity regression | IMPLEMENTED / tool aggregate |
| Repository-wide status-lattice verifier | IMPLEMENTED / CI |
| OpenAI/Gemini normal evaluator support | IMPLEMENTED / mock-tested |
| OpenAI/Gemini receipt-backed tool-evaluator support | IMPLEMENTED / mock-tested |
| OpenAI/Gemini offline-tool subject translation bridge | IMPLEMENTED / mock-tested |
| Provider-native continuation evidence binding | IMPLEMENTED / mock-tested |
| Credentialed live provider subject tool execution | DEFERRED / readiness BLOCKED |
| Credentialed live multi-subject execution | DEFERRED / trust-root dependent |
| Real network-enabled effect profile | DEFERRED |

`distinct-provider-v1` is versioned scenario policy. It is present in the nine no-tool v2 scenarios and the two tool v3 scenarios. Same-provider evaluator pairs add `EVALUATOR_PROVIDER_COLLISION` and force the aggregate to `BLOCKED`. The independent dual-evidence verifier recomputes the provider comparison from verified evaluator bindings, so resealing an aggregate without the blocker cannot create PASS evidence.

Historical no-tool v1 scenarios intentionally retain their original evaluation semantics; they are not silently upgraded by this change.

Readiness v5 binds the exact scenario hash, readiness-gate hash and provider/evaluator adapter hashes. Tool-enabled scenarios additionally require exact-bound authorization evidence, capability evidence, and an acceptance record for each evidence artifact.

A missing or non-`ACCEPTED` acceptance record blocks readiness. A structurally valid `ACCEPTED` record also remains blocked until reviewer identity is authenticated by a protected trust-root component. This means self-authored reviewer names cannot unlock live tool execution.

The provider subject bridge binds exact provider-native continuation context into the offline tool transcript and session receipt. OpenAI output/reasoning items and Gemini returned model Parts are preserved rather than reconstructed before receipt-backed tool results are returned.

The v3 tool scenarios add a frozen `claims-only-v1` contract. The independent verifier recomputes the exact expected `OBSERVED <label>=<value>` lines from the receipt-backed tool trace. A model cannot obtain a PASS merely because both semantic evaluators incorrectly call a false final claim compliant.

The multi-subject path reuses independently verified dual-evaluator bundles and the existing evidence-only comparator. Its orchestration receipt is separately sealed and independently recomputed; live credentialed execution remains blocked by the current trust root.

This is still protocol/evidence infrastructure. Live provider behavior remains `UNVERIFIED` until credentialed repeated execution is governed and independently verified.

See [MULTI-SUBJECT.md](../execution/MULTI-SUBJECT.md), [STATUS-LATTICE.md](../../governance/STATUS-LATTICE.md), [LIVE-TOOL-EVIDENCE.md](../evidence/LIVE-TOOL-EVIDENCE.md), [LIVE-TOOL-ACCEPTANCE.md](../evidence/LIVE-TOOL-ACCEPTANCE.md), [PROVIDER-ADAPTERS.md](../execution/PROVIDER-ADAPTERS.md), [TOOL-BEHAVIOR-AGGREGATE.md](../evidence/TOOL-BEHAVIOR-AGGREGATE.md), and [DEFERRED.md](../../governance/DEFERRED.md) for the trust boundaries.
