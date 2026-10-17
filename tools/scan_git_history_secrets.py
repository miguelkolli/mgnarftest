#!/usr/bin/env python3
"""Fail closed on high-confidence credential material anywhere in Git history."""

from __future__ import annotations

import re
import subprocess
import sys

MAX_BLOB_BYTES = 5 * 1024 * 1024

PATTERNS = (
    ("openai_or_anthropic_api_key", re.compile(rb"\bsk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}\b")),
    ("github_classic_token", re.compile(rb"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("github_fine_grained_token", re.compile(rb"\bgithub_pat_[A-Za-z0-9_]{20,}\b")),
    ("google_api_key", re.compile(rb"\bAIza[0-9A-Za-z_-]{30,}\b")),
    ("aws_access_key", re.compile(rb"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("slack_token", re.compile(rb"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("private_key", re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
)


def git(*args: str, binary: bool = False) -> bytes | str:
    result = subprocess.run(
        ["git", *args],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout if binary else result.stdout.decode("utf-8", errors="strict")


def object_paths() -> dict[str, str]:
    paths: dict[str, str] = {}
    for line in git("rev-list", "--objects", "--all").splitlines():
        oid, _, path = line.partition(" ")
        if oid and oid not in paths:
            paths[oid] = path or "<no-path>"
    return paths


def main() -> int:
    findings: list[tuple[str, str, str]] = []
    scanned = 0

    for oid, path in object_paths().items():
        if git("cat-file", "-t", oid).strip() != "blob":
            continue
        size = int(git("cat-file", "-s", oid).strip())
        if size > MAX_BLOB_BYTES:
            continue
        content = git("cat-file", "blob", oid, binary=True)
        scanned += 1
        for label, pattern in PATTERNS:
            if pattern.search(content):
                findings.append((label, oid, path))

    if findings:
        print("HISTORY SECRET SCAN: FAIL", file=sys.stderr)
        for label, oid, path in findings:
            print(f"- {label}: blob={oid} path={path}", file=sys.stderr)
        print("Matched values are intentionally not printed.", file=sys.stderr)
        return 1

    print(f"HISTORY SECRET SCAN: PASS — scanned {scanned} unique Git blobs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
