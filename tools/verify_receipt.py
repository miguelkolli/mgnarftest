#!/usr/bin/env python3
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
TARGET_REPOSITORY = "miguelkolli/mgnarf"
TARGET_RELEASE = "v1.70"
TARGET_SHA = "b811a13eab9cacd9f922b1f15097aa6bf700fc01"
MGTEST_REPOSITORY = "miguelkolli/mgnarftest"


def die(message: str) -> None:
    raise SystemExit(f"MGNARFTEST RECEIPT VERIFY: FAIL - {message}")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def require_dict(obj, key):
    value = obj.get(key)
    if not isinstance(value, dict):
        die(f"missing/invalid object: {key}")
    return value


def main() -> int:
    if len(sys.argv) != 2:
        die("usage: verify_receipt.py <receipt.json>")

    path = Path(sys.argv[1])
    if not path.is_file():
        die("receipt file missing")
    try:
        receipt = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        die(f"invalid JSON: {exc}")

    if receipt.get("schema_version") != 1:
        die("schema_version must be 1")

    claimed_hash = receipt.get("receipt_sha256")
    if not isinstance(claimed_hash, str) or not HEX64.fullmatch(claimed_hash):
        die("invalid receipt_sha256")
    unsigned = dict(receipt)
    unsigned.pop("receipt_sha256", None)
    canonical = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
    actual_hash = hashlib.sha256(canonical).hexdigest()
    if actual_hash != claimed_hash:
        die("receipt_sha256 mismatch")

    test = require_dict(receipt, "test")
    test_id = test.get("id")
    version = test.get("version")
    if not isinstance(test_id, str) or not test_id.startswith("MGTEST-"):
        die("invalid test.id")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        die("invalid test.version")
    test_dir = ROOT / "tests" / test_id / f"v{version}"
    manifest = test_dir / "manifest.json"
    test_file = test_dir / "test.py"
    if not manifest.is_file() or not test_file.is_file():
        die("bound manifest/test file missing")
    if test.get("manifest_sha256") != sha256_file(manifest):
        die("manifest hash mismatch")
    if test.get("test_sha256") != sha256_file(test_file):
        die("test hash mismatch")

    mgtest = require_dict(receipt, "mgtest")
    if mgtest.get("repository") != MGTEST_REPOSITORY:
        die("wrong MGnarfTest repository")
    subject_sha = mgtest.get("commit")
    if not isinstance(subject_sha, str) or not HEX40.fullmatch(subject_sha):
        die("invalid MGnarfTest commit")
    expected_sha = os.environ.get("MGTEST_SHA", "").strip()
    if expected_sha and subject_sha != expected_sha:
        die("MGnarfTest commit does not match expected exact head")

    target = require_dict(receipt, "target")
    if target.get("repository") != TARGET_REPOSITORY or target.get("release") != TARGET_RELEASE or target.get("commit") != TARGET_SHA:
        die("wrong target binding")

    execution = require_dict(receipt, "execution")
    if execution.get("provider") != "github-actions" or execution.get("result") != "PASS":
        die("invalid execution provider/result")
    run_id = str(execution.get("run_id", "")).strip()
    if not run_id.isdigit():
        die("invalid run_id")
    expected_run_id = os.environ.get("GITHUB_RUN_ID", "").strip()
    if expected_run_id and run_id != expected_run_id:
        die("run_id does not match current GitHub Actions run")

    print(f"MGNARFTEST RECEIPT VERIFY: PASS - {path}")
    print(f"receipt_sha256={claimed_hash}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
