#!/usr/bin/env python3
import json
import os
import re
import shlex
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNABLE_STATUSES = {"PROPOSED", "REVIEW-A", "REVIEW-B", "STABLE"}
EXPECTED_TARGET_REPOSITORY = "miguelkolli/mgnarf"
PINNED_IMAGE = "python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1"
MAX_TIMEOUT_SECONDS = 300
HEX40 = re.compile(r"^[0-9a-f]{40}$")


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


def result_contract(path: Path, manifest: dict) -> str:
    expected = manifest.get("expected") or {}
    allowed = expected.get("allowed_results")
    if not isinstance(allowed, list) or "PASS" not in allowed:
        die(f"{path.relative_to(ROOT)}: runnable test must explicitly allow PASS before execution")
    return "PASS"


def execution_contract(path: Path, manifest: dict) -> tuple[list[str], int]:
    test_id = manifest.get("test_id")
    version = manifest.get("test_version")
    execution = manifest.get("execution") or {}

    if execution.get("network") is not False:
        die(f"{path.relative_to(ROOT)}: only network=false tests are supported")
    if execution.get("privileges") != "none":
        die(f"{path.relative_to(ROOT)}: only privileges=none tests are supported")
    if execution.get("external_dependencies") != []:
        die(f"{path.relative_to(ROOT)}: external dependencies are not supported by isolated runner")

    timeout_seconds = execution.get("timeout_seconds")
    if (
        not isinstance(timeout_seconds, int)
        or isinstance(timeout_seconds, bool)
        or timeout_seconds < 1
        or timeout_seconds > MAX_TIMEOUT_SECONDS
    ):
        die(f"{path.relative_to(ROOT)}: timeout_seconds must be integer 1..{MAX_TIMEOUT_SECONDS}")

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
    return ["python3", expected.as_posix()], timeout_seconds


def target_source_for(workspace: Path, path: Path, manifest: dict) -> Path:
    target = manifest.get("target") or {}
    repository = target.get("repository")
    commit = target.get("commit")
    if repository != EXPECTED_TARGET_REPOSITORY:
        die(f"{path.relative_to(ROOT)}: unsupported target repository")
    if not isinstance(commit, str) or not HEX40.fullmatch(commit):
        die(f"{path.relative_to(ROOT)}: target commit must be exact lowercase 40-hex SHA")
    target_source = workspace / "targets" / commit / "src"
    if not target_source.is_dir():
        die(f"{path.relative_to(ROOT)}: prepared exact target source missing for {commit}")
    return target_source


def run_container(command: list[str], container_name: str, timeout_seconds: int) -> None:
    try:
        result = subprocess.run(command, check=False, timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        subprocess.run(
            ["docker", "rm", "-f", container_name],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=15,
        )
        die(f"container {container_name} exceeded timeout_seconds={timeout_seconds}")
    if result.returncode != 0:
        die(f"container {container_name} returned {result.returncode}")


def main() -> int:
    workspace = Path(os.environ.get("GITHUB_WORKSPACE", "")).resolve()
    image = os.environ.get("MGNARFTEST_PYTHON_IMAGE", "").strip()
    run_id = os.environ.get("GITHUB_RUN_ID", "local").strip() or "local"

    if not workspace.is_dir():
        die("GITHUB_WORKSPACE is missing")
    if image != PINNED_IMAGE:
        die("container image does not match pinned immutable digest")

    registry_mount = workspace / "mgnarftest"
    if not registry_mount.is_dir():
        die("registry checkout is missing")

    count = 0
    for path, manifest in load_manifests():
        target_mount = target_source_for(workspace, path, manifest)
        target_sha = (manifest.get("target") or {})["commit"]
        result_contract(path, manifest)
        argv, timeout_seconds = execution_contract(path, manifest)
        test_name = f"{manifest['test_id']}/v{manifest['test_version']}"
        safe_id = manifest["test_id"].lower().replace("_", "-")
        container_name = f"mgnarftest-{safe_id}-v{manifest['test_version']}-{run_id}"[:120]
        print(
            f"MGNARFTEST RUNNER: START - {test_name} target={target_sha} timeout={timeout_seconds}s",
            flush=True,
        )

        command = [
            "docker", "run", "--rm",
            "--name", container_name,
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
        run_container(command, container_name, timeout_seconds)
        print(f"MGNARFTEST RUNNER: PASS - {test_name}", flush=True)
        count += 1

    print(f"MGNARFTEST RUNNER: PASS - {count} runnable test(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
