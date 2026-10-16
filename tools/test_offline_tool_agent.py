import json
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from tools.ai_runner_protocol import seal, sha256
from tools.offline_tool_agent import ToolAgentError, parse_action, run_tool_session
from tools.verify_offline_tool_session import ToolSessionEvidenceError, verify_bundle


class OfflineToolAgentTests(unittest.TestCase):
    def case(self, mode="normal", immutable="subject-v1"):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        root = Path(td.name)
        spec = root / "spec.json"
        spec.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "profile": "offline-deterministic-tools-v1",
                    "task": "Store release=UNVERIFIED, read it back, then report the observed value.",
                    "max_steps": 5,
                    "initial_state": {"kv": {}, "counters": {}},
                }
            ),
            encoding="utf-8",
        )
        model = root / "model.py"
        model.write_text(
            textwrap.dedent(
                f'''\
                import json,sys
                q=json.load(sys.stdin); h=q["history"]
                base={{"provider":"local","model":"tool-subject","immutable_version":{immutable!r},"parameters":{{"temperature":0}}}}
                mode={mode!r}
                if mode=="unknown":
                    out={{**base,"action":"tool_call","call_id":"bad","tool":"shell.exec","arguments":{{}}}}
                elif not h:
                    out={{**base,"action":"tool_call","call_id":"put-1","tool":"kv.put","arguments":{{"key":"release","value":"UNVERIFIED"}}}}
                elif len(h)==1:
                    cid="put-1" if mode=="duplicate" else "get-1"
                    out={{**base,"action":"tool_call","call_id":cid,"tool":"kv.get","arguments":{{"key":"release"}}}}
                else:
                    value=h[-1]["result"]["value"]
                    out={{**base,"action":"final","response_text":"Observed release="+str(value)}}
                print(json.dumps(out))
                if mode=="drift" and not h:
                    open(__file__,"a").write("\\n# drift")
                '''
            ),
            encoding="utf-8",
        )
        out = root / "out"
        return root, spec, model, out

    def run_case(self, mode="normal", immutable="subject-v1"):
        root, spec, model, out = self.case(mode, immutable)
        receipt = run_tool_session(
            spec,
            [sys.executable, str(model)],
            output_dir=out,
            timeout=10,
            model_env=[],
            mgtest_commit="a" * 40,
        )
        return root, spec, model, out, receipt

    def test_tool_loop_uses_executor_results_and_verifies(self):
        _, spec, _, out, receipt = self.run_case()
        self.assertEqual(receipt["status"], "COMPLETED")
        self.assertEqual(len(receipt["tool_receipts"]), 2)
        self.assertEqual(receipt["provider_context_chain_sha256"], sha256([]))
        result = verify_bundle(spec, out, "a" * 40)
        self.assertEqual(result["status"], "VERIFIED")
        self.assertEqual(result["tool_calls"], 2)
        self.assertEqual(result["provider_contexts"], 0)
        transcript = json.loads((out / "transcript.json").read_text())
        self.assertEqual(
            transcript["steps"][-1]["action"]["response_text"],
            "Observed release=UNVERIFIED",
        )

    def test_unknown_tool_blocks(self):
        _, spec, model, out = self.case("unknown")
        with self.assertRaises(ToolAgentError):
            run_tool_session(
                spec,
                [sys.executable, str(model)],
                output_dir=out,
                timeout=10,
                model_env=[],
                mgtest_commit="a" * 40,
            )

    def test_duplicate_tool_call_id_blocks(self):
        _, spec, model, out = self.case("duplicate")
        with self.assertRaises(ToolAgentError):
            run_tool_session(
                spec,
                [sys.executable, str(model)],
                output_dir=out,
                timeout=10,
                model_env=[],
                mgtest_commit="a" * 40,
            )

    def test_adapter_drift_blocks(self):
        _, spec, model, out = self.case("drift")
        with self.assertRaisesRegex(ToolAgentError, "MODEL_ADAPTER_DRIFT"):
            run_tool_session(
                spec,
                [sys.executable, str(model)],
                output_dir=out,
                timeout=10,
                model_env=[],
                mgtest_commit="a" * 40,
            )

    def test_mutable_model_is_recorded_limitation(self):
        _, spec, _, out, receipt = self.run_case(immutable=None)
        self.assertEqual(
            receipt["limitations"],
            ["SUBJECT_MODEL_VERSION_MUTABLE_OR_UNAVAILABLE"],
        )
        result = verify_bundle(spec, out, "a" * 40)
        self.assertEqual(
            result["limitations"],
            ["SUBJECT_MODEL_VERSION_MUTABLE_OR_UNAVAILABLE"],
        )

    def test_resealed_fabricated_tool_result_is_rejected(self):
        _, spec, _, out, _ = self.run_case()
        transcript_path = out / "transcript.json"
        session_path = out / "session.json"
        transcript = json.loads(transcript_path.read_text())
        transcript["steps"][1]["tool_result"] = {
            "found": True,
            "value": "PASS",
        }
        transcript_path.write_text(
            json.dumps(transcript, sort_keys=True, indent=2) + "\n"
        )
        session = json.loads(session_path.read_text())
        session["transcript_sha256"] = sha256(transcript)
        seal(session)
        session_path.write_text(
            json.dumps(session, sort_keys=True, indent=2) + "\n"
        )
        with self.assertRaises(ToolSessionEvidenceError):
            verify_bundle(spec, out, "a" * 40)

    def test_resealed_provider_context_chain_mismatch_is_rejected(self):
        _, spec, _, out, _ = self.run_case()
        session_path = out / "session.json"
        session = json.loads(session_path.read_text())
        session["provider_context_chain_sha256"] = "0" * 64
        seal(session)
        session_path.write_text(
            json.dumps(session, sort_keys=True, indent=2) + "\n"
        )
        with self.assertRaisesRegex(
            ToolSessionEvidenceError,
            "provider continuation context chain mismatch",
        ):
            verify_bundle(spec, out, "a" * 40)

    def test_known_provider_requires_continuation_context(self):
        with self.assertRaisesRegex(
            ToolAgentError,
            "PROVIDER_CONTINUATION_CONTEXT_MISSING",
        ):
            parse_action(
                {
                    "provider": "openai",
                    "model": "gpt-test",
                    "immutable_version": "gpt-test-v1",
                    "parameters": {"temperature": 0},
                    "action": "tool_call",
                    "call_id": "call-1",
                    "tool": "kv.get",
                    "arguments": {"key": "x"},
                }
            )


if __name__ == "__main__":
    unittest.main()
