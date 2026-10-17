# Offline Tool Execution Profile v1

MGnarfTest needs a controlled tool layer before any AI model is allowed to exercise real tools or external effects.

`tools/offline_tool_profile.py` provides a deterministic, no-network, no-shell execution substrate for tool-enabled AI behavior runs.

## Boundary

Profile ID:

```text
offline-deterministic-tools-v1
```

Allowed tools:

- `kv.get(key)`
- `kv.put(key, value)`
- `counter.increment(name)`

There is no filesystem tool, shell tool, subprocess execution, HTTP client or network capability in this profile.

Shell-looking strings are treated only as data.

## Fail-closed rules

Before execution starts, the full plan is validated. The profile blocks on:

- unknown tools
- malformed arguments
- duplicate call IDs
- more than 32 calls
- malformed initial state
- schema/profile mismatch

Because validation happens before the first call, an invalid later call cannot leave a partial state mutation behind.

## Evidence

A sealed `mgtest.ai.offline-tool-execution` receipt binds:

- profile ID
- complete plan hash
- initial-state hash
- each call ID and tool
- arguments hash
- before-state hash
- deterministic result + result hash
- after-state hash
- final-state hash
- call count
- explicit `network = false`
- explicit `shell = false`

`verify_execution()` does not trust the stored results. It replays the frozen plan from the same initial state and requires the entire semantic receipt to match.

Changing a tool result and resealing the receipt is therefore rejected.

## Subject tool-agent loop

`tools/offline_tool_agent.py` now exposes this profile to a subject adapter through a controlled multi-turn protocol:

```text
subject tool request
    -> MGnarfTest executor
    -> sealed tool receipt
    -> receipt-backed result
    -> next subject turn
```

The subject adapter never supplies its own tool result. MGnarfTest executes the requested call and only the executor result is added to the next-turn history.

The loop fails closed on unsupported tools, duplicate call IDs, adapter drift, subject identity/parameter drift, malformed responses and sessions that exhaust their step budget without a final response.

`tools/verify_offline_tool_session.py` independently verifies the complete session by replaying every tool receipt from the frozen initial state and checking transcript/result bindings, subject identity, final state and final response hashes.

A fabricated transcript tool result remains invalid even if the transcript and session receipt are both resealed.

## Current scope

This remains execution infrastructure, not real provider/model behavior evidence.

Local/mock subject adapters exercise the orchestration and evidence path in CI. The current OpenAI/Gemini provider adapters still support `tools=none` only, and no credentialed provider tool-call workflow is enabled.

No AI behavior PASS is claimed by this profile or orchestration layer alone.
