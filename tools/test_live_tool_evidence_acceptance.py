import unittest

from tools.live_tool_evidence_acceptance import (
    EvidenceAcceptanceError,
    RECORD_TYPE,
    seal_record,
    validate_record,
)


def review(identity, review_id="review-1"):
    return {
        "reviewer_identity": identity,
        "review_id": review_id,
        "reviewed_evidence_sha256": "b" * 64,
        "reviewed_mgtest_commit": "c" * 40,
        "decision": "APPROVED",
    }


def record(status="PROPOSED"):
    body = {
        "schema_version": 1,
        "record_type": RECORD_TYPE,
        "status": status,
        "evidence_kind": "authorization",
        "evidence_file_sha256": "a" * 64,
        "evidence_sha256": "b" * 64,
        "target_mgtest_commit": "c" * 40,
        "author_identity": "author",
        "reviewer_a": None,
        "reviewer_b": None,
        "external_reviewer_identity": None,
        "accepted_revision": None,
        "trust_root_receipt_sha256": None,
    }
    if status == "REVIEW-A":
        body["reviewer_a"] = review("reviewer-a", "review-a")
    elif status == "REVIEW-B":
        body["reviewer_a"] = review("reviewer-a", "review-a")
        body["reviewer_b"] = review("reviewer-b", "review-b")
    elif status == "ACCEPTED":
        body["reviewer_a"] = review("reviewer-a", "review-a")
        body["reviewer_b"] = review("external-reviewer", "review-b")
        body["external_reviewer_identity"] = "external-reviewer"
        body["accepted_revision"] = 1
        body["trust_root_receipt_sha256"] = "d" * 64
    return seal_record(body)


class EvidenceAcceptanceTests(unittest.TestCase):
    def test_proposed_is_structurally_valid_without_reviews(self):
        result = validate_record(record())
        self.assertEqual(result["status"], "STRUCTURALLY_VALID")
        self.assertEqual(result["lifecycle_status"], "PROPOSED")
        self.assertFalse(result["authenticated_identity_verified"])

    def test_review_a_requires_exactly_one_distinct_reviewer(self):
        result = validate_record(record("REVIEW-A"))
        self.assertEqual(result["reviewer_a_identity"], "reviewer-a")
        value = record("REVIEW-A")
        value["reviewer_a"]["reviewer_identity"] = "author"
        value = seal_record(
            {k: v for k, v in value.items() if k != "record_sha256"}
        )
        with self.assertRaisesRegex(EvidenceAcceptanceError, "author cannot"):
            validate_record(value)

    def test_review_b_requires_two_distinct_reviewers(self):
        result = validate_record(record("REVIEW-B"))
        self.assertEqual(result["reviewer_b_identity"], "reviewer-b")
        value = record("REVIEW-B")
        value["reviewer_b"]["reviewer_identity"] = "reviewer-a"
        value = seal_record(
            {k: v for k, v in value.items() if k != "record_sha256"}
        )
        with self.assertRaisesRegex(
            EvidenceAcceptanceError, "reviewers must be distinct"
        ):
            validate_record(value)

    def test_accepted_requires_external_approver_and_trust_receipt(self):
        result = validate_record(record("ACCEPTED"))
        self.assertEqual(result["lifecycle_status"], "ACCEPTED")
        self.assertEqual(
            result["external_reviewer_identity"], "external-reviewer"
        )
        value = record("ACCEPTED")
        value["external_reviewer_identity"] = "someone-else"
        value = seal_record(
            {k: v for k, v in value.items() if k != "record_sha256"}
        )
        with self.assertRaisesRegex(EvidenceAcceptanceError, "external reviewer"):
            validate_record(value)

    def test_accepted_without_trust_receipt_is_rejected(self):
        value = record("ACCEPTED")
        value["trust_root_receipt_sha256"] = None
        value = seal_record(
            {k: v for k, v in value.items() if k != "record_sha256"}
        )
        with self.assertRaisesRegex(
            EvidenceAcceptanceError, "trust_root_receipt"
        ):
            validate_record(value)

    def test_review_evidence_must_bind_same_evidence_and_commit(self):
        value = record("REVIEW-B")
        value["reviewer_b"]["reviewed_evidence_sha256"] = "e" * 64
        value = seal_record(
            {k: v for k, v in value.items() if k != "record_sha256"}
        )
        with self.assertRaisesRegex(
            EvidenceAcceptanceError, "evidence binding mismatch"
        ):
            validate_record(value)

    def test_resealed_status_upgrade_without_required_reviews_is_rejected(self):
        value = record()
        body = {k: v for k, v in value.items() if k != "record_sha256"}
        body["status"] = "ACCEPTED"
        forged = seal_record(body)
        with self.assertRaises(EvidenceAcceptanceError):
            validate_record(forged)

    def test_record_tamper_is_rejected(self):
        value = record("REVIEW-A")
        value["evidence_file_sha256"] = "e" * 64
        with self.assertRaisesRegex(
            EvidenceAcceptanceError, "record hash mismatch"
        ):
            validate_record(value)


if __name__ == "__main__":
    unittest.main()
