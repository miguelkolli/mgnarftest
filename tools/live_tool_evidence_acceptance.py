#!/usr/bin/env python3
import hashlib
import json
import re

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
RECORD_TYPE = "mgtest.ai.live-tool-evidence-acceptance"
STATUSES = {
    "PROPOSED",
    "REVIEW-A",
    "REVIEW-B",
    "ACCEPTED",
    "NEEDS-REVISION",
    "REJECTED",
}
EVIDENCE_KINDS = {"authorization", "capability"}


class EvidenceAcceptanceError(ValueError):
    pass


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha(value):
    if not isinstance(value, (bytes, bytearray)):
        value = _canonical(value)
    return hashlib.sha256(value).hexdigest()


def seal_record(body):
    if not isinstance(body, dict) or "record_sha256" in body:
        raise EvidenceAcceptanceError("record body invalid")
    value = json.loads(json.dumps(body))
    value["record_sha256"] = _sha(value)
    return value


def _hex40(value, where):
    if not isinstance(value, str) or not HEX40.fullmatch(value):
        raise EvidenceAcceptanceError(f"{where} invalid")
    return value


def _hex64(value, where):
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise EvidenceAcceptanceError(f"{where} invalid")
    return value


def _identity(value, where):
    if not isinstance(value, str) or not value.strip():
        raise EvidenceAcceptanceError(f"{where} required")
    return value.strip()


def _review(value, where, evidence_sha256, target_mgtest_commit):
    expected = {
        "reviewer_identity",
        "review_id",
        "reviewed_evidence_sha256",
        "reviewed_mgtest_commit",
        "decision",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise EvidenceAcceptanceError(f"{where} fields invalid")
    identity = _identity(value["reviewer_identity"], f"{where}.reviewer_identity")
    _identity(value["review_id"], f"{where}.review_id")
    if (
        _hex64(
            value["reviewed_evidence_sha256"],
            f"{where}.reviewed_evidence_sha256",
        )
        != evidence_sha256
    ):
        raise EvidenceAcceptanceError(f"{where} evidence binding mismatch")
    if (
        _hex40(
            value["reviewed_mgtest_commit"],
            f"{where}.reviewed_mgtest_commit",
        )
        != target_mgtest_commit
    ):
        raise EvidenceAcceptanceError(f"{where} MGnarfTest commit mismatch")
    if value["decision"] != "APPROVED":
        raise EvidenceAcceptanceError(f"{where} decision must be APPROVED")
    return identity


def _required_review_count(status):
    if status in {"PROPOSED", "NEEDS-REVISION", "REJECTED"}:
        return 0
    if status == "REVIEW-A":
        return 1
    return 2


def validate_record(value):
    expected_fields = {
        "schema_version",
        "record_type",
        "status",
        "evidence_kind",
        "evidence_file_sha256",
        "evidence_sha256",
        "target_mgtest_commit",
        "author_identity",
        "reviewer_a",
        "reviewer_b",
        "external_reviewer_identity",
        "accepted_revision",
        "trust_root_receipt_sha256",
        "record_sha256",
    }
    if not isinstance(value, dict) or set(value) != expected_fields:
        raise EvidenceAcceptanceError("acceptance record fields invalid")
    if value["schema_version"] != 1 or value["record_type"] != RECORD_TYPE:
        raise EvidenceAcceptanceError("acceptance record type/version invalid")
    status = value["status"]
    if status not in STATUSES:
        raise EvidenceAcceptanceError("acceptance status invalid")
    if value["evidence_kind"] not in EVIDENCE_KINDS:
        raise EvidenceAcceptanceError("evidence_kind invalid")
    evidence_file_sha = _hex64(
        value["evidence_file_sha256"], "evidence_file_sha256"
    )
    evidence_sha = _hex64(value["evidence_sha256"], "evidence_sha256")
    target_commit = _hex40(
        value["target_mgtest_commit"], "target_mgtest_commit"
    )
    author = _identity(value["author_identity"], "author_identity")

    review_count = _required_review_count(status)
    reviewer_a = value["reviewer_a"]
    reviewer_b = value["reviewer_b"]
    a_identity = None
    b_identity = None

    if review_count == 0:
        if reviewer_a is not None or reviewer_b is not None:
            raise EvidenceAcceptanceError(
                f"{status} must not contain approval reviews"
            )
    elif review_count == 1:
        if reviewer_a is None or reviewer_b is not None:
            raise EvidenceAcceptanceError("REVIEW-A requires reviewer_a only")
        a_identity = _review(
            reviewer_a, "reviewer_a", evidence_sha, target_commit
        )
    else:
        if reviewer_a is None or reviewer_b is None:
            raise EvidenceAcceptanceError(f"{status} requires both reviewers")
        a_identity = _review(
            reviewer_a, "reviewer_a", evidence_sha, target_commit
        )
        b_identity = _review(
            reviewer_b, "reviewer_b", evidence_sha, target_commit
        )

    if a_identity is not None and a_identity == author:
        raise EvidenceAcceptanceError("author cannot be reviewer_a")
    if b_identity is not None and b_identity == author:
        raise EvidenceAcceptanceError("author cannot be reviewer_b")
    if (
        a_identity is not None
        and b_identity is not None
        and a_identity == b_identity
    ):
        raise EvidenceAcceptanceError("reviewers must be distinct")

    external = value["external_reviewer_identity"]
    accepted_revision = value["accepted_revision"]
    trust_receipt = value["trust_root_receipt_sha256"]
    if status == "ACCEPTED":
        external = _identity(external, "external_reviewer_identity")
        if external not in {a_identity, b_identity}:
            raise EvidenceAcceptanceError(
                "external reviewer must be one of the approving reviewers"
            )
        if (
            not isinstance(accepted_revision, int)
            or isinstance(accepted_revision, bool)
            or accepted_revision < 1
        ):
            raise EvidenceAcceptanceError(
                "accepted_revision must be positive integer"
            )
        _hex64(trust_receipt, "trust_root_receipt_sha256")
    else:
        if external is not None:
            raise EvidenceAcceptanceError(
                "external_reviewer_identity allowed only for ACCEPTED"
            )
        if accepted_revision is not None:
            raise EvidenceAcceptanceError(
                "accepted_revision allowed only for ACCEPTED"
            )
        if trust_receipt is not None:
            raise EvidenceAcceptanceError(
                "trust_root_receipt_sha256 allowed only for ACCEPTED"
            )

    supplied = _hex64(value["record_sha256"], "record_sha256")
    body = dict(value)
    del body["record_sha256"]
    if supplied != _sha(body):
        raise EvidenceAcceptanceError("acceptance record hash mismatch")

    return {
        "status": "STRUCTURALLY_VALID",
        "lifecycle_status": status,
        "evidence_kind": value["evidence_kind"],
        "evidence_file_sha256": evidence_file_sha,
        "evidence_sha256": evidence_sha,
        "target_mgtest_commit": target_commit,
        "author_identity": author,
        "reviewer_a_identity": a_identity,
        "reviewer_b_identity": b_identity,
        "external_reviewer_identity": external,
        "record_sha256": supplied,
        "authenticated_identity_verified": False,
    }
