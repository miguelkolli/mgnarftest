#!/usr/bin/env python3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tools import prepare_targets as prep


class PrepareTargetsTests(unittest.TestCase):
    SHA_A = "a" * 40
    SHA_B = "b" * 40

    def manifest(self, sha, repository=prep.TARGET_REPOSITORY):
        return {
            "status": "PROPOSED",
            "target": {
                "repository": repository,
                "commit": sha,
            },
        }

    def test_collects_unique_exact_target_shas(self):
        manifests = [
            (Path("tests/a/manifest.json"), self.manifest(self.SHA_B)),
            (Path("tests/b/manifest.json"), self.manifest(self.SHA_A)),
            (Path("tests/c/manifest.json"), self.manifest(self.SHA_B)),
        ]
        self.assertEqual(prep.collect_target_shas(manifests), [self.SHA_A, self.SHA_B])

    def test_wrong_target_repository_fails_closed(self):
        manifests = [(Path("tests/a/manifest.json"), self.manifest(self.SHA_A, "other/repo"))]
        with self.assertRaises(SystemExit) as ctx:
            prep.collect_target_shas(manifests)
        self.assertIn("unsupported target repository", str(ctx.exception))

    def test_non_exact_target_sha_fails_closed(self):
        manifests = [(Path("tests/a/manifest.json"), self.manifest("main"))]
        with self.assertRaises(SystemExit) as ctx:
            prep.collect_target_shas(manifests)
        self.assertIn("exact lowercase 40-hex SHA", str(ctx.exception))

    def test_prepare_target_fetches_exact_sha_and_verifies_head(self):
        with tempfile.TemporaryDirectory() as tmp:
            targets = Path(tmp) / "targets"
            targets.mkdir()

            def fake_run(command, *, cwd=None, capture=False):
                self.assertIsNotNone(cwd)
                if command[:2] == ["git", "rev-parse"]:
                    return self.SHA_A
                if command[:2] == ["git", "-c"] and "checkout" in command:
                    (cwd / "src").mkdir(exist_ok=True)
                return ""

            with mock.patch.object(prep, "run", side_effect=fake_run) as run:
                prep.prepare_target(targets, self.SHA_A)

            commands = [call.args[0] for call in run.call_args_list]
            fetches = [command for command in commands if "fetch" in command]
            self.assertEqual(len(fetches), 1)
            self.assertEqual(fetches[0][-1], self.SHA_A)
            self.assertIn(["git", "rev-parse", "HEAD"], commands)

    def test_prepare_target_rejects_reused_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            targets = Path(tmp) / "targets"
            (targets / self.SHA_A).mkdir(parents=True)
            with self.assertRaises(SystemExit) as ctx:
                prep.prepare_target(targets, self.SHA_A)
        self.assertIn("already exists", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
