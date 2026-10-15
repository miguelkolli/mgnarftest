#!/usr/bin/env python3
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEST_ID = "MGTEST-NARF-ORDER-001"
TEST_VERSION = 1
TEST_DIR = ROOT / "tests" / TEST_ID / f"v{TEST_VERSION}"
TARGET_SHA = "b811a13eab9cacd9f922b1f15097aa6bf700fc01"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    subject_sha = os.environ.get("MGTEST_SHA", "").strip()
    run_id = os.environ.get("GITHUB_RUN_ID", "").strip()
    run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "").strip()
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()

    if len(subject_sha) != 40:
        raise SystemExit("MGNARFTEST RECEIPT: FAIL - MGTEST_SHA must be exact 40-hex SHA")
    if repository != "miguelkolli/mgnarftest":
        raise SystemExit("MGNARFTEST RECEIPT: FAIL - wrong repository context")
    if not run_id:
        raise SystemExit("MGNARFTEST RECEIPT: FAIL - missing GITHUB_RUN_ID")

    manifest = TEST_DIR / "manifest.json"
    test_file = TEST_DIR / "test.py"
    if not manifest.is_file() or not test_file.is_file():
        raise SystemExit("MGNARFTEST RECEIPT: FAIL - manifest or test file missing")

    receipt = {
        "schema_version": 1,
        "test": {
            "id": TEST_ID,
            "version": TEST_VERSION,
            "manifest_sha256": sha256_file(manifest),
            "test_sha256": sha256_file(test_file),
        },
        "mgtest": {
            "repository": repository,
            "commit": subject_sha,
        },
        "target": {
            "repository": "miguelkolli/mgnarf",
            "release": "v1.70",
            "commit": TARGET_SHA,
        },
        "execution": {
            "provider": "github-actions",
            "run_id": run_id,
            "run_attempt": run_attempt,
            "result": "PASS",
        },
    }

    canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    receipt["receipt_sha256"] = hashlib.sha256(canonical).hexdigest()

    out = ROOT / "evidence"
    out.mkdir(exist_ok=True)
    path = out / f"{TEST_ID}-v{TEST_VERSION}-{run_id}.json"
    path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"MGNARFTEST RECEIPT: PASS - {path.relative_to(ROOT)}")
    print(f"receipt_sha256={receipt['receipt_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
