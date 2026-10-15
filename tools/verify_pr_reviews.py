#!/usr/bin/env python3
import json
import os
import sys
import urllib.request


def die(message: str) -> None:
    print(f"MGNARFTEST REVIEW GATE: FAIL - {message}", file=sys.stderr)
    raise SystemExit(1)


def api_get(url: str, token: str):
    req = urllib.request.Request(url, headers={"Accept":"application/vnd.github+json","Authorization":f"Bearer {token}","X-GitHub-Api-Version":"2022-11-28","User-Agent":"mgnarftest-review-gate"})
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def main() -> int:
    event_path = os.environ.get("GITHUB_EVENT_PATH")
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not event_path or not token or not repo:
        die("required GitHub Actions context is missing")

    event = json.load(open(event_path, encoding="utf-8"))
    pr = event.get("pull_request")
    if not pr:
        print("MGNARFTEST REVIEW GATE: SKIP - event has no pull_request")
        return 0

    number = pr["number"]
    author = pr["user"]["login"]
    head_sha = pr["head"]["sha"]
    reviews = api_get(f"https://api.github.com/repos/{repo}/pulls/{number}/reviews?per_page=100", token)

    latest = {}
    for review in reviews:
        user = (review.get("user") or {}).get("login")
        if not user:
            continue
        submitted = review.get("submitted_at") or ""
        prev = latest.get(user)
        if prev is None or submitted >= (prev.get("submitted_at") or ""):
            latest[user] = review

    approved = []
    for user, review in latest.items():
        if user == author or review.get("state") != "APPROVED" or review.get("commit_id") != head_sha:
            continue
        approved.append(user)

    approved = sorted(set(approved))
    if len(approved) < 2:
        die(f"exact head {head_sha} requires 2 distinct authenticated approvals excluding author {author}; found {len(approved)}: {approved}")

    print(f"MGNARFTEST REVIEW GATE: PASS - exact head {head_sha} approved by {approved}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
