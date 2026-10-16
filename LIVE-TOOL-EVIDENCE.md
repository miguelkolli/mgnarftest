# Live Tool Authority and Capability Evidence v1

MGnarfTest does not allow credentialed provider tool-subject readiness to be enabled by boolean flags.

A tool-enabled live-readiness plan requires two separate evidence artifacts:

1. **governance authorization evidence** — proves that the exact MGnarfTest commit/provider/model/adapter/tool contract is authorized for credentialed live offline-tool subject execution;
2. **provider/model capability evidence** — proves that an identified verifier checked the exact provider/model/adapter against the frozen tool + continuation contract.

Both artifacts are JSON objects with an internal canonical `evidence_sha256`. The readiness plan also records the exact raw-file SHA-256. A changed artifact therefore does not silently retain authority.

## Authorization evidence

Required fields:

```json
{
  "schema_version": 1,
  "evidence_type": "mgtest.ai.provider-tool-subject-authorization",
  "status": "AUTHORIZED",
  "scope": "credentialed-live-offline-tool-subject",
  "authority_id": "<authenticated/governed authority identity>",
  "authority_revision": 1,
  "target_mgtest_commit": "<40-hex exact commit>",
  "provider": "openai|google-gemini",
  "model": "<exact selected model alias/name>",
  "adapter_sha256": "<exact adapter SHA-256>",
  "tool_subject_contract": "<frozen provider tool contract>",
  "continuation_chain_contract": "provider-native-context-chain-v1",
  "evidence_sha256": "<canonical body SHA-256>"
}
```

This artifact answers **who/what authorized the live subject-tool mode for exactly this target**. It does not prove technical capability.

## Capability evidence

Required fields:

```json
{
  "schema_version": 1,
  "evidence_type": "mgtest.ai.provider-model-tool-capability",
  "status": "VERIFIED",
  "verifier_id": "<verifier identity>",
  "verification_revision": 1,
  "verification_method": "<frozen method/fixture description>",
  "target_mgtest_commit": "<40-hex exact commit>",
  "provider": "openai|google-gemini",
  "model": "<exact selected model alias/name>",
  "immutable_version": "<snapshot/build or null>",
  "adapter_sha256": "<exact adapter SHA-256>",
  "tool_subject_contract": "<frozen provider tool contract>",
  "continuation_context_kind": "<provider-native context kind>",
  "continuation_chain_contract": "provider-native-context-chain-v1",
  "evidence_sha256": "<canonical body SHA-256>"
}
```

This artifact answers **what exact provider/model/adapter capability was verified, by whom, and against which contract**. It does not itself grant authority.

## Fail-closed composition

For a tool-enabled plan:

```text
protected repository trust root
        +
valid authorization evidence
        +
valid capability evidence
        +
exact scenario / commit / adapter bindings
        =
READY eligibility
```

Missing, malformed, tampered or mismatched evidence leaves the plan `BLOCKED`.

Authorization and capability are deliberately separate. One artifact cannot substitute for the other.

## Current boundary

The evidence format and validation are test infrastructure. The repository is still private/unprotected for governed STABLE promotion, and no credentialed live provider/model behavior evidence is claimed.

When the repository trust root is later enforced, evidence acceptance must be governed by the protected review/promotion process rather than by self-authored files alone.
