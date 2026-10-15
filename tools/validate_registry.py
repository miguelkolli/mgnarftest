#!/usr/bin/env python3
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFESTS = sorted(ROOT.glob("tests/*/*/manifest.json"))
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ID_RE = re.compile(r"^MGTEST-[A-Z0-9]+-[A-Z0-9-]+-[0-9]{3}$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
STATUSES = {"PROPOSED", "REVIEW-A", "REVIEW-B", "STABLE", "BLOCKED", "REJECTED", "NEEDS-REVISION", "RETIRED"}
RUNNABLE_STATUSES = {"PROPOSED", "REVIEW-A", "REVIEW-B", "STABLE"}
RESULTS = {"PASS", "FAIL", "BLOCKED", "UNVERIFIED", "LIMITATION_CONFIRMED"}
MAX_TIMEOUT_SECONDS = 300
TOP_KEYS = {"schema_version", "test_id", "test_version", "status", "target", "purpose", "expected", "execution", "limits", "review", "evidence"}
TARGET_KEYS = {"project", "repository", "release", "commit"}
EXPECTED_KEYS = {"allowed_results", "safe_condition"}
EXECUTION_KEYS = {"entrypoint", "network", "privileges", "external_dependencies", "timeout_seconds"}
REVIEW_KEYS = {"author", "reviewer_a", "reviewer_b", "promotion_pr"}
EVIDENCE_KEYS = {"result", "run_id", "artifact_hash", "receipt_sha256", "mgtest_commit", "target_commit"}


def fail(path: Path, message: str) -> None:
    raise ValueError(f"{path.relative_to(ROOT)}: {message}")


def require(obj, key, path):
    if key not in obj:
        fail(path, f"missing required field: {key}")
    return obj[key]


def reject_unknown(obj, allowed_keys: set[str], path: Path, context: str) -> None:
    if not isinstance(obj, dict):
        fail(path, f"{context} must be an object")
    unknown = sorted(set(obj) - allowed_keys)
    if unknown:
        fail(path, f"{context} contains unknown field(s): {', '.join(unknown)}")


def optional_hex(value, regex, path: Path, field: str) -> None:
    if value is not None and (not isinstance(value, str) or not regex.fullmatch(value)):
        fail(path, f"{field} must be null or exact lowercase hex")


def validate(path: Path) -> tuple[str, int]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(path, f"invalid JSON: {exc}")
    reject_unknown(data, TOP_KEYS, path, "manifest")

    if require(data, "schema_version", path) != 1:
        fail(path, "schema_version must be 1")

    test_id = require(data, "test_id", path)
    version = require(data, "test_version", path)
    status = require(data, "status", path)
    if not isinstance(test_id, str) or not ID_RE.fullmatch(test_id):
        fail(path, "invalid test_id")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        fail(path, "test_version must be a positive integer")
    if status not in STATUSES:
        fail(path, f"invalid status: {status}")

    expected_dir = ROOT / "tests" / test_id / f"v{version}"
    if path.parent != expected_dir:
        fail(path, f"path must be tests/{test_id}/v{version}/manifest.json")

    target = require(data, "target", path)
    reject_unknown(target, TARGET_KEYS, path, "target")
    for key in TARGET_KEYS:
        require(target, key, path)
    if not isinstance(target["project"], str) or not target["project"]:
        fail(path, "target.project must be a non-empty string")
    if not isinstance(target["repository"], str) or not REPO_RE.fullmatch(target["repository"]):
        fail(path, "target.repository must be owner/name")
    if not isinstance(target["release"], str) or not target["release"]:
        fail(path, "target.release must be a non-empty string")
    if not isinstance(target["commit"], str) or not HEX40.fullmatch(target["commit"]):
        fail(path, "target.commit must be an exact lowercase 40-hex Git SHA")

    purpose = require(data, "purpose", path)
    if not isinstance(purpose, str) or len(purpose.strip()) < 10:
        fail(path, "purpose is too short")

    expected = require(data, "expected", path)
    reject_unknown(expected, EXPECTED_KEYS, path, "expected")
    allowed = require(expected, "allowed_results", path)
    safe_condition = require(expected, "safe_condition", path)
    if not isinstance(allowed, list) or not allowed or any(item not in RESULTS for item in allowed):
        fail(path, "expected.allowed_results contains unsupported result")
    if len(set(allowed)) != len(allowed):
        fail(path, "expected.allowed_results must not contain duplicates")
    if status in RUNNABLE_STATUSES and "PASS" not in allowed:
        fail(path, "runnable test must explicitly allow PASS before execution")
    if not isinstance(safe_condition, str) or len(safe_condition.strip()) < 10:
        fail(path, "expected.safe_condition is too short")

    execution = require(data, "execution", path)
    reject_unknown(execution, EXECUTION_KEYS, path, "execution")
    for key in EXECUTION_KEYS:
        require(execution, key, path)
    if not isinstance(execution["entrypoint"], str) or not execution["entrypoint"]:
        fail(path, "execution.entrypoint must be a non-empty string")
    if not isinstance(execution["network"], bool):
        fail(path, "execution.network must be boolean")
    if not isinstance(execution["privileges"], str) or not execution["privileges"]:
        fail(path, "execution.privileges must be a non-empty string")
    if not isinstance(execution["external_dependencies"], list) or any(not isinstance(item, str) for item in execution["external_dependencies"]):
        fail(path, "execution.external_dependencies must be a list of strings")
    timeout_seconds = execution["timeout_seconds"]
    if (
        not isinstance(timeout_seconds, int)
        or isinstance(timeout_seconds, bool)
        or timeout_seconds < 1
        or timeout_seconds > MAX_TIMEOUT_SECONDS
    ):
        fail(path, f"execution.timeout_seconds must be integer 1..{MAX_TIMEOUT_SECONDS}")

    limits = require(data, "limits", path)
    if not isinstance(limits, list) or not limits or any(not isinstance(item, str) or len(item) < 3 for item in limits):
        fail(path, "limits must contain at least one string of length >= 3")

    review = require(data, "review", path)
    reject_unknown(review, REVIEW_KEYS, path, "review")
    for key in REVIEW_KEYS:
        require(review, key, path)
    for key in ("author", "reviewer_a", "reviewer_b"):
        if review[key] is not None and not isinstance(review[key], str):
            fail(path, f"review.{key} must be string or null")
    promotion_pr = review["promotion_pr"]
    if promotion_pr is not None and (not isinstance(promotion_pr, int) or isinstance(promotion_pr, bool) or promotion_pr < 1):
        fail(path, "review.promotion_pr must be null or a positive integer")

    evidence = require(data, "evidence", path)
    reject_unknown(evidence, EVIDENCE_KEYS, path, "evidence")
    for key in EVIDENCE_KEYS:
        require(evidence, key, path)
    if evidence["result"] not in RESULTS:
        fail(path, "unsupported evidence.result")
    if evidence["run_id"] is not None and not isinstance(evidence["run_id"], str):
        fail(path, "evidence.run_id must be string or null")
    optional_hex(evidence["artifact_hash"], HEX64, path, "evidence.artifact_hash")
    optional_hex(evidence["receipt_sha256"], HEX64, path, "evidence.receipt_sha256")
    optional_hex(evidence["mgtest_commit"], HEX40, path, "evidence.mgtest_commit")
    optional_hex(evidence["target_commit"], HEX40, path, "evidence.target_commit")

    if status == "STABLE":
        author = review["author"]
        a = review["reviewer_a"]
        b = review["reviewer_b"]
        if not all(isinstance(v, str) and v.strip() for v in (author, a, b)):
            fail(path, "STABLE requires author, reviewer_a and reviewer_b identities")
        if len({author, a, b}) != 3:
            fail(path, "STABLE requires three distinct identities")
        if promotion_pr is None:
            fail(path, "STABLE requires positive integer review.promotion_pr")
        if evidence["result"] != "PASS":
            fail(path, "STABLE requires PASS execution evidence")
        if evidence["result"] not in allowed:
            fail(path, "STABLE evidence.result must be permitted by expected.allowed_results")
        if not isinstance(evidence["run_id"], str) or not evidence["run_id"].isdigit():
            fail(path, "STABLE requires numeric-string evidence.run_id")
        for key in ("artifact_hash", "receipt_sha256", "mgtest_commit", "target_commit"):
            if evidence[key] is None:
                fail(path, f"STABLE requires evidence.{key}")
        if evidence["target_commit"] != target["commit"]:
            fail(path, "STABLE evidence.target_commit must equal target.commit")
    else:
        if promotion_pr is not None:
            fail(path, "non-STABLE manifest must not set review.promotion_pr")
        for key in ("artifact_hash", "receipt_sha256", "mgtest_commit", "target_commit"):
            if evidence[key] is not None:
                fail(path, f"non-STABLE manifest must not set evidence.{key}")

    return test_id, version


def main() -> int:
    if not MANIFESTS:
        print("MGNARFTEST VALIDATION: FAIL - no manifests found", file=sys.stderr)
        return 1
    seen = set()
    try:
        for path in MANIFESTS:
            key = validate(path)
            if key in seen:
                fail(path, f"duplicate test identity/version: {key[0]}/v{key[1]}")
            seen.add(key)
            print(f"VALID: {key[0]}/v{key[1]} ({path.relative_to(ROOT)})")
    except ValueError as exc:
        print(f"MGNARFTEST VALIDATION: FAIL - {exc}", file=sys.stderr)
        return 1
    print(f"MGNARFTEST VALIDATION: PASS - {len(seen)} manifest(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
