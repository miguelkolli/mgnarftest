#!/usr/bin/env python3
import hashlib
import io
import json
import os
import sys
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_REPOSITORY = "miguelkolli/mgnarftest"
REGISTRY_WORKFLOW_PATH = ".github/workflows/registry-validate.yml"


def die(message: str) -> None:
    print(f"MGNARFTEST PROMOTION: FAIL - {message}", file=sys.stderr)
    raise SystemExit(1)


def api_get(url: str, token: str):
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "mgnarftest-promotion-gate",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def api_bytes(url: str, token: str, accept: str = "application/vnd.github+json") -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": accept,
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "mgnarftest-promotion-gate",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()


def canonical_receipt_hash(receipt: dict) -> str:
    body = dict(receipt)
    claimed = body.pop("receipt_sha256", None)
    if not claimed:
        die("receipt missing receipt_sha256")
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    actual = hashlib.sha256(canonical).hexdigest()
    if actual != claimed:
        die("receipt_sha256 mismatch")
    return claimed


def github_file_bytes(repo: str, sha: str, path: str, token: str) -> bytes:
    encoded = urllib.parse.quote(path, safe="/")
    url = f"https://api.github.com/repos/{repo}/contents/{encoded}?ref={sha}"
    payload = api_get(url, token)
    download_url = payload.get("download_url")
    if not download_url:
        die(f"subject file unavailable: {path}")
    return api_bytes(download_url, token, accept="application/octet-stream")


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    head_sha = os.environ.get("PROMOTION_HEAD_SHA", "").strip()
    if not token or repo != REGISTRY_REPOSITORY or len(head_sha) != 40:
        die("required GitHub context is missing or wrong repository")

    stable = []
    for path in sorted(ROOT.glob("tests/*/*/manifest.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("status") == "STABLE":
            stable.append((path, data))

    if not stable:
        print("MGNARFTEST PROMOTION: SKIP - no STABLE manifests")
        return 0

    artifact_cache = {}
    run_cache = {}
    archive_cache = {}

    for path, manifest in stable:
        review = manifest["review"]
        evidence = manifest["evidence"]
        target = manifest["target"]
        test_id = manifest["test_id"]
        version = manifest["test_version"]

        if review.get("accepted_commit") != head_sha:
            die(f"{path}: review.accepted_commit must equal current promotion head {head_sha}")

        run_id = str(evidence.get("run_id") or "").strip()
        subject_sha = str(evidence.get("mgtest_commit") or "").strip()
        if not run_id.isdigit():
            die(f"{path}: evidence.run_id must be a GitHub Actions run id")
        if len(subject_sha) != 40:
            die(f"{path}: evidence.mgtest_commit must be an exact subject SHA")

        if run_id not in run_cache:
            run_cache[run_id] = api_get(
                f"https://api.github.com/repos/{repo}/actions/runs/{run_id}",
                token,
            )
        run = run_cache[run_id]
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            die(f"{path}: subject workflow run is not completed/success")
        if run.get("head_sha") != subject_sha:
            die(f"{path}: workflow head_sha does not match tested subject commit")
        if run.get("path") != REGISTRY_WORKFLOW_PATH:
            die(f"{path}: evidence came from unexpected workflow path")

        if run_id not in artifact_cache:
            artifacts = api_get(
                f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100",
                token,
            ).get("artifacts", [])
            artifact_cache[run_id] = artifacts
        artifacts = artifact_cache[run_id]
        expected_name = f"mgnarftest-evidence-{run_id}"
        matches = [a for a in artifacts if a.get("name") == expected_name and not a.get("expired")]
        if len(matches) != 1:
            die(f"{path}: expected exactly one live artifact named {expected_name}")
        artifact = matches[0]

        workflow_run = artifact.get("workflow_run") or {}
        if str(workflow_run.get("id")) != run_id or workflow_run.get("head_sha") != subject_sha:
            die(f"{path}: artifact workflow binding mismatch")

        digest = str(artifact.get("digest") or "")
        if not digest.startswith("sha256:") or digest.split(":", 1)[1] != evidence.get("artifact_hash"):
            die(f"{path}: artifact digest mismatch")

        artifact_id = str(artifact.get("id"))
        if artifact_id not in archive_cache:
            archive_cache[artifact_id] = api_bytes(artifact["archive_download_url"], token)
        archive = archive_cache[artifact_id]

        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            receipts = []
            for name in zf.namelist():
                if not name.endswith(".json") or name.endswith("tampered.json"):
                    continue
                try:
                    candidate = json.loads(zf.read(name).decode("utf-8"))
                except Exception as exc:
                    die(f"{path}: invalid receipt JSON in artifact: {exc}")
                test = candidate.get("test") or {}
                if test.get("id") == test_id and test.get("version") == version:
                    receipts.append(candidate)
            if len(receipts) != 1:
                die(f"{path}: artifact must contain exactly one matching receipt for {test_id}/v{version}")
            receipt = receipts[0]

        receipt_hash = canonical_receipt_hash(receipt)
        if receipt_hash != evidence.get("receipt_sha256"):
            die(f"{path}: receipt hash mismatch")
        execution = receipt.get("execution") or {}
        if execution.get("result") != "PASS":
            die(f"{path}: receipt result is not PASS")
        if str(execution.get("run_id")) != run_id:
            die(f"{path}: receipt run_id mismatch")
        isolation = execution.get("isolation") or {}
        if isolation != {
            "network": "none",
            "rootfs": "read-only",
            "capabilities": "drop-all",
            "no_new_privileges": True,
            "user": "65534:65534",
        }:
            die(f"{path}: receipt isolation contract mismatch")

        mgtest = receipt.get("mgtest") or {}
        if mgtest.get("repository") != repo or mgtest.get("commit") != subject_sha:
            die(f"{path}: tested subject repository/commit mismatch")

        receipt_target = receipt.get("target") or {}
        for key in ("repository", "release", "commit"):
            if receipt_target.get(key) != target.get(key):
                die(f"{path}: receipt target.{key} mismatch")
        if evidence.get("target_commit") != target.get("commit"):
            die(f"{path}: evidence target commit mismatch")

        receipt_test = receipt.get("test") or {}
        manifest_rel = f"tests/{test_id}/v{version}/manifest.json"
        test_rel = f"tests/{test_id}/v{version}/test.py"
        subject_manifest = github_file_bytes(repo, subject_sha, manifest_rel, token)
        subject_test = github_file_bytes(repo, subject_sha, test_rel, token)
        if hashlib.sha256(subject_manifest).hexdigest() != receipt_test.get("manifest_sha256"):
            die(f"{path}: subject manifest hash does not match receipt")
        if hashlib.sha256(subject_test).hexdigest() != receipt_test.get("test_sha256"):
            die(f"{path}: subject test hash does not match receipt")

        print(
            f"MGNARFTEST PROMOTION: PASS - {test_id}/v{version} "
            f"subject={subject_sha} promotion={head_sha} run={run_id}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
