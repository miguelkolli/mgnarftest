#!/usr/bin/env python3
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNABLE_STATUSES = {"PROPOSED", "REVIEW-A", "REVIEW-B", "STABLE"}
EXPECTED_TARGET_REPOSITORY = "miguelkolli/mgnarf"
DEFAULT_IMAGE = "python:3.12-slim"


def die(message: str) -> None:
    raise SystemExit(f"MGNARFTEST RUNNER: FAIL - {message}")


def load_manifests():
    manifests = []
    for path in sorted(ROOT.glob("tests/*/*/manifest.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:
            die(f"{path.relative_to(ROOT)}: invalid JSON: {exc}")
        if data.get("status") in RUNNABLE_STATUSES:
            manifests.append((path, data))
    if not manifests:
        die("no runnable manifests")
    return manifests


def entrypoint_for(path: Path, manifest: dict) -> list[str]:
    test_id = manifest.get("test_id")
    version = manifest.get("test_version")
    execution = manifest.get("execution") or {}

    if execution.get("network") is not False:
        die(f"{path.relative_to(ROOT)}: only network=false tests are supported")
    if execution.get("privileges") != "none":
        die(f"{path.relative_to(ROOT)}: only privileges=none tests are supported")
    if execution.get("external_dependencies") != []:
        die(f"{path.relative_to(ROOT)}: external dependencies are not supported by isolated runner")

    raw = execution.get("entrypoint")
    if not isinstance(raw, str) or not raw.strip():
        die(f"{path.relative_to(ROOT)}: missing execution.entrypoint")
    argv = shlex.split(raw)
    if len(argv) != 2 or argv[0] not in {"python", "python3"}:
        die(f"{path.relative_to(ROOT)}: entrypoint must be exactly 'python3 <test.py>'")

    expected = Path("tests") / str(test_id) / f"v{version}" / "test.py"
    if Path(argv[1]) != expected:
        die(f"{path.relative_to(ROOT)}: entrypoint must reference {expected.as_posix()}")
    if not (ROOT / expected).is_file():
        die(f"{path.relative_to(ROOT)}: entrypoint file missing")
    return ["python3", expected.as_posix()]


def main() -> int:
    workspace = Path(os.environ.get("GITHUB_WORKSPACE", "")).resolve()
    target_sha = os.environ.get("MGNARF_TARGET_SHA", "").strip()
    image = os.environ.get("MGNARFTEST_PYTHON_IMAGE", DEFAULT_IMAGE).strip()

    if not workspace.is_dir():
        die("GITHUB_WORKSPACE is missing")
    if len(target_sha) != 40:
        die("MGNARF_TARGET_SHA must be an exact 40-hex SHA")
    if not image:
        die("container image is empty")

    registry_mount = workspace / "mgnarftest"
    target_mount = workspace / "target-mgnarf" / "src"
    if not registry_mount.is_dir() or not target_mount.is_dir():
        die("registry or target source checkout is missing")

    count = 0
    for path, manifest in load_manifests():
        target = manifest.get("target") or {}
        if target.get("repository") != EXPECTED_TARGET_REPOSITORY:
            die(f"{path.relative_to(ROOT)}: unsupported target repository")
        if target.get("commit") != target_sha:
            die(f"{path.relative_to(ROOT)}: target commit does not match checked-out exact target")

        argv = entrypoint_for(path, manifest)
        test_name = f"{manifest['test_id']}/v{manifest['test_version']}"
        print(f"MGNARFTEST RUNNER: START - {test_name}", flush=True)

        command = [
            "docker", "run", "--rm",
            "--network", "none",
            "--read-only",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--user", "65534:65534",
            "--pids-limit", "128",
            "--memory", "256m",
            "--cpus", "1.0",
            "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=64m",
            "-e", "PYTHONPATH=/target-src",
            "-e", "PYTHONDONTWRITEBYTECODE=1",
            "-v", f"{registry_mount}:/mgnarftest:ro",
            "-v", f"{target_mount}:/target-src:ro",
            "-w", "/mgnarftest",
            image,
            *argv,
        ]
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            die(f"{test_name}: isolated execution returned {result.returncode}")
        print(f"MGNARFTEST RUNNER: PASS - {test_name}", flush=True)
        count += 1

    print(f"MGNARFTEST RUNNER: PASS - {count} runnable test(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
