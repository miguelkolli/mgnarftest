import json
import tempfile
import unittest
from pathlib import Path

from tools.check_ai_live_readiness import ReadinessError, build_plan


class LiveReadinessTests(unittest.TestCase):
    def scenario(self, *, tools="none", network=False, minimum_runs=20):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        root = Path(td.name)
        path = root / "ai-tests" / "MGTEST-AI-LIVE-999" / "v1" / "scenario.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps({
            "schema_version": 1,
            "test_id": "MGTEST-AI-LIVE-999",
            "test_version": 1,
            "status": "PROPOSED",
            "category": "evidence_integrity",
            "purpose": "live readiness test",
            "stimulus": {"system_context": "truth", "user_message": "test"},
            "target_policy": {"provider": "ANY", "model": "ANY", "immutable_version_required_for_strong_comparison": True},
            "execution": {"minimum_runs": minimum_runs, "temperature_policy": "record_actual", "tools": tools, "network": network},
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
        }), encoding="utf-8")
        return path

    def plan(self, path, **kwargs):
        defaults = dict(
            mgtest_commit="a" * 40,
            subject_provider="openai",
            subject_model="subject-model",
            evaluator_a_provider="google-gemini",
            evaluator_a_model="eval-a-model",
            evaluator_b_provider="openai",
            evaluator_b_model="eval-b-model",
            runs=20,
        )
        defaults.update(kwargs)
        return build_plan(path, **defaults)

    def test_current_trust_root_blocks(self):
        plan = self.plan(self.scenario())
        self.assertEqual(plan["status"], "BLOCKED")
        self.assertEqual(plan["execution_mode"], "dual-evaluator-v2")
        self.assertIn("REPOSITORY_TRUST_ROOT_NOT_ENFORCED", plan["blockers"])
        self.assertIn("TRUST_ROOT_STATUS_UNPROTECTED", plan["blockers"])

    def test_enforced_trust_root_can_be_ready(self):
        plan = self.plan(
            self.scenario(), trust_root_status="PROTECTED", stable_promotion_enabled=True
        )
        self.assertEqual(plan["status"], "READY")
        self.assertEqual(plan["blockers"], [])
        self.assertEqual(plan["subject"]["required_secret_env"], "OPENAI_API_KEY")
        self.assertEqual(plan["evaluators"]["a"]["required_secret_env"], "GEMINI_API_KEY")
        self.assertEqual(plan["evaluators"]["b"]["required_secret_env"], "OPENAI_API_KEY")

    def test_below_minimum_runs_rejected(self):
        with self.assertRaises(ReadinessError):
            self.plan(self.scenario(), runs=19)

    def test_subject_evaluator_a_collision_blocks(self):
        plan = self.plan(
            self.scenario(),
            evaluator_a_provider="openai",
            evaluator_a_model="subject-model",
            trust_root_status="PROTECTED",
            stable_promotion_enabled=True,
        )
        self.assertEqual(plan["status"], "BLOCKED")
        self.assertIn("SUBJECT_EVALUATOR_A_SAME_MODEL_ALIAS", plan["blockers"])

    def test_subject_evaluator_b_collision_blocks(self):
        plan = self.plan(
            self.scenario(),
            evaluator_b_provider="openai",
            evaluator_b_model="subject-model",
            trust_root_status="PROTECTED",
            stable_promotion_enabled=True,
        )
        self.assertEqual(plan["status"], "BLOCKED")
        self.assertIn("SUBJECT_EVALUATOR_B_SAME_MODEL_ALIAS", plan["blockers"])

    def test_evaluator_pair_collision_blocks(self):
        plan = self.plan(
            self.scenario(),
            evaluator_b_provider="google-gemini",
            evaluator_b_model="eval-a-model",
            trust_root_status="PROTECTED",
            stable_promotion_enabled=True,
        )
        self.assertEqual(plan["status"], "BLOCKED")
        self.assertIn("EVALUATOR_PAIR_SAME_MODEL_ALIAS", plan["blockers"])

    def test_tool_capability_rejected(self):
        with self.assertRaises(ReadinessError):
            self.plan(self.scenario(tools="web"))

    def test_model_network_capability_rejected(self):
        with self.assertRaises(ReadinessError):
            self.plan(self.scenario(network=True))

    def test_invalid_commit_rejected(self):
        with self.assertRaises(ReadinessError):
            self.plan(self.scenario(), mgtest_commit="main")


if __name__ == "__main__":
    unittest.main()
