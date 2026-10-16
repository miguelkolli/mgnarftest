# Offline Tool Execution Profile v1

MGnarfTest needs a controlled tool layer before any AI model is allowed to exercise real tools or external effects.

`tools/offline_tool_profile.py` provides a deterministic, no-network, no-shell execution substrate for future tool-enabled AI behavior runs.

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

## Current scope

This is execution infrastructure, not model-behavior evidence.

The current OpenAI/Gemini provider adapters still support `tools=none` only. A later agent/tool runner can expose this profile to a subject model and bind model tool requests to these receipts without giving the model real external authority.

No AI behavior PASS is claimed by this profile alone.
