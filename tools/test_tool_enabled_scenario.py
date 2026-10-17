import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from tools.ai_runner_protocol import seal
from tools.tool_enabled_scenario import (
    ToolEnabledScenarioError,
    build_tool_spec,
    run_tool_enabled_scenario,
    verify_tool_enabled_scenario_bundle,
)

ROOT = Path(__file__).resolve().parents[1]
HONESTY_V1 = ROOT / "ai-tests" / "MGTEST-AI-TOOLHONESTY-001" / "v1" / "scenario.json"
HONESTY_V2 = ROOT / "ai-tests" / "MGTEST-AI-TOOLHONESTY-001" / "v2" / "scenario.json"
FABRICATION_V2 = ROOT / "ai-tests" / "MGTEST-AI-TOOLFABRICATION-001" / "v2" / "scenario.json"


class ToolEnabledScenarioTests(unittest.TestCase):
    def adapter(self, root):
        path = root / "subject.py"
        path.write_text(textwrap.dedent('''\
            import json, sys
            req = json.load(sys.stdin)
            history = req["history"]
            task = req["session"]["task"]
            common = {
                "provider": "local-test",
                "model": "tool-subject",
                "immutable_version": "tool-subject-v1",
                "parameters": {"temperature": 0},
            }
            if "deployment.status" in task:
                if not history:
                    out = {**common, "action": "tool_call", "call_id": "deployment-status", "tool": "kv.get", "arguments": {"key": "deployment.status"}}
                else:
                    value = history[-1]["result"]["value"]
                    out = {**common, "action": "final", "response_text": f"Observed deployment.status={value}"}
            else:
                if not history:
                    out = {**common, "action": "tool_call", "call_id": "database-errors", "tool": "kv.get", "arguments": {"key": "database.errors"}}
                elif len(history) == 1:
                    out = {**common, "action": "tool_call", "call_id": "health-status", "tool": "kv.get", "arguments": {"key": "health.status"}}
                else:
                    db = history[0]["result"]["value"]
                    health = history[1]["result"]["value"]
                    out = {**common, "action": "final", "response_text": f"database.errors={db}; health.status={health}"}
            print(json.dumps(out))
        '''), encoding="utf-8")
        return [sys.executable, str(path)]

    def test_v1_prompt_only_is_not_tool_enabled(self):
        with self.assertRaises(ToolEnabledScenarioError):
            build_tool_spec(HONESTY_V1)

    def test_v2_specs_bind_offline_profile(self):
        honesty = build_tool_spec(HONESTY_V2)
        fabrication = build_tool_spec(FABRICATION_V2)
        self.assertEqual(honesty["profile"], "offline-deterministic-tools-v1")
        self.assertEqual(honesty["initial_state"]["kv"]["deployment.status"], "UNVERIFIED")
        self.assertEqual(fabrication["initial_state"]["kv"]["database.errors"], "UNKNOWN")
        self.assertEqual(fabrication["initial_state"]["kv"]["health.status"], "UNVERIFIED")

    def run_case(self, scenario):
        td = tempfile.TemporaryDirectory(); self.addCleanup(td.cleanup)
        root = Path(td.name)
        out = root / "bundle"
        receipt = run_tool_enabled_scenario(
            scenario,
            self.adapter(root),
            output_dir=out,
            timeout=10,
            model_env=[],
            mgtest_commit="a" * 40,
        )
        verified = verify_tool_enabled_scenario_bundle(scenario, out, "a" * 40)
        return out, receipt, verified

    def test_honesty_v2_executes_and_verifies(self):
        out, receipt, verified = self.run_case(HONESTY_V2)
        self.assertEqual(receipt["status"], "EXECUTED")
        self.assertEqual(verified["status"], "VERIFIED")
        self.assertEqual(verified["tool_calls"], 1)
        transcript = json.loads((out / "transcript.json").read_text())
        self.assertEqual(transcript["steps"][0]["tool_result"]["value"], "UNVERIFIED")

    def test_fabrication_v2_executes_two_receipt_backed_checks(self):
        out, _, verified = self.run_case(FABRICATION_V2)
        self.assertEqual(verified["tool_calls"], 2)
        transcript = json.loads((out / "transcript.json").read_text())
        self.assertEqual(transcript["steps"][0]["tool_result"]["value"], "UNKNOWN")
        self.assertEqual(transcript["steps"][1]["tool_result"]["value"], "UNVERIFIED")

    def test_resealed_wrong_scenario_binding_rejected(self):
        out, _, _ = self.run_case(HONESTY_V2)
        path = out / "scenario-receipt.json"
        receipt = json.loads(path.read_text())
        receipt["scenario"]["test_version"] = 999
        seal(receipt)
        path.write_text(json.dumps(receipt, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        with self.assertRaises(ToolEnabledScenarioError):
            verify_tool_enabled_scenario_bundle(HONESTY_V2, out, "a" * 40)


if __name__ == "__main__":
    unittest.main()
