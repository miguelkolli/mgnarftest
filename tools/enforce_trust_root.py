#!/usr/bin/env python3
import json
import os
import sys

from tools.verify_stable_promotion_pr import (
    MANIFEST_RE,
    REGISTRY_REPOSITORY,
    changed_files,
    json_repo_file,
)

TRUST_ROOT_STATUS = "UNVERIFIED"
STABLE_PROMOTION_ENABLED = False


def die(message: str) -> None:
    print(f"MGNARFTEST TRUST ROOT: BLOCKED - {message}", file=sys.stderr)
    raise SystemExit(1)


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
    stable_paths = []
    for filename in changed_files(repo, number, token):
        if not MANIFEST_RE.fullmatch(filename):
            continue
        head = json_repo_file(repo, head_sha, filename, token)
        if head.get("status") == "STABLE":
            stable_paths.append(filename)

    if stable_paths and not STABLE_PROMOTION_ENABLED:
        die(
            f"STABLE promotion disabled while repository trust root is {TRUST_ROOT_STATUS}; "
            f"requested manifests: {stable_paths}"
        )

    if stable_paths:
        print(
            f"MGNARFTEST TRUST ROOT: PASS - STABLE promotion enabled; "
            f"status={TRUST_ROOT_STATUS}, manifests={stable_paths}"
        )
    else:
        print("MGNARFTEST TRUST ROOT: SKIP - no STABLE promotion requested")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
