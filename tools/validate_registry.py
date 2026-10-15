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
STATUSES = {"PROPOSED", "REVIEW-A", "REVIEW-B", "STABLE", "BLOCKED", "REJECTED", "NEEDS-REVISION"}
RESULTS = {"PASS", "FAIL", "BLOCKED", "UNVERIFIED", "LIMITATION_CONFIRMED"}


def fail(path: Path, message: str) -> None:
    raise ValueError(f"{path.relative_to(ROOT)}: {message}")


def require(obj, key, path):
    if key not in obj:
        fail(path, f"missing required field: {key}")
    return obj[key]


def validate(path: Path) -> tuple[str, int]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        fail(path, f"invalid JSON: {exc}")

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
    for key in ("project", "repository", "release", "commit"):
        require(target, key, path)
    if not isinstance(target["commit"], str) or not HEX40.fullmatch(target["commit"]):
        fail(path, "target.commit must be an exact lowercase 40-hex Git SHA")

    purpose = require(data, "purpose", path)
    if not isinstance(purpose, str) or len(purpose.strip()) < 10:
        fail(path, "purpose is too short")

    expected = require(data, "expected", path)
    allowed = require(expected, "allowed_results", path)
    safe_condition = require(expected, "safe_condition", path)
    if not isinstance(allowed, list) or not allowed or any(item not in RESULTS for item in allowed):
        fail(path, "expected.allowed_results contains unsupported result")
    if not isinstance(safe_condition, str) or len(safe_condition.strip()) < 10:
        fail(path, "expected.safe_condition is too short")

    execution = require(data, "execution", path)
    for key in ("entrypoint", "network", "privileges", "external_dependencies"):
        require(execution, key, path)
    if not isinstance(execution["network"], bool):
        fail(path, "execution.network must be boolean")
    if not isinstance(execution["external_dependencies"], list):
        fail(path, "execution.external_dependencies must be a list")

    limits = require(data, "limits", path)
    if not isinstance(limits, list) or not limits:
        fail(path, "at least one explicit limitation is required")

    review = require(data, "review", path)
    for key in ("author", "reviewer_a", "reviewer_b", "promotion_pr"):
        require(review, key, path)

    evidence = require(data, "evidence", path)
    for key in ("result", "run_id", "artifact_hash", "receipt_sha256", "mgtest_commit", "target_commit"):
        require(evidence, key, path)
    if evidence["result"] not in RESULTS:
        fail(path, "unsupported evidence.result")

    if status == "STABLE":
        author = review["author"]
        a = review["reviewer_a"]
        b = review["reviewer_b"]
        promotion_pr = review["promotion_pr"]
        if not all(isinstance(v, str) and v.strip() for v in (author, a, b)):
            fail(path, "STABLE requires author, reviewer_a and reviewer_b identities")
        if len({author, a, b}) != 3:
            fail(path, "STABLE requires three distinct identities")
        if not isinstance(promotion_pr, int) or isinstance(promotion_pr, bool) or promotion_pr < 1:
            fail(path, "STABLE requires positive integer review.promotion_pr")
        if evidence["result"] != "PASS":
            fail(path, "STABLE requires PASS execution evidence")
        if not isinstance(evidence["run_id"], str) or not evidence["run_id"].isdigit():
            fail(path, "STABLE requires numeric-string evidence.run_id")
        if not isinstance(evidence["artifact_hash"], str) or not HEX64.fullmatch(evidence["artifact_hash"]):
            fail(path, "STABLE requires 64-hex evidence.artifact_hash")
        if not isinstance(evidence["receipt_sha256"], str) or not HEX64.fullmatch(evidence["receipt_sha256"]):
            fail(path, "STABLE requires 64-hex evidence.receipt_sha256")
        if not isinstance(evidence["mgtest_commit"], str) or not HEX40.fullmatch(evidence["mgtest_commit"]):
            fail(path, "STABLE requires exact evidence.mgtest_commit subject SHA")
        if not isinstance(evidence["target_commit"], str) or not HEX40.fullmatch(evidence["target_commit"]):
            fail(path, "STABLE requires exact evidence.target_commit")
        if evidence["target_commit"] != target["commit"]:
            fail(path, "STABLE evidence.target_commit must equal target.commit")
    else:
        if review["promotion_pr"] is not None:
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
