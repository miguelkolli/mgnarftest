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

    def test_non_stable_development_is_allowed(self):
        with self.context(), \
             mock.patch.object(guard, "changed_files", return_value=[self.MANIFEST_PATH]), \
             mock.patch.object(guard, "json_repo_file", return_value={"status": "PROPOSED"}):
            self.assertEqual(guard.main(), 0)

    def test_unverified_trust_root_blocks_stable_promotion(self):
        stderr = io.StringIO()
        with self.context(), \
             mock.patch.object(guard, "changed_files", return_value=[self.MANIFEST_PATH]), \
             mock.patch.object(guard, "json_repo_file", return_value={"status": "STABLE"}), \
             mock.patch.object(guard, "STABLE_PROMOTION_ENABLED", False), \
             mock.patch.object(guard, "TRUST_ROOT_STATUS", "UNVERIFIED"), \
             redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as ctx:
                guard.main()
        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("STABLE promotion disabled", stderr.getvalue())
        self.assertIn("UNVERIFIED", stderr.getvalue())

    def test_verified_enabled_trust_root_allows_stable_promotion(self):
        with self.context(), \
             mock.patch.object(guard, "changed_files", return_value=[self.MANIFEST_PATH]), \
             mock.patch.object(guard, "json_repo_file", return_value={"status": "STABLE"}), \
             mock.patch.object(guard, "STABLE_PROMOTION_ENABLED", True), \
             mock.patch.object(guard, "TRUST_ROOT_STATUS", "VERIFIED"):
            self.assertEqual(guard.main(), 0)

    def test_non_manifest_change_skips(self):
        with self.context(), \
             mock.patch.object(guard, "changed_files", return_value=["README.md"]), \
             mock.patch.object(guard, "json_repo_file") as fetch:
            self.assertEqual(guard.main(), 0)
            fetch.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
