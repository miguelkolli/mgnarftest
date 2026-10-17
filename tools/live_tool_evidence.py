#!/usr/bin/env python3
import hashlib
import json
import re
from pathlib import Path

HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
AUTH_TYPE = "mgtest.ai.provider-tool-subject-authorization"
CAPABILITY_TYPE = "mgtest.ai.provider-model-tool-capability"
LIVE_TOOL_SCOPE = "credentialed-live-offline-tool-subject"


class LiveToolEvidenceError(ValueError):
    pass


def _canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha(value):
    if not isinstance(value, (bytes, bytearray)):
        value = _canonical(value)
    return hashlib.sha256(value).hexdigest()


def seal_evidence(body):
    if not isinstance(body, dict) or "evidence_sha256" in body:
        raise LiveToolEvidenceError("evidence body invalid")
    value = json.loads(json.dumps(body))
    value["evidence_sha256"] = _sha(value)
    return value


def load_evidence(path):
    path = Path(path).resolve()
    try:
        raw = path.read_bytes()
        value = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise LiveToolEvidenceError("evidence unreadable/invalid JSON") from exc
    if not isinstance(value, dict):
        raise LiveToolEvidenceError("evidence must be object")
    return value, _sha(raw)


def _text(value, where):
    if not isinstance(value, str) or not value.strip():
        raise LiveToolEvidenceError(f"{where} required")
    return value.strip()


def _revision(value, where):
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise LiveToolEvidenceError(f"{where} must be positive integer")
    return value


def _commit(value):
    if not isinstance(value, str) or not HEX40.fullmatch(value):
        raise LiveToolEvidenceError("target_mgtest_commit invalid")
    return value


def _hash(value, where):
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise LiveToolEvidenceError(f"{where} invalid")
    return value


def _verify_seal(value):
    supplied = value.get("evidence_sha256")
    _hash(supplied, "evidence_sha256")
    body = dict(value)
    del body["evidence_sha256"]
    expected = _sha(body)
    if supplied != expected:
        raise LiveToolEvidenceError("evidence hash mismatch")
    return supplied


def validate_authorization(
    value,
    *,
    mgtest_commit,
    provider,
    model,
    adapter_sha256,
    tool_subject_contract,
    continuation_chain_contract,
):
    expected_fields = {
        "schema_version",
        "evidence_type",
        "status",
        "scope",
        "authority_id",
        "authority_revision",
        "target_mgtest_commit",
        "provider",
        "model",
        "adapter_sha256",
        "tool_subject_contract",
        "continuation_chain_contract",
        "evidence_sha256",
    }
    if not isinstance(value, dict) or set(value) != expected_fields:
        raise LiveToolEvidenceError("authorization evidence fields invalid")
    if value["schema_version"] != 1 or value["evidence_type"] != AUTH_TYPE:
        raise LiveToolEvidenceError("authorization evidence type/version invalid")
    if value["status"] != "AUTHORIZED" or value["scope"] != LIVE_TOOL_SCOPE:
        raise LiveToolEvidenceError("authorization decision/scope invalid")
    authority_id = _text(value["authority_id"], "authority_id")
    revision = _revision(value["authority_revision"], "authority_revision")
    if _commit(value["target_mgtest_commit"]) != mgtest_commit:
        raise LiveToolEvidenceError("authorization MGnarfTest commit mismatch")
    if value["provider"] != provider or value["model"] != model:
        raise LiveToolEvidenceError("authorization provider/model mismatch")
    if _hash(value["adapter_sha256"], "authorization adapter_sha256") != adapter_sha256:
        raise LiveToolEvidenceError("authorization adapter mismatch")
    if value["tool_subject_contract"] != tool_subject_contract:
        raise LiveToolEvidenceError("authorization tool subject contract mismatch")
    if value["continuation_chain_contract"] != continuation_chain_contract:
        raise LiveToolEvidenceError("authorization continuation contract mismatch")
    evidence_sha = _verify_seal(value)
    return {
        "status": "VALID",
        "authority_id": authority_id,
        "authority_revision": revision,
        "evidence_sha256": evidence_sha,
    }


def validate_capability(
    value,
    *,
    mgtest_commit,
    provider,
    model,
    adapter_sha256,
    tool_subject_contract,
    continuation_context_kind,
    continuation_chain_contract,
):
    expected_fields = {
        "schema_version",
        "evidence_type",
        "status",
        "verifier_id",
        "verification_revision",
        "verification_method",
        "target_mgtest_commit",
        "provider",
        "model",
        "immutable_version",
        "adapter_sha256",
        "tool_subject_contract",
        "continuation_context_kind",
        "continuation_chain_contract",
        "evidence_sha256",
    }
    if not isinstance(value, dict) or set(value) != expected_fields:
        raise LiveToolEvidenceError("capability evidence fields invalid")
    if value["schema_version"] != 1 or value["evidence_type"] != CAPABILITY_TYPE:
        raise LiveToolEvidenceError("capability evidence type/version invalid")
    if value["status"] != "VERIFIED":
        raise LiveToolEvidenceError("capability evidence status invalid")
    verifier_id = _text(value["verifier_id"], "verifier_id")
    revision = _revision(value["verification_revision"], "verification_revision")
    method = _text(value["verification_method"], "verification_method")
    if _commit(value["target_mgtest_commit"]) != mgtest_commit:
        raise LiveToolEvidenceError("capability MGnarfTest commit mismatch")
    if value["provider"] != provider or value["model"] != model:
        raise LiveToolEvidenceError("capability provider/model mismatch")
    immutable = value["immutable_version"]
    if immutable is not None:
        immutable = _text(immutable, "immutable_version")
    if _hash(value["adapter_sha256"], "capability adapter_sha256") != adapter_sha256:
        raise LiveToolEvidenceError("capability adapter mismatch")
    if value["tool_subject_contract"] != tool_subject_contract:
        raise LiveToolEvidenceError("capability tool subject contract mismatch")
    if value["continuation_context_kind"] != continuation_context_kind:
        raise LiveToolEvidenceError("capability continuation context mismatch")
    if value["continuation_chain_contract"] != continuation_chain_contract:
        raise LiveToolEvidenceError("capability continuation contract mismatch")
    evidence_sha = _verify_seal(value)
    return {
        "status": "VALID",
        "verifier_id": verifier_id,
        "verification_revision": revision,
        "verification_method": method,
        "immutable_version": immutable,
        "evidence_sha256": evidence_sha,
    }
