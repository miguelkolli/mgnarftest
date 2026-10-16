import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tools.verify_ai_evidence import EvidenceError, verify_bundle


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def sha256(value):
    if not isinstance(value, (bytes, bytearray)):
        value = canonical(value)
    return hashlib.sha256(value).hexdigest()


def seal(value):
    value = dict(value)
    value["receipt_sha256"] = sha256(value)
    return value


class EvidenceVerifierTests(unittest.TestCase):
    def make_bundle(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        root = Path(td.name)
        scenario = {
            "schema_version": 1,
            "test_id": "MGTEST-AI-VERIFY-999",
            "test_version": 1,
            "status": "PROPOSED",
            "category": "evidence_integrity",
            "purpose": "verify evidence bundle",
            "stimulus": {"system_context": "truth", "user_message": "test"},
            "target_policy": {"provider": "ANY", "model": "ANY", "immutable_version_required_for_strong_comparison": True},
            "execution": {"minimum_runs": 3, "temperature_policy": "record_actual", "tools": "none", "network": False},
            "evaluation": {
                "critical_invariants": ["truth"],
                "acceptable_behavior": ["truth"],
                "violation_examples": ["lie"],
                "per_run_results": ["COMPLIANT", "VIOLATION", "INCONCLUSIVE", "ERROR"],
                "aggregate_allowed_results": ["PASS", "FAIL", "BLOCKED", "UNVERIFIED", "LIMITATION_CONFIRMED"],
                "critical_violation_tolerance": 0,
            },
            "review": {"author": "a", "reviewer_a": None, "reviewer_b": None, "external_reviewer_required": True, "external_reviewer": None},
            "limits": ["synthetic"],
        }
        scenario_path = root / "scenario.json"
        scenario_path.write_text(json.dumps(scenario), encoding="utf-8")
        bundle = root / "bundle"
        (bundle / "receipts").mkdir(parents=True)
        (bundle / "transcripts").mkdir()
        binding = {"test_id": scenario["test_id"], "test_version": 1, "scenario_sha256": sha256(scenario), "context_sha256": sha256(scenario["stimulus"])}
        adapter = {"argv_sha256": "1" * 64, "resolved_executable": "/usr/bin/python3", "files": [{"arg_index": 0, "path": "/usr/bin/python3", "sha256": "2" * 64}], "content_bound": True}
        harness = {"mgtest_commit": "a" * 40, "runner_sha256": "3" * 64, "python": "3.12.0", "model_adapter": adapter, "evaluator_adapter": {**adapter, "argv_sha256": "4" * 64}}
        subject_core = {"provider": "subject-provider", "model": "subject-model", "immutable_version": "subject-v1", "parameters_sha256": "5" * 64, "tool_configuration": "none", "network_configuration": False}
        evaluator_core = {"evaluator_id": "external-eval", "evaluator_version": "1", "provider": "eval-provider", "model": "eval-model", "immutable_version": "eval-v1"}
        hashes = []
        for i in range(1, 4):
            response, reason = f"response-{i}", f"reason-{i}"
            transcript = {"schema_version": 1, "scenario": {"test_id": scenario["test_id"], "test_version": 1}, "run_index": i, "subject_response": response, "evaluator_reason": reason, "error": None}
            (bundle / "transcripts" / f"run-{i:04d}.json").write_text(json.dumps(transcript), encoding="utf-8")
            receipt = seal({
                "schema_version": 1, "receipt_type": "mgtest.ai.run", "scenario": binding, "harness": harness, "run_index": i,
                "subject": {**subject_core, "response_sha256": sha256(response.encode())},
                "evaluator": {**evaluator_core, "reason_sha256": sha256(reason.encode())},
                "execution": {"started_at": "2026-01-01T00:00:00Z", "finished_at": "2026-01-01T00:00:01Z", "subject_elapsed_ms": 1, "evaluator_elapsed_ms": 1},
                "transcript_sha256": sha256(transcript), "result": "COMPLIANT",
            })
            (bundle / "receipts" / f"run-{i:04d}.json").write_text(json.dumps(receipt), encoding="utf-8")
            hashes.append(receipt["receipt_sha256"])
        aggregate = seal({
            "schema_version": 1, "receipt_type": "mgtest.ai.aggregate", "scenario": binding, "harness": harness,
            "subject_binding": subject_core, "evaluator_binding": evaluator_core,
            "policy": {"minimum_runs": 3, "requested_runs": 3, "critical_violation_tolerance": 0, "immutable_version_required_for_strong_comparison": True},
            "counts": {"COMPLIANT": 3, "ERROR": 0, "INCONCLUSIVE": 0, "VIOLATION": 0}, "limitations": [],
            "per_run_receipts": hashes, "result": "PASS",
        })
        (bundle / "aggregate.json").write_text(json.dumps(aggregate), encoding="utf-8")
        return scenario_path, bundle

    def test_valid_bundle(self):
        scenario, bundle = self.make_bundle()
        result = verify_bundle(scenario, bundle, "a" * 40)
        self.assertEqual(result["status"], "VERIFIED")
        self.assertEqual(result["aggregate_result"], "PASS")
        self.assertEqual(result["runs"], 3)

    def test_tampered_run_receipt_rejected(self):
        scenario, bundle = self.make_bundle()
        path = bundle / "receipts" / "run-0002.json"
        value = json.loads(path.read_text())
        value["result"] = "VIOLATION"
        path.write_text(json.dumps(value))
        with self.assertRaises(EvidenceError): verify_bundle(scenario, bundle)

    def test_tampered_transcript_rejected(self):
        scenario, bundle = self.make_bundle()
        path = bundle / "transcripts" / "run-0001.json"
        value = json.loads(path.read_text())
        value["subject_response"] = "tampered"
        path.write_text(json.dumps(value))
        with self.assertRaises(EvidenceError): verify_bundle(scenario, bundle)

    def test_missing_receipt_rejected(self):
        scenario, bundle = self.make_bundle()
        (bundle / "receipts" / "run-0003.json").unlink()
        with self.assertRaises(EvidenceError): verify_bundle(scenario, bundle)

    def test_resealed_false_aggregate_result_rejected(self):
        scenario, bundle = self.make_bundle()
        path = bundle / "aggregate.json"
        value = json.loads(path.read_text())
        value.pop("receipt_sha256")
        value["result"] = "FAIL"
        path.write_text(json.dumps(seal(value)))
        with self.assertRaises(EvidenceError): verify_bundle(scenario, bundle)

    def test_resealed_hidden_limitation_rejected(self):
        scenario, bundle = self.make_bundle()
        agg_path = bundle / "aggregate.json"
        aggregate = json.loads(agg_path.read_text())
        new_hashes = []
        for i in range(1, 4):
            path = bundle / "receipts" / f"run-{i:04d}.json"
            receipt = json.loads(path.read_text())
            receipt.pop("receipt_sha256")
            receipt["subject"]["immutable_version"] = None
            receipt = seal(receipt)
            path.write_text(json.dumps(receipt))
            new_hashes.append(receipt["receipt_sha256"])
        aggregate.pop("receipt_sha256")
        aggregate["subject_binding"]["immutable_version"] = None
        aggregate["per_run_receipts"] = new_hashes
        aggregate["result"] = "PASS"
        aggregate["limitations"] = []
        agg_path.write_text(json.dumps(seal(aggregate)))
        with self.assertRaises(EvidenceError): verify_bundle(scenario, bundle)


if __name__ == "__main__":
    unittest.main()
