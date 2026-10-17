#!/usr/bin/env python3
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest import mock

from tools import enforce_trust_root as guard


class TrustRootGuardTests(unittest.TestCase):
    HEAD_SHA = "h" * 40
    MANIFEST_PATH = "tests/MGTEST-NARF-ORDER-001/v1/manifest.json"

    def event_file(self):
        event = {
            "pull_request": {
                "number": 7,
                "head": {"sha": self.HEAD_SHA},
                "base": {"sha": "b" * 40},
                "user": {"login": "promoter"},
            }
        }
        handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
        json.dump(event, handle)
        handle.close()
        self.addCleanup(lambda: os.path.exists(handle.name) and os.unlink(handle.name))
        return handle.name

    def context(self):
        return mock.patch.dict(
            os.environ,
            {
                "GITHUB_TOKEN": "test-token",
                "GITHUB_EVENT_PATH": self.event_file(),
                "GITHUB_REPOSITORY": guard.REGISTRY_REPOSITORY,
            },
            clear=False,
        )

    @staticmethod
    def good_ruleset():
        return {
            "id": 25304585,
            "name": guard.TRUST_ROOT_RULESET_NAME,
            "target": "branch",
            "source_type": "Repository",
            "source": guard.REGISTRY_REPOSITORY,
            "enforcement": "active",
            "conditions": {"ref_name": {"exclude": [], "include": ["~DEFAULT_BRANCH"]}},
            "rules": [
                {"type": "deletion"},
                {"type": "non_fast_forward"},
                {
                    "type": "pull_request",
                    "parameters": {
                        "required_review_thread_resolution": True,
                    },
                },
                {
                    "type": "required_status_checks",
                    "parameters": {
                        "strict_required_status_checks_policy": True,
                        "do_not_enforce_on_create": False,
                        "required_status_checks": [
                            {"context": context, "integration_id": guard.EXPECTED_CHECK_INTEGRATION_ID}
                            for context in sorted(guard.REQUIRED_STATUS_CHECKS)
                        ],
                    },
                },
            ],
            "bypass_actors": [],
        }

    @classmethod
    def api_for(cls, detail=None, *, protected=True):
        detail = detail or cls.good_ruleset()

        def side_effect(url, token):
            if url.endswith("/branches/main"):
                return {"name": "main", "protected": protected}
            if url.endswith("/rulesets?per_page=100"):
                return [
                    {
                        "id": detail["id"],
                        "name": detail["name"],
                        "target": detail["target"],
                        "source_type": detail["source_type"],
                        "source": detail["source"],
                        "enforcement": detail["enforcement"],
                    }
                ]
            if url.endswith(f"/rulesets/{detail['id']}"):
                return detail
            raise AssertionError(f"unexpected API URL: {url}")

        return side_effect

    def test_live_ruleset_authority_accepts_exact_policy(self):
        with mock.patch.object(guard, "api_get", side_effect=self.api_for()):
            result = guard.verify_repository_trust_root(guard.REGISTRY_REPOSITORY, "token")
        self.assertEqual(result["status"], "PROTECTED")
        self.assertEqual(result["bypass_actors"], 0)
        self.assertEqual(result["required_status_checks"], sorted(guard.REQUIRED_STATUS_CHECKS))

    def test_missing_trusted_promotion_gate_is_rejected(self):
        detail = self.good_ruleset()
        status_rule = next(rule for rule in detail["rules"] if rule["type"] == "required_status_checks")
        status_rule["parameters"]["required_status_checks"] = [
            check
            for check in status_rule["parameters"]["required_status_checks"]
            if check["context"] != "trusted-promotion-gate"
        ]
        with mock.patch.object(guard, "api_get", side_effect=self.api_for(detail)):
            with self.assertRaisesRegex(guard.TrustRootConfigurationError, "trusted-promotion-gate"):
                guard.verify_repository_trust_root(guard.REGISTRY_REPOSITORY, "token")

    def test_bypass_actor_is_rejected(self):
        detail = self.good_ruleset()
        detail["bypass_actors"] = [{"actor_id": 1, "actor_type": "RepositoryRole"}]
        with mock.patch.object(guard, "api_get", side_effect=self.api_for(detail)):
            with self.assertRaisesRegex(guard.TrustRootConfigurationError, "bypass"):
                guard.verify_repository_trust_root(guard.REGISTRY_REPOSITORY, "token")

    def test_unprotected_branch_is_rejected(self):
        with mock.patch.object(guard, "api_get", side_effect=self.api_for(protected=False)):
            with self.assertRaisesRegex(guard.TrustRootConfigurationError, "not protected"):
                guard.verify_repository_trust_root(guard.REGISTRY_REPOSITORY, "token")

    def test_non_strict_status_policy_is_rejected(self):
        detail = self.good_ruleset()
        status_rule = next(rule for rule in detail["rules"] if rule["type"] == "required_status_checks")
        status_rule["parameters"]["strict_required_status_checks_policy"] = False
        with mock.patch.object(guard, "api_get", side_effect=self.api_for(detail)):
            with self.assertRaisesRegex(guard.TrustRootConfigurationError, "not strict"):
                guard.verify_repository_trust_root(guard.REGISTRY_REPOSITORY, "token")

    def test_non_stable_development_is_allowed_without_live_trust_lookup(self):
        with self.context(), \
             mock.patch.object(guard, "changed_files", return_value=["README.md"]), \
             mock.patch.object(guard, "verify_repository_trust_root") as live:
            self.assertEqual(guard.main(), 0)
            live.assert_not_called()

    def test_trust_policy_change_requires_live_ruleset(self):
        with self.context(), \
             mock.patch.object(
                 guard,
                 "changed_files",
                 return_value=["tools/enforce_trust_root.py"],
             ), \
             mock.patch.object(
                 guard,
                 "verify_repository_trust_root",
                 return_value={"status": "PROTECTED", "ruleset_id": 25304585},
             ) as live:
            self.assertEqual(guard.main(), 0)
            live.assert_called_once()

    def test_trust_policy_change_fails_closed_on_incomplete_ruleset(self):
        stderr = io.StringIO()
        with self.context(), \
             mock.patch.object(
                 guard,
                 "changed_files",
                 return_value=["tools/enforce_trust_root.py"],
             ), \
             mock.patch.object(
                 guard,
                 "verify_repository_trust_root",
                 side_effect=guard.TrustRootConfigurationError("required trust-root checks missing"),
             ), \
             redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as ctx:
                guard.main()
        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("repository trust-root verification failed", stderr.getvalue())

    def test_disabled_policy_blocks_stable_after_live_ruleset_passes(self):
        stderr = io.StringIO()
        with self.context(), \
             mock.patch.object(guard, "changed_files", return_value=[self.MANIFEST_PATH]), \
             mock.patch.object(guard, "json_repo_file", return_value={"status": "STABLE"}), \
             mock.patch.object(
                 guard,
                 "verify_repository_trust_root",
                 return_value={"status": "PROTECTED", "ruleset_id": 25304585},
             ), \
             mock.patch.object(guard, "STABLE_PROMOTION_ENABLED", False), \
             mock.patch.object(guard, "TRUST_ROOT_STATUS", "UNPROTECTED"), \
             redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as ctx:
                guard.main()
        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("STABLE promotion disabled", stderr.getvalue())

    def test_live_ruleset_drift_blocks_even_if_policy_is_enabled(self):
        stderr = io.StringIO()
        with self.context(), \
             mock.patch.object(guard, "changed_files", return_value=[self.MANIFEST_PATH]), \
             mock.patch.object(guard, "json_repo_file", return_value={"status": "STABLE"}), \
             mock.patch.object(
                 guard,
                 "verify_repository_trust_root",
                 side_effect=guard.TrustRootConfigurationError("required trust-root checks missing"),
             ), \
             mock.patch.object(guard, "STABLE_PROMOTION_ENABLED", True), \
             mock.patch.object(guard, "TRUST_ROOT_STATUS", "PROTECTED"), \
             redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as ctx:
                guard.main()
        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("repository trust-root verification failed", stderr.getvalue())

    def test_verified_enabled_trust_root_allows_stable_promotion(self):
        with self.context(), \
             mock.patch.object(guard, "changed_files", return_value=[self.MANIFEST_PATH]), \
             mock.patch.object(guard, "json_repo_file", return_value={"status": "STABLE"}), \
             mock.patch.object(
                 guard,
                 "verify_repository_trust_root",
                 return_value={"status": "PROTECTED", "ruleset_id": 25304585},
             ), \
             mock.patch.object(guard, "STABLE_PROMOTION_ENABLED", True), \
             mock.patch.object(guard, "TRUST_ROOT_STATUS", "PROTECTED"):
            self.assertEqual(guard.main(), 0)

    def test_non_manifest_change_skips(self):
        with self.context(), \
             mock.patch.object(guard, "changed_files", return_value=["README.md"]), \
             mock.patch.object(guard, "json_repo_file") as fetch:
            self.assertEqual(guard.main(), 0)
            fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
