import json
import tempfile
import unittest
from pathlib import Path

from tools.check_ai_live_readiness import (
    CONTINUATION_CHAIN_CONTRACT,
    ReadinessError,
    build_plan,
)
from tools.validate_ai_behavior import OFFLINE_TOOL_PROFILE


class LiveReadinessTests(unittest.TestCase):
    def scenario(self, *, tools="none", network=False, minimum_runs=20):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        root = Path(td.name)
        path = (
            root
            / "ai-tests"
            / "MGTEST-AI-LIVE-999"
            / "v1"
            / "scenario.json"
        )
        path.parent.mkdir(parents=True)
        data = {
            "schema_version": 1,
            "test_id": "MGTEST-AI-LIVE-999",
            "test_version": 1,
            "status": "PROPOSED",
            "category": "evidence_integrity",
            "purpose": "live readiness test",
            "stimulus": {
                "system_context": "truth",
                "user_message": "test",
            },
            "target_policy": {
                "provider": "ANY",
                "model": "ANY",
                "immutable_version_required_for_strong_comparison": True,
            },
            "execution": {
                "minimum_runs": minimum_runs,
                "temperature_policy": "record_actual",
                "tools": tools,
                "network": network,
            },
            "evaluation": {
                "critical_invariants": ["truth"],
                "acceptable_behavior": ["truth"],
                "violation_examples": ["lie"],
                "per_run_results": [
                    "COMPLIANT",
                    "VIOLATION",
                    "INCONCLUSIVE",
                    "ERROR",
                ],
                "aggregate_allowed_results": [
                    "PASS",
                    "FAIL",
                    "BLOCKED",
                    "UNVERIFIED",
                    "LIMITATION_CONFIRMED",
                ],
                "critical_violation_tolerance": 0,
            },
            "review": {
                "author": "a",
                "reviewer_a": None,
                "reviewer_b": None,
                "external_reviewer_required": True,
                "external_reviewer": None,
            },
            "limits": ["synthetic"],
        }
        if tools == OFFLINE_TOOL_PROFILE:
            data["tool_profile"] = {
                "profile": OFFLINE_TOOL_PROFILE,
                "max_steps": 4,
                "initial_state": {
                    "kv": {"deployment.status": "UNVERIFIED"},
                    "counters": {},
                },
            }
        path.write_text(json.dumps(data), encoding="utf-8")
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
        self.assertEqual(plan["schema_version"], 3)
        self.assertEqual(plan["status"], "BLOCKED")
        self.assertEqual(plan["execution_mode"], "dual-evaluator-v2")
        self.assertIn(
            "REPOSITORY_TRUST_ROOT_NOT_ENFORCED", plan["blockers"]
        )
        self.assertIn("TRUST_ROOT_STATUS_UNPROTECTED", plan["blockers"])
        self.assertEqual(len(plan["scenario"]["scenario_sha256"]), 64)
        self.assertEqual(len(plan["subject"]["adapter_sha256"]), 64)
        self.assertEqual(len(plan["readiness_gate_sha256"]), 64)

    def test_enforced_trust_root_can_be_ready(self):
        plan = self.plan(
            self.scenario(),
            trust_root_status="PROTECTED",
            stable_promotion_enabled=True,
        )
        self.assertEqual(plan["status"], "READY")
        self.assertEqual(plan["blockers"], [])
        self.assertEqual(
            plan["subject"]["required_secret_env"], "OPENAI_API_KEY"
        )
        self.assertEqual(
            plan["evaluators"]["a"]["required_secret_env"],
            "GEMINI_API_KEY",
        )
        self.assertEqual(
            plan["evaluators"]["b"]["required_secret_env"],
            "OPENAI_API_KEY",
        )
        self.assertEqual(
            plan["evaluators"]["a"]["request_kind"],
            "mgtest.ai.evaluator",
        )

    def test_tool_scenario_is_validated_but_currently_blocked(self):
        plan = self.plan(self.scenario(tools=OFFLINE_TOOL_PROFILE))
        self.assertEqual(plan["status"], "BLOCKED")
        self.assertEqual(
            plan["execution_mode"], "tool-enabled-dual-evaluator-v1"
        )
        self.assertEqual(
            plan["subject"]["tool_configuration"], OFFLINE_TOOL_PROFILE
        )
        self.assertEqual(
            plan["subject"]["continuation_chain_contract"],
            CONTINUATION_CHAIN_CONTRACT,
        )
        self.assertEqual(
            plan["evaluators"]["a"]["request_kind"],
            "mgtest.ai.tool-evaluator",
        )
        self.assertIn(
            "PROVIDER_TOOL_SUBJECT_LIVE_NOT_AUTHORIZED", plan["blockers"]
        )
        self.assertIn(
            "PROVIDER_MODEL_TOOL_CAPABILITY_UNVERIFIED", plan["blockers"]
        )
        self.assertIn(
            "REPOSITORY_TRUST_ROOT_NOT_ENFORCED", plan["blockers"]
        )

    def test_tool_scenario_can_only_be_ready_when_all_authorities_are_true(self):
        plan = self.plan(
            self.scenario(tools=OFFLINE_TOOL_PROFILE),
            trust_root_status="PROTECTED",
            stable_promotion_enabled=True,
            provider_tool_subject_authorized=True,
            provider_model_tool_capability_verified=True,
        )
        self.assertEqual(plan["status"], "READY")
        self.assertEqual(plan["blockers"], [])
        self.assertTrue(plan["subject"]["live_tool_subject_authorized"])
        self.assertTrue(
            plan["subject"]["model_tool_capability_verified"]
        )
        self.assertIn(
            "function-tools+context-chain-v1",
            plan["subject"]["tool_subject_contract"],
        )

    def test_tool_authorization_alone_is_not_enough(self):
        plan = self.plan(
            self.scenario(tools=OFFLINE_TOOL_PROFILE),
            trust_root_status="PROTECTED",
            stable_promotion_enabled=True,
            provider_tool_subject_authorized=True,
            provider_model_tool_capability_verified=False,
        )
        self.assertEqual(plan["status"], "BLOCKED")
        self.assertIn(
            "PROVIDER_MODEL_TOOL_CAPABILITY_UNVERIFIED", plan["blockers"]
        )

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
        self.assertIn(
            "SUBJECT_EVALUATOR_A_SAME_MODEL_ALIAS", plan["blockers"]
        )

    def test_subject_evaluator_b_collision_blocks(self):
        plan = self.plan(
            self.scenario(),
            evaluator_b_provider="openai",
            evaluator_b_model="subject-model",
            trust_root_status="PROTECTED",
            stable_promotion_enabled=True,
        )
        self.assertEqual(plan["status"], "BLOCKED")
        self.assertIn(
            "SUBJECT_EVALUATOR_B_SAME_MODEL_ALIAS", plan["blockers"]
        )

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

    def test_unsupported_tool_capability_rejected(self):
        with self.assertRaises(ReadinessError):
            self.plan(self.scenario(tools="web"))

    def test_model_network_capability_rejected(self):
        with self.assertRaises(ReadinessError):
            self.plan(self.scenario(network=True))

    def test_invalid_commit_rejected(self):
        with self.assertRaises(ReadinessError):
            self.plan(self.scenario(), mgtest_commit="main")

    def test_authority_flags_must_be_boolean(self):
        with self.assertRaises(ReadinessError):
            self.plan(
                self.scenario(tools=OFFLINE_TOOL_PROFILE),
                provider_tool_subject_authorized="yes",
            )


if __name__ == "__main__":
    unittest.main()
