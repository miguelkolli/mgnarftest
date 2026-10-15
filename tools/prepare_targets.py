#!/usr/bin/env python3
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNNABLE_STATUSES = {"PROPOSED", "REVIEW-A", "REVIEW-B", "STABLE"}
TARGET_REPOSITORY = "miguelkolli/mgnarf"
TARGET_URL = "https://github.com/miguelkolli/mgnarf.git"
HEX40 = re.compile(r"^[0-9a-f]{40}$")


def die(message: str) -> None:
    raise SystemExit(f"MGNARFTEST TARGET PREP: FAIL - {message}")


def load_runnable_manifests() -> list[tuple[Path, dict]]:
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


def collect_target_shas(manifests: list[tuple[Path, dict]]) -> list[str]:
    shas = set()
    for path, manifest in manifests:
        target = manifest.get("target") or {}
        repository = target.get("repository")
        commit = target.get("commit")
        if repository != TARGET_REPOSITORY:
            die(f"{path}: unsupported target repository {repository!r}")
        if not isinstance(commit, str) or not HEX40.fullmatch(commit):
            die(f"{path}: target.commit must be exact lowercase 40-hex SHA")
        shas.add(commit)
    return sorted(shas)


def run(command: list[str], *, cwd: Path | None = None, capture: bool = False) -> str:
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            check=True,
            text=True,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None,
            timeout=120,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        die(f"command failed: {command[0]} {command[1] if len(command) > 1 else ''}: {type(exc).__name__}")
    return (result.stdout or "").strip()


def prepare_target(targets_root: Path, sha: str) -> None:
    destination = targets_root / sha
    if destination.exists():
        die(f"target destination already exists: {destination}")
    destination.mkdir(parents=True)

    run(["git", "init", "--quiet"], cwd=destination)
    run(["git", "remote", "add", "origin", TARGET_URL], cwd=destination)
    run(
        [
            "git",
            "-c",
            "protocol.version=2",
            "fetch",
            "--no-tags",
            "--depth=1",
            "origin",
            sha,
        ],
        cwd=destination,
    )
    run(["git", "-c", "advice.detachedHead=false", "checkout", "--detach", "FETCH_HEAD"], cwd=destination)
    actual = run(["git", "rev-parse", "HEAD"], cwd=destination, capture=True)
    if actual != sha:
        die(f"exact target verification failed: expected {sha}, got {actual}")
    if not (destination / "src").is_dir():
        die(f"exact target {sha} has no src directory")
    print(f"MGNARFTEST TARGET PREP: PASS - {TARGET_REPOSITORY}@{sha}")


def main() -> int:
    workspace_raw = os.environ.get("GITHUB_WORKSPACE", "").strip()
    if not workspace_raw:
        die("GITHUB_WORKSPACE is missing")
    workspace = Path(workspace_raw).resolve()
    if not workspace.is_dir():
        die("GITHUB_WORKSPACE is not a directory")

    targets_root = workspace / "targets"
    if targets_root.exists():
        die("targets directory already exists; refusing to reuse target state")
    targets_root.mkdir()

    shas = collect_target_shas(load_runnable_manifests())
    for sha in shas:
        prepare_target(targets_root, sha)

    print(f"MGNARFTEST TARGET PREP: PASS - {len(shas)} exact target(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
