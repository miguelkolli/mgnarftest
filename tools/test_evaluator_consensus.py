import unittest

from tools.ai_runner_protocol import seal
from tools.evaluator_consensus import (
    ConsensusError,
    build_consensus_receipt,
    verify_consensus_receipt,
)


class ConsensusTests(unittest.TestCase):
    def subject(self, provider="subject-provider", model="subject-model", immutable="subject-v1"):
        return {"provider": provider, "model": model, "immutable_version": immutable}

    def evaluator(self, *, evaluator_id, provider, model, immutable, result, reason="rubric"):
        return {
            "evaluator_id": evaluator_id,
            "evaluator_version": "1",
            "provider": provider,
            "model": model,
            "immutable_version": immutable,
            "result": result,
            "reason": reason,
        }

    def pair(self, a="COMPLIANT", b="COMPLIANT"):
        return (
            self.evaluator(evaluator_id="eval-a", provider="provider-a", model="judge-a", immutable="a-v1", result=a),
            self.evaluator(evaluator_id="eval-b", provider="provider-b", model="judge-b", immutable="b-v1", result=b),
        )

    def build(self, a="COMPLIANT", b="COMPLIANT", subject=None, pair=None):
        ea, eb = pair or self.pair(a, b)
        return build_consensus_receipt("a" * 64, subject or self.subject(), ea, eb)

    def test_two_compliant_agree(self):
        receipt = self.build()
        self.assertEqual(receipt["consensus"]["status"], "AGREED")
        self.assertEqual(receipt["consensus"]["result"], "COMPLIANT")
        self.assertTrue(verify_consensus_receipt(receipt))

    def test_one_violation_is_conservative_violation(self):
        receipt = self.build("VIOLATION", "COMPLIANT")
        self.assertEqual(receipt["consensus"]["status"], "CONSERVATIVE_VIOLATION")
        self.assertEqual(receipt["consensus"]["result"], "VIOLATION")

    def test_non_violation_disagreement_is_inconclusive(self):
        receipt = self.build("COMPLIANT", "INCONCLUSIVE")
        self.assertEqual(receipt["consensus"]["status"], "DISAGREEMENT")
        self.assertEqual(receipt["consensus"]["result"], "INCONCLUSIVE")

    def test_same_underlying_evaluator_identity_blocks(self):
        pair = (
            self.evaluator(evaluator_id="logical-a", provider="same", model="judge", immutable="v1", result="COMPLIANT"),
            self.evaluator(evaluator_id="logical-b", provider="same", model="judge", immutable="v1", result="COMPLIANT"),
        )
        receipt = self.build(pair=pair)
        self.assertEqual(receipt["consensus"]["status"], "BLOCKED")
        self.assertEqual(receipt["consensus"]["result"], "ERROR")
        self.assertIn("EVALUATOR_PAIR_IDENTITY_COLLISION", receipt["consensus"]["blockers"])

    def test_evaluator_subject_identity_collision_blocks(self):
        pair = (
            self.evaluator(evaluator_id="eval-a", provider="subject-provider", model="subject-model", immutable="subject-v1", result="COMPLIANT"),
            self.evaluator(evaluator_id="eval-b", provider="other", model="judge", immutable="v1", result="COMPLIANT"),
        )
        receipt = self.build(pair=pair)
        self.assertEqual(receipt["consensus"]["result"], "ERROR")
        self.assertIn("EVALUATOR_A_SUBJECT_IDENTITY_COLLISION", receipt["consensus"]["blockers"])

    def test_resealed_false_consensus_is_rejected(self):
        receipt = self.build("COMPLIANT", "INCONCLUSIVE")
        receipt["consensus"] = {"status": "AGREED", "result": "COMPLIANT", "blockers": []}
        seal(receipt)
        with self.assertRaises(ConsensusError):
            verify_consensus_receipt(receipt)


if __name__ == "__main__":
    unittest.main()
