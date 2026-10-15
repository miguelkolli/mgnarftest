#!/usr/bin/env python3
import base64
import hashlib
import io
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile

REGISTRY_REPOSITORY = "miguelkolli/mgnarftest"
REGISTRY_WORKFLOW_PATH = ".github/workflows/registry-validate.yml"
PINNED_IMAGE = "python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1"
MANIFEST_RE = re.compile(r"^tests/(MGTEST-[A-Z0-9]+-[A-Z0-9-]+-[0-9]{3})/v([1-9][0-9]*)/manifest\.json$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


def die(message: str) -> None:
    print(f"MGNARFTEST TRUSTED PROMOTION: FAIL - {message}", file=sys.stderr)
    raise SystemExit(1)


def request(url: str, token: str, *, accept: str = "application/vnd.github+json") -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": accept,
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "mgnarftest-trusted-promotion",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return response.read()


def api_get(url: str, token: str):
    return json.loads(request(url, token).decode("utf-8"))


def api_get_optional(url: str, token: str):
    try:
        return api_get(url, token)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise


def repo_file(repo: str, sha: str, path: str, token: str) -> bytes:
    encoded = urllib.parse.quote(path, safe="/")
    payload = api_get_optional(f"https://api.github.com/repos/{repo}/contents/{encoded}?ref={sha}", token)
    if payload is None or payload.get("type") != "file":
        die(f"missing repository file at {sha}: {path}")
    content = payload.get("content")
    if not isinstance(content, str):
        die(f"repository file has no inline content: {path}")
    return base64.b64decode(content.replace("\n", ""), validate=True)


def json_repo_file(repo: str, sha: str, path: str, token: str) -> dict:
    try:
        value = json.loads(repo_file(repo, sha, path, token).decode("utf-8"))
    except Exception as exc:
        die(f"invalid JSON at {sha}:{path}: {exc}")
    if not isinstance(value, dict):
        die(f"JSON root is not object at {sha}:{path}")
    return value


def changed_files(repo: str, number: int, token: str) -> list[str]:
    names = []
    page = 1
    while True:
        rows = api_get(f"https://api.github.com/repos/{repo}/pulls/{number}/files?per_page=100&page={page}", token)
        if not isinstance(rows, list):
            die("invalid pull-request file list")
        names.extend(str(row.get("filename")) for row in rows if row.get("filename"))
        if len(rows) < 100:
            break
        page += 1
    return names


def canonical_receipt_hash(receipt: dict) -> str:
    body = dict(receipt)
    claimed = body.pop("receipt_sha256", None)
    if not isinstance(claimed, str) or not HEX64.fullmatch(claimed):
        die("receipt missing valid receipt_sha256")
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
    if hashlib.sha256(canonical).hexdigest() != claimed:
        die("receipt_sha256 mismatch")
    return claimed


def immutable_manifest(data: dict) -> dict:
    copy = dict(data)
    copy.pop("status", None)
    copy.pop("review", None)
    copy.pop("evidence", None)
    return copy


def validate_stable_shape(path: str, head: dict, base: dict, subject: dict, pr_number: int) -> None:
    if base.get("status") == "STABLE":
        die(f"{path}: already STABLE on base; promotion PR must introduce the transition")
    if head.get("status") != "STABLE":
        die(f"{path}: promotion manifest must be STABLE")
    if immutable_manifest(head) != immutable_manifest(base):
        die(f"{path}: STABLE promotion may not change test semantics")
    if immutable_manifest(head) != immutable_manifest(subject):
        die(f"{path}: tested subject semantics differ from promotion semantics")

    review = head.get("review") or {}
    evidence = head.get("evidence") or {}
    if review.get("author") != (base.get("review") or {}).get("author"):
        die(f"{path}: review.author may not change during promotion")
    if review.get("promotion_pr") != pr_number:
        die(f"{path}: review.promotion_pr must equal the current GitHub PR number")
    if evidence.get("result") != "PASS":
        die(f"{path}: STABLE requires PASS evidence")
    if not str(evidence.get("run_id") or "").isdigit():
        die(f"{path}: invalid evidence.run_id")
    if not isinstance(evidence.get("artifact_hash"), str) or not HEX64.fullmatch(evidence["artifact_hash"]):
        die(f"{path}: invalid evidence.artifact_hash")
    if not isinstance(evidence.get("receipt_sha256"), str) or not HEX64.fullmatch(evidence["receipt_sha256"]):
        die(f"{path}: invalid evidence.receipt_sha256")
    if not isinstance(evidence.get("mgtest_commit"), str) or not HEX40.fullmatch(evidence["mgtest_commit"]):
        die(f"{path}: invalid evidence.mgtest_commit")
    if evidence.get("target_commit") != (head.get("target") or {}).get("commit"):
        die(f"{path}: evidence.target_commit mismatch")


def latest_approvals(repo: str, number: int, head_sha: str, excluded: set[str], token: str) -> set[str]:
    reviews = api_get(f"https://api.github.com/repos/{repo}/pulls/{number}/reviews?per_page=100", token)
    latest = {}
    for review in reviews:
        user = (review.get("user") or {}).get("login")
        if not user:
            continue
        submitted = review.get("submitted_at") or ""
        previous = latest.get(user)
        if previous is None or submitted >= (previous.get("submitted_at") or ""):
            latest[user] = review
    return {
        user for user, review in latest.items()
        if user not in excluded
        and review.get("state") == "APPROVED"
        and review.get("commit_id") == head_sha
    }


def verify_evidence(repo: str, base_sha: str, path: str, manifest: dict, token: str) -> None:
    evidence = manifest["evidence"]
    target = manifest["target"]
    test_id = manifest["test_id"]
    version = manifest["test_version"]
    subject_sha = evidence["mgtest_commit"]
    run_id = str(evidence["run_id"])

    compare = api_get(f"https://api.github.com/repos/{repo}/compare/{subject_sha}...{base_sha}", token)
    if (compare.get("merge_base_commit") or {}).get("sha") != subject_sha:
        die(f"{path}: tested subject is not an ancestor of promotion base")

    run = api_get(f"https://api.github.com/repos/{repo}/actions/runs/{run_id}", token)
    if run.get("status") != "completed" or run.get("conclusion") != "success":
        die(f"{path}: evidence run is not completed/success")
    if run.get("event") != "push" or run.get("head_branch") != "main":
        die(f"{path}: STABLE evidence must come from a main push run")
    if run.get("head_sha") != subject_sha or run.get("path") != REGISTRY_WORKFLOW_PATH:
        die(f"{path}: evidence run subject/workflow mismatch")

    artifacts = api_get(f"https://api.github.com/repos/{repo}/actions/runs/{run_id}/artifacts?per_page=100", token).get("artifacts", [])
    expected_name = f"mgnarftest-evidence-{run_id}"
    matches = [a for a in artifacts if a.get("name") == expected_name and not a.get("expired")]
    if len(matches) != 1:
        die(f"{path}: expected exactly one live evidence artifact")
    artifact = matches[0]
    workflow_run = artifact.get("workflow_run") or {}
    if str(workflow_run.get("id")) != run_id or workflow_run.get("head_sha") != subject_sha:
        die(f"{path}: artifact workflow binding mismatch")
    digest = str(artifact.get("digest") or "")
    if digest != f"sha256:{evidence['artifact_hash']}":
        die(f"{path}: artifact digest mismatch")

    archive = request(artifact["archive_download_url"], token, accept="application/octet-stream")
    with zipfile.ZipFile(io.BytesIO(archive)) as zf:
        receipts = []
        for name in zf.namelist():
            if not name.endswith(".json"):
                continue
            candidate = json.loads(zf.read(name).decode("utf-8"))
            test = candidate.get("test") or {}
            if test.get("id") == test_id and test.get("version") == version:
                receipts.append(candidate)
        if len(receipts) != 1:
            die(f"{path}: artifact must contain exactly one matching receipt")
        receipt = receipts[0]

    if canonical_receipt_hash(receipt) != evidence["receipt_sha256"]:
        die(f"{path}: receipt hash mismatch")
    execution = receipt.get("execution") or {}
    if execution.get("result") != "PASS" or str(execution.get("run_id")) != run_id:
        die(f"{path}: receipt execution mismatch")
    if execution.get("container_image") != PINNED_IMAGE:
        die(f"{path}: receipt runtime image mismatch")
    if (receipt.get("mgtest") or {}).get("repository") != repo or (receipt.get("mgtest") or {}).get("commit") != subject_sha:
        die(f"{path}: receipt subject mismatch")
    receipt_target = receipt.get("target") or {}
    for key in ("repository", "release", "commit"):
        if receipt_target.get(key) != target.get(key):
            die(f"{path}: receipt target.{key} mismatch")

    test_path = f"tests/{test_id}/v{version}/test.py"
    subject_manifest_bytes = repo_file(repo, subject_sha, path, token)
    base_test_bytes = repo_file(repo, base_sha, test_path, token)
    subject_test_bytes = repo_file(repo, subject_sha, test_path, token)
    receipt_test = receipt.get("test") or {}
    if hashlib.sha256(subject_manifest_bytes).hexdigest() != receipt_test.get("manifest_sha256"):
        die(f"{path}: subject manifest hash mismatch")
    if hashlib.sha256(subject_test_bytes).hexdigest() != receipt_test.get("test_sha256"):
        die(f"{path}: subject test hash mismatch")
    if hashlib.sha256(base_test_bytes).hexdigest() != hashlib.sha256(subject_test_bytes).hexdigest():
        die(f"{path}: test.py changed after the evidenced subject run")


def main() -> int:
    token = os.environ.get("GITHUB_TOKEN", "").strip()
    event_path = os.environ.get("GITHUB_EVENT_PATH", "").strip()
    repo = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if not token or not event_path or repo != REGISTRY_REPOSITORY:
        die("required trusted GitHub context missing")

    with open(event_path, encoding="utf-8") as event_file:
        event = json.load(event_file)
    pr = event.get("pull_request")
    if not isinstance(pr, dict):
        die("event has no pull_request")
    number = int(pr["number"])
    head_sha = pr["head"]["sha"]
    base_sha = pr["base"]["sha"]
    pr_author = pr["user"]["login"]

    files = changed_files(repo, number, token)
    changed_manifests = []
    for filename in files:
        if not MANIFEST_RE.fullmatch(filename):
            continue
        head = json_repo_file(repo, head_sha, filename, token)
        base = json_repo_file(repo, base_sha, filename, token)
        if base.get("status") == "STABLE":
            die(
                f"{filename}: existing STABLE manifest is immutable; "
                "use a dedicated trusted retirement transition"
            )
        if head.get("status") == "STABLE":
            changed_manifests.append((filename, head, base))

    if not changed_manifests:
        print("MGNARFTEST TRUSTED PROMOTION: SKIP - no STABLE transition requested")
        return 0

    allowed = {"REGISTRY.md"}
    allowed.update(path for path, _, _ in changed_manifests)
    unexpected = sorted(set(files) - allowed)
    if unexpected:
        die(f"STABLE promotion PR contains non-promotion changes: {unexpected}")

    authors = set()
    promoted = []
    for path, head, base in changed_manifests:
        evidence = head.get("evidence") or {}
        subject_sha = evidence.get("mgtest_commit")
        if not isinstance(subject_sha, str) or not HEX40.fullmatch(subject_sha):
            die(f"{path}: invalid evidenced subject commit")
        subject = json_repo_file(repo, subject_sha, path, token)
        validate_stable_shape(path, head, base, subject, number)
        verify_evidence(repo, base_sha, path, head, token)
        author = (head.get("review") or {}).get("author")
        if not isinstance(author, str) or not author.strip():
            die(f"{path}: missing test author")
        authors.add(author)
        promoted.append((path, head))

    approvals = latest_approvals(repo, number, head_sha, authors | {pr_author}, token)
    if len(approvals) < 2:
        die(f"exact promotion head requires 2 authenticated approvals excluding authors; found {sorted(approvals)}")

    for path, manifest in promoted:
        review = manifest["review"]
        a = review.get("reviewer_a")
        b = review.get("reviewer_b")
        if not isinstance(a, str) or not isinstance(b, str) or a == b:
            die(f"{path}: reviewer_a and reviewer_b must be distinct identities")
        if a not in approvals or b not in approvals:
            die(f"{path}: manifest reviewers are not authenticated exact-head approvers")

    print(
        f"MGNARFTEST TRUSTED PROMOTION: PASS - {len(promoted)} manifest(s), "
        f"exact_head={head_sha}, promotion_pr={number}, approvals={sorted(approvals)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
