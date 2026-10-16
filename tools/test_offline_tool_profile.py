import copy
import unittest

from tools.ai_runner_protocol import seal
from tools.offline_tool_profile import (
    MAX_CALLS, PROFILE_ID, ToolProfileError, execute_plan, verify_execution,
)


class OfflineToolProfileTests(unittest.TestCase):
    def plan(self, calls):
        return {"schema_version": 1, "profile": PROFILE_ID, "calls": calls}

    def test_deterministic_stateful_execution_verifies(self):
        plan = self.plan([
            {"call_id": "1", "tool": "kv.put", "arguments": {"key": "release", "value": "UNVERIFIED"}},
            {"call_id": "2", "tool": "kv.get", "arguments": {"key": "release"}},
            {"call_id": "3", "tool": "counter.increment", "arguments": {"name": "checks"}},
            {"call_id": "4", "tool": "counter.increment", "arguments": {"name": "checks"}},
        ])
        state, receipt = execute_plan(plan)
        self.assertEqual(state["kv"]["release"], "UNVERIFIED")
        self.assertEqual(state["counters"]["checks"], 2)
        self.assertFalse(receipt["network"])
        self.assertFalse(receipt["shell"])
        verified = verify_execution(plan, receipt)
        self.assertEqual(verified["status"], "VERIFIED")

    def test_unknown_tool_blocks_before_mutation(self):
        initial = {"kv": {"safe": "yes"}, "counters": {}}
        plan = self.plan([
            {"call_id": "1", "tool": "kv.put", "arguments": {"key": "safe", "value": "changed"}},
            {"call_id": "2", "tool": "shell.exec", "arguments": {}},
        ])
        frozen = copy.deepcopy(initial)
        with self.assertRaises(ToolProfileError):
            execute_plan(plan, initial)
        self.assertEqual(initial, frozen)

    def test_duplicate_call_id_blocks(self):
        plan = self.plan([
            {"call_id": "x", "tool": "kv.get", "arguments": {"key": "a"}},
            {"call_id": "x", "tool": "kv.get", "arguments": {"key": "b"}},
        ])
        with self.assertRaises(ToolProfileError):
            execute_plan(plan)

    def test_resealed_forged_result_rejected_by_semantic_replay(self):
        plan = self.plan([
            {"call_id": "1", "tool": "counter.increment", "arguments": {"name": "n"}},
        ])
        _, receipt = execute_plan(plan)
        receipt["executions"][0]["result"] = {"value": 999}
        receipt["executions"][0]["result_sha256"] = "0" * 64
        seal(receipt)
        with self.assertRaises(ToolProfileError):
            verify_execution(plan, receipt)

    def test_shell_like_text_is_data_not_execution(self):
        payload = "$(touch /tmp/mgnarftest-should-not-exist); rm -rf /"
        plan = self.plan([
            {"call_id": "1", "tool": "kv.put", "arguments": {"key": "payload", "value": payload}},
            {"call_id": "2", "tool": "kv.get", "arguments": {"key": "payload"}},
        ])
        state, receipt = execute_plan(plan)
        self.assertEqual(state["kv"]["payload"], payload)
        self.assertEqual(receipt["executions"][1]["result"]["value"], payload)
        self.assertTrue(verify_execution(plan, receipt))

    def test_max_calls_fail_closed(self):
        calls = [
            {"call_id": str(i), "tool": "kv.get", "arguments": {"key": "x"}}
            for i in range(MAX_CALLS + 1)
        ]
        with self.assertRaises(ToolProfileError):
            execute_plan(self.plan(calls))


if __name__ == "__main__":
    unittest.main()
