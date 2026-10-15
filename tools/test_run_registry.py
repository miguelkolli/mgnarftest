#!/usr/bin/env python3
import subprocess
import unittest
from unittest import mock

from tools import run_registry as runner


class RegistryRunnerTimeoutTests(unittest.TestCase):
    def test_timeout_kills_named_container_and_fails_closed(self):
        command = ["docker", "run", "--name", "mgnarftest-timeout-fixture"]
        with mock.patch.object(
            runner.subprocess,
            "run",
            side_effect=[
                subprocess.TimeoutExpired(command, 2),
                subprocess.CompletedProcess(["docker", "rm", "-f", "mgnarftest-timeout-fixture"], 0),
            ],
        ) as run:
            with self.assertRaises(SystemExit) as ctx:
                runner.run_container(command, "mgnarftest-timeout-fixture", 2)
        self.assertIn("exceeded timeout_seconds=2", str(ctx.exception))
        self.assertEqual(run.call_count, 2)
        cleanup = run.call_args_list[1].args[0]
        self.assertEqual(cleanup, ["docker", "rm", "-f", "mgnarftest-timeout-fixture"])

    def test_nonzero_container_result_fails_closed(self):
        with mock.patch.object(
            runner.subprocess,
            "run",
            return_value=subprocess.CompletedProcess(["docker", "run"], 9),
        ):
            with self.assertRaises(SystemExit) as ctx:
                runner.run_container(["docker", "run"], "fixture", 3)
        self.assertIn("returned 9", str(ctx.exception))


if __name__ == "__main__":
    unittest.main(verbosity=2)
