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
| Cross-model comparison | multi-subject harness required | DEFERRED |

Current defined scenario count: **11**.

All current scenarios remain `PROPOSED` and model execution evidence remains `UNVERIFIED` until real repeated runs are executed and independently verified.

See `DEFERRED.md` for trust-root, live-provider and cross-model work intentionally postponed while private-repository development continues.
