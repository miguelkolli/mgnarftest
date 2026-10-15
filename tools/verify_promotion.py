#!/usr/bin/env python3
import hashlib
import io
import json
import os
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def die(message: str) -> None:
    print(f"MGNARFTEST PROMOTION: FAIL - {message}", file=sys.stderr)
    raise SystemExit(1)


def api_get(url: str, token: str):
    req = urllib.request.Request(url, headers={"Accept":"application/vnd.github+json","Authorization":f"Bearer {token}","X-GitHub-Api-Version":"2022-11-28","User-Agent":"mgnarftest-promotion-gate"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def download(url: str, token: str) -> bytes:
    req = urllib.request.Request(url, headers={"Accept":"application/vnd.github+json","Authorization":f"Bearer {token}","X-GitHub-Api-Version":"2022-11-28","User-Agent":"mgnarftest-promotion-gate"})
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


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    head_sha = os.environ.get("PROMOTION_HEAD_SHA", "").strip()
    if not token or repo != "miguelkolli/mgnarftest" or len(head_sha) != 40:
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
        if not run_id.isdigit():
            die(f"{path}: evidence.run_id must be a GitHub Actions run id")

        artifacts = api_get(f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100", token).get("artifacts", [])
        expected_name = f"mgnarftest-evidence-{run_id}"
        matches = [a for a in artifacts if a.get("name") == expected_name and not a.get("expired")]
        if len(matches) != 1:
            die(f"{path}: expected exactly one live artifact named {expected_name}")
        artifact = matches[0]
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
        if receipt.get("mgtest", {}).get("commit") != evidence.get("mgtest_commit"):
            die(f"{path}: tested subject commit mismatch")
        if receipt.get("target", {}).get("commit") != target.get("commit") or evidence.get("target_commit") != target.get("commit"):
            die(f"{path}: target commit mismatch")
        if receipt.get("test", {}).get("id") != manifest.get("test_id") or receipt.get("test", {}).get("version") != manifest.get("test_version"):
            die(f"{path}: receipt test identity/version mismatch")

        print(f"MGNARFTEST PROMOTION: PASS - {manifest['test_id']}/v{manifest['test_version']} subject={evidence['mgtest_commit']} promotion={head_sha} run={run_id}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
