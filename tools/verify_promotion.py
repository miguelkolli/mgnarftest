#!/usr/bin/env python3
import base64
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
EXPECTED_REPOSITORY = "miguelkolli/mgnarftest"


def die(message: str) -> None:
    print(f"MGNARFTEST PROMOTION: FAIL - {message}", file=sys.stderr)
    raise SystemExit(1)


def request(url: str, token: str, accept: str = "application/vnd.github+json"):
    req = urllib.request.Request(
        url,
        headers={
            "Accept": accept,
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "mgnarftest-promotion-gate",
        },
    )
    return urllib.request.urlopen(req, timeout=30)


def api_get(url: str, token: str):
    with request(url, token) as response:
        return json.load(response)


def download(url: str, token: str) -> bytes:
    with request(url, token) as response:
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


def subject_file_sha256(repo: str, subject_sha: str, path: str, token: str) -> str:
    quoted = urllib.parse.quote(path, safe="/")
    data = api_get(
        f"https://api.github.com/repos/{repo}/contents/{quoted}?ref={subject_sha}",
        token,
    )
    if data.get("type") != "file" or data.get("encoding") != "base64":
        die(f"subject file unavailable or unsupported: {path}@{subject_sha}")
    raw = base64.b64decode(data.get("content", ""), validate=False)
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    head_sha = os.environ.get("PROMOTION_HEAD_SHA", "").strip()
    if not token or repo != EXPECTED_REPOSITORY or len(head_sha) != 40:
        die("required GitHub context is missing or wrong repository")

    stable = []
    for path in sorted(ROOT.glob("tests/*/*/manifest.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("status") == "STABLE":
            stable.append((path, data))

    if not stable:
        print("MGNARFTEST PROMOTION: SKIP - no STABLE manifests")
        return 0

    for path, manifest in stable:
        review = manifest["review"]
        evidence = manifest["evidence"]
        target = manifest["target"]
        if review.get("accepted_commit") != head_sha:
            die(f"{path}: review.accepted_commit must equal current promotion head {head_sha}")

        run_id = str(evidence.get("run_id") or "").strip()
        subject_sha = str(evidence.get("mgtest_commit") or "").strip()
        if not run_id.isdigit():
            die(f"{path}: evidence.run_id must be a GitHub Actions run id")
        if len(subject_sha) != 40:
            die(f"{path}: evidence.mgtest_commit must be exact subject SHA")

        run = api_get(f"https://api.github.com/repos/{repo}/actions/runs/{run_id}", token)
        if run.get("status") != "completed" or run.get("conclusion") != "success":
            die(f"{path}: subject workflow run is not completed/success")
        if run.get("head_sha") != subject_sha:
            die(f"{path}: workflow head_sha does not match evidence.mgtest_commit")
        if (run.get("repository") or {}).get("full_name") != repo:
            die(f"{path}: workflow run repository mismatch")

        artifacts = api_get(
            f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100",
            token,
        ).get("artifacts", [])
        expected_name = f"mgnarftest-evidence-{run_id}"
        matches = [a for a in artifacts if a.get("name") == expected_name and not a.get("expired")]
        if len(matches) != 1:
            die(f"{path}: expected exactly one live artifact named {expected_name}")
        artifact = matches[0]
        if (artifact.get("workflow_run") or {}).get("head_sha") != subject_sha:
            die(f"{path}: artifact workflow head does not match subject commit")
        digest = str(artifact.get("digest") or "")
        if not digest.startswith("sha256:") or digest.split(":", 1)[1] != evidence.get("artifact_hash"):
            die(f"{path}: artifact digest mismatch")

        archive = download(artifact["archive_download_url"], token)
        with zipfile.ZipFile(io.BytesIO(archive)) as zf:
            names = [n for n in zf.namelist() if n.endswith(".json") and not n.endswith("tampered.json")]
            if len(names) != 1:
                die(f"{path}: evidence artifact must contain exactly one receipt JSON")
            receipt = json.loads(zf.read(names[0]).decode("utf-8"))

        receipt_hash = canonical_receipt_hash(receipt)
        if receipt_hash != evidence.get("receipt_sha256"):
            die(f"{path}: receipt hash mismatch")
        if receipt.get("execution", {}).get("result") != "PASS":
            die(f"{path}: receipt result is not PASS")
        if str(receipt.get("execution", {}).get("run_id")) != run_id:
            die(f"{path}: receipt run_id mismatch")
        if receipt.get("mgtest", {}).get("repository") != repo:
            die(f"{path}: receipt repository mismatch")
        if receipt.get("mgtest", {}).get("commit") != subject_sha:
            die(f"{path}: tested subject commit mismatch")
        if receipt.get("target", {}).get("commit") != target.get("commit") or evidence.get("target_commit") != target.get("commit"):
            die(f"{path}: target commit mismatch")
        if receipt.get("test", {}).get("id") != manifest.get("test_id") or receipt.get("test", {}).get("version") != manifest.get("test_version"):
            die(f"{path}: receipt test identity/version mismatch")

        test_id = manifest["test_id"]
        version = manifest["test_version"]
        base = f"tests/{test_id}/v{version}"
        if receipt.get("test", {}).get("manifest_sha256") != subject_file_sha256(repo, subject_sha, f"{base}/manifest.json", token):
            die(f"{path}: receipt manifest hash does not match immutable subject commit")
        if receipt.get("test", {}).get("test_sha256") != subject_file_sha256(repo, subject_sha, f"{base}/test.py", token):
            die(f"{path}: receipt test hash does not match immutable subject commit")

        print(
            f"MGNARFTEST PROMOTION: PASS - {test_id}/v{version} "
            f"subject={subject_sha} promotion={head_sha} run={run_id}"
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
