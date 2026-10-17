# MGnarfTest documentation

Documentation is grouped by subject. Start with the [project README](../README.md) and the [external test quickstart](contributing/EXTERNAL-TEST-QUICKSTART.md).

Only the repository entry points `README.md`, `REGISTRY.md`, and `CHANGELOG.md` remain at the root. `REGISTRY.md` is a fixed path in the STABLE promotion verifier; `README.md` is the GitHub landing page. GitHub recognizes contribution and security policies from `.github/`. The quickstart has moved into the contributing documentation folder; previously shared direct links to its old path need updating.

## Contributing and security

- [External test quickstart](contributing/EXTERNAL-TEST-QUICKSTART.md)
- [Contribution and review policy](../.github/CONTRIBUTING.md)
- [Security policy and vulnerability reporting](../.github/SECURITY.md)

## AI behavior specifications

- [AI-BEHAVIOR-SPEC.md](ai/behavior/AI-BEHAVIOR-SPEC.md)
- [AI-COVERAGE.md](ai/behavior/AI-COVERAGE.md)

## AI runners, providers and offline execution

- [AI-RUNNER.md](ai/execution/AI-RUNNER.md)
- [AI-LIVE-RUN.md](ai/execution/AI-LIVE-RUN.md)
- [MULTI-SUBJECT.md](ai/execution/MULTI-SUBJECT.md)
- [OFFLINE-TOOL-PROFILE.md](ai/execution/OFFLINE-TOOL-PROFILE.md)
- [PROVIDER-ADAPTERS.md](ai/execution/PROVIDER-ADAPTERS.md)

## AI evidence, acceptance and evaluation

- [AI-EVIDENCE-VERIFY.md](ai/evidence/AI-EVIDENCE-VERIFY.md)
- [CROSS-MODEL.md](ai/evidence/CROSS-MODEL.md)
- [EVALUATOR-CONSENSUS.md](ai/evidence/EVALUATOR-CONSENSUS.md)
- [LIVE-TOOL-ACCEPTANCE.md](ai/evidence/LIVE-TOOL-ACCEPTANCE.md)
- [LIVE-TOOL-EVIDENCE.md](ai/evidence/LIVE-TOOL-EVIDENCE.md)
- [TOOL-BEHAVIOR-AGGREGATE.md](ai/evidence/TOOL-BEHAVIOR-AGGREGATE.md)

## MGnarf gate test specification

- [TEST-SPEC.md](gate/TEST-SPEC.md)

## Governance and trust boundaries

- [DEFERRED.md](governance/DEFERRED.md)
- [STATUS-LATTICE.md](governance/STATUS-LATTICE.md)
- [TRUST-BOUNDARY.md](governance/TRUST-BOUNDARY.md)

## Releases

- [RELEASE-CHECKLIST.md](releases/RELEASE-CHECKLIST.md)

## Other resources

- [Example external gate-test template](../tests/_template/README.md)
- [AI behavior scenarios](../ai-tests/README.md)
- [Community outreach draft](mgnarftest_reddit_short.md)

A PASS is execution evidence, not STABLE acceptance. For exact coverage and limits, refer to [REGISTRY.md](../REGISTRY.md).
