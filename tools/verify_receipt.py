#!/usr/bin/env python3
import hashlib
import json
import os
import re
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
REGISTRY_REPOSITORY = "miguelkolli/mgnarftest"
PINNED_IMAGE = "python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1"


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
    if hashlib.sha256(canonical).hexdigest() != claimed_hash:
        die("receipt_sha256 mismatch")

    test = require_dict(receipt, "test")
    test_id = test.get("id")
    version = test.get("version")
    if not isinstance(test_id, str) or not test_id.startswith("MGTEST-"):
        die("invalid test.id")
    if not isinstance(version, int) or isinstance(version, bool) or version < 1:
        die("invalid test.version")
    test_dir = ROOT / "tests" / test_id / f"v{version}"
    manifest_path = test_dir / "manifest.json"
    if not manifest_path.is_file():
        die("bound manifest missing")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("test_id") != test_id or manifest.get("test_version") != version:
        die("manifest identity/version mismatch")
    raw_entrypoint = (manifest.get("execution") or {}).get("entrypoint")
    argv = shlex.split(raw_entrypoint) if isinstance(raw_entrypoint, str) else []
    if len(argv) != 2 or argv[0] not in {"python", "python3"}:
        die("manifest entrypoint is unsupported")
    test_file = ROOT / argv[1]
    expected_test_file = test_dir / "test.py"
    if test_file.resolve() != expected_test_file.resolve() or not test_file.is_file():
        die("bound test file missing or unexpected")
    if test.get("manifest_sha256") != sha256_file(manifest_path):
        die("manifest hash mismatch")
    if test.get("test_sha256") != sha256_file(test_file):
        die("test hash mismatch")

    mgtest = require_dict(receipt, "mgtest")
    if mgtest.get("repository") != REGISTRY_REPOSITORY:
        die("wrong MGnarfTest repository")
    subject_sha = mgtest.get("commit")
    if not isinstance(subject_sha, str) or not HEX40.fullmatch(subject_sha):
        die("invalid MGnarfTest commit")
    expected_sha = os.environ.get("MGTEST_SHA", "").strip()
    if expected_sha and subject_sha != expected_sha:
        die("MGnarfTest commit does not match expected exact head")

    target = require_dict(receipt, "target")
    manifest_target = manifest.get("target") or {}
    for key in ("repository", "release", "commit"):
        if target.get(key) != manifest_target.get(key):
            die(f"target.{key} does not match manifest")

    expected_receipt = require_dict(receipt, "expected")
    manifest_allowed = (manifest.get("expected") or {}).get("allowed_results")
    receipt_allowed = expected_receipt.get("allowed_results")
    if not isinstance(manifest_allowed, list) or receipt_allowed != manifest_allowed:
        die("expected.allowed_results binding mismatch")

    execution = require_dict(receipt, "execution")
    result = execution.get("result")
    if execution.get("provider") != "github-actions":
        die("invalid execution provider")
    if result not in receipt_allowed:
        die("execution result is not permitted by frozen expected.allowed_results")
    if result != "PASS":
        die("execution result is not PASS")
    if execution.get("container_image") != PINNED_IMAGE:
        die("container image binding mismatch")
    manifest_timeout = (manifest.get("execution") or {}).get("timeout_seconds")
    if execution.get("timeout_seconds") != manifest_timeout:
        die("timeout_seconds binding mismatch")
    isolation = require_dict(execution, "isolation")
    expected_isolation = {"network": "none", "rootfs": "read-only", "capabilities": "drop-all", "no_new_privileges": True, "user": "65534:65534"}
    if isolation != expected_isolation:
        die("isolation contract mismatch")

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
