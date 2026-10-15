#!/usr/bin/env python3
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import validate_registry as validator


class RegistryValidatorParityTests(unittest.TestCase):
    TEST_ID = "MGTEST-NARF-ORDER-001"

    def base_manifest(self):
        return {
            "schema_version": 1,
            "test_id": self.TEST_ID,
            "test_version": 1,
            "status": "PROPOSED",
            "target": {
                "project": "MGnarf",
                "repository": "miguelkolli/mgnarf",
                "release": "v1.70",
                "commit": "b811a13eab9cacd9f922b1f15097aa6bf700fc01",
            },
            "purpose": "Exercise a frozen external security invariant.",
            "expected": {
                "allowed_results": ["PASS", "FAIL", "BLOCKED", "UNVERIFIED"],
                "safe_condition": "The protected boundary must reject the frozen attack condition.",
            },
            "execution": {
                "entrypoint": "python3 tests/MGTEST-NARF-ORDER-001/v1/test.py",
                "network": False,
                "privileges": "none",
                "external_dependencies": [],
                "timeout_seconds": 30,
            },
            "limits": ["This fixture exercises validator contract parity."],
            "review": {
                "author": "miguelkolli",
                "reviewer_a": None,
                "reviewer_b": None,
                "promotion_pr": None,
            },
            "evidence": {
                "result": "UNVERIFIED",
                "run_id": None,
                "artifact_hash": None,
                "receipt_sha256": None,
                "mgtest_commit": None,
                "target_commit": None,
            },
        }

    def validate_data(self, data):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "tests" / self.TEST_ID / "v1" / "manifest.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(data), encoding="utf-8")
            with mock.patch.object(validator, "ROOT", root):
                return validator.validate(path)

    def test_valid_manifest_passes(self):
        self.assertEqual(self.validate_data(self.base_manifest()), (self.TEST_ID, 1))

    def test_unknown_top_level_field_fails_closed(self):
        data = self.base_manifest()
        data["surprise"] = True
        with self.assertRaises(ValueError) as ctx:
            self.validate_data(data)
        self.assertIn("manifest contains unknown field(s): surprise", str(ctx.exception))

    def test_unknown_nested_field_fails_closed(self):
        data = self.base_manifest()
        data["execution"]["debug"] = True
        with self.assertRaises(ValueError) as ctx:
            self.validate_data(data)
        self.assertIn("execution contains unknown field(s): debug", str(ctx.exception))

    def test_invalid_repository_shape_fails_closed(self):
        data = self.base_manifest()
        data["target"]["repository"] = "not-a-repository"
        with self.assertRaises(ValueError) as ctx:
            self.validate_data(data)
        self.assertIn("target.repository must be owner/name", str(ctx.exception))

    def test_non_string_external_dependency_fails_closed(self):
        data = self.base_manifest()
        data["execution"]["external_dependencies"] = [123]
        with self.assertRaises(ValueError) as ctx:
            self.validate_data(data)
        self.assertIn("must be a list of strings", str(ctx.exception))

    def test_runnable_manifest_without_pass_fails_closed(self):
        data = self.base_manifest()
        data["expected"]["allowed_results"] = ["FAIL", "BLOCKED"]
        with self.assertRaises(ValueError) as ctx:
            self.validate_data(data)
        self.assertIn("must explicitly allow PASS", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
