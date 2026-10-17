# AI Evidence Verification v1

`tools/verify_ai_evidence.py` verifies an AI behavior evidence bundle independently from the runner that generated it.

Input bundle:

```text
scenario.json
bundle/
  aggregate.json
  receipts/run-*.json
  transcripts/run-*.json
```

Example:

```text
python3 tools/verify_ai_evidence.py \
  --scenario ai-tests/MGTEST-AI-FALSEPASS-001/v1/scenario.json \
  --bundle /path/to/evidence-bundle \
  --expected-mgtest-commit <40-hex-commit>
```

The verifier does not trust the aggregate `result` field. It independently checks receipt hashes, exact scenario/context hashes, referenced run-set completeness, run ordering, transcript hashes, response/reason hashes, harness equality, adapter-binding structure, subject/evaluator bindings, frozen run policy, counts, identity/configuration drift, known limitations and the aggregate-result decision rule.

This means simply changing `PASS` to another result (or changing a limitation and recomputing the outer receipt hash) is not sufficient: the verifier recomputes the semantic outcome from the bound per-run evidence.

The verifier is still a consistency verifier, not a cryptographic signer. SHA-256 receipts are tamper-evident only relative to the evidence set. Authenticity of a STABLE claim still depends on the repository trust root, CI/artifact provenance, authenticated review history and the external-review requirement.

Current AI scenarios remain `PROPOSED`/`UNVERIFIED` until real provider/model runs exist. A successful evidence-verifier check means the bundle is internally consistent with the frozen rule; it does not convert an unexecuted scenario into PASS and does not make a test STABLE.
