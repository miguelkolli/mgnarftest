#!/usr/bin/env python3
import hashlib
import json
import os
import shlex
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNABLE_STATUSES = {"PROPOSED", "REVIEW-A", "REVIEW-B", "STABLE"}
REGISTRY_REPOSITORY = "miguelkolli/mgnarftest"
PINNED_IMAGE = "python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1"


def die(message: str) -> None:
    raise SystemExit(f"MGNARFTEST RECEIPT: FAIL - {message}")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_manifest(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        die(f"{path}: invalid manifest JSON: {exc}")
    test_id = data.get("test_id")
    version = data.get("test_version")
    expected = ROOT / "tests" / str(test_id) / f"v{version}" / "manifest.json"
    if path.resolve() != expected.resolve():
        die(f"{path}: manifest path does not match test identity/version")
    if data.get("status") not in RUNNABLE_STATUSES:
        die(f"{path}: status is not runnable")
    return data


def test_file_for(manifest: dict) -> Path:
    raw = (manifest.get("execution") or {}).get("entrypoint")
    if not isinstance(raw, str):
        die("execution.entrypoint missing")
    argv = shlex.split(raw)
    if len(argv) != 2 or argv[0] not in {"python", "python3"}:
        die("entrypoint must be exactly 'python3 <test.py>'")
    test_file = ROOT / argv[1]
    expected = ROOT / "tests" / manifest["test_id"] / f"v{manifest['test_version']}" / "test.py"
    if test_file.resolve() != expected.resolve() or not test_file.is_file():
        die("entrypoint does not bind to expected test.py")
    return test_file


def manifest_paths(argv: list[str]) -> list[Path]:
    if argv:
        return [Path(item) if Path(item).is_absolute() else ROOT / item for item in argv]
    return [
        path for path in sorted(ROOT.glob("tests/*/*/manifest.json"))
        if json.loads(path.read_text(encoding="utf-8")).get("status") in RUNNABLE_STATUSES
    ]


def main() -> int:
    subject_sha = os.environ.get("MGTEST_SHA", "").strip()
    run_id = os.environ.get("GITHUB_RUN_ID", "").strip()
    run_attempt = os.environ.get("GITHUB_RUN_ATTEMPT", "").strip()
    repository = os.environ.get("GITHUB_REPOSITORY", "").strip()
    image = os.environ.get("MGNARFTEST_PYTHON_IMAGE", "").strip()

    if len(subject_sha) != 40:
        die("MGTEST_SHA must be exact 40-hex SHA")
    if repository != REGISTRY_REPOSITORY:
        die("wrong repository context")
    if not run_id.isdigit():
        die("missing/invalid GITHUB_RUN_ID")
    if image != PINNED_IMAGE:
        die("container image does not match pinned immutable digest")

    paths = manifest_paths(sys.argv[1:])
    if not paths:
        die("no runnable manifests")

    out = ROOT / "evidence"
    out.mkdir(exist_ok=True)
    created = 0

    for manifest_path in paths:
        manifest = load_manifest(manifest_path)
        test_file = test_file_for(manifest)
        target = manifest.get("target") or {}
        test_id = manifest["test_id"]
        version = manifest["test_version"]

        receipt = {
            "schema_version": 1,
            "test": {
                "id": test_id,
                "version": version,
                "manifest_sha256": sha256_file(manifest_path),
                "test_sha256": sha256_file(test_file),
            },
            "mgtest": {
                "repository": repository,
                "commit": subject_sha,
            },
            "target": {
                "repository": target.get("repository"),
                "release": target.get("release"),
                "commit": target.get("commit"),
            },
            "execution": {
                "provider": "github-actions",
                "run_id": run_id,
                "run_attempt": run_attempt,
                "result": "PASS",
                "container_image": image,
                "isolation": {
                    "network": "none",
                    "rootfs": "read-only",
                    "capabilities": "drop-all",
                    "no_new_privileges": True,
                    "user": "65534:65534",
                },
            },
        }

        canonical = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
        receipt["receipt_sha256"] = hashlib.sha256(canonical).hexdigest()

        output = out / f"{test_id}-v{version}-{run_id}.json"
        output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"MGNARFTEST RECEIPT: PASS - {output.relative_to(ROOT)}")
        print(f"receipt_sha256={receipt['receipt_sha256']}")
        created += 1

    print(f"MGNARFTEST RECEIPT: PASS - {created} receipt(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
