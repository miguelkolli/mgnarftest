#!/usr/bin/env python3
import json
import os
import sys

from tools.verify_stable_promotion_pr import (
    MANIFEST_RE,
    REGISTRY_REPOSITORY,
    api_get,
    changed_files,
    json_repo_file,
)

TRUST_ROOT_STATUS = "UNPROTECTED"
STABLE_PROMOTION_ENABLED = False

TRUST_ROOT_RULESET_NAME = "MGnarfTest main protection"
TRUST_ROOT_BRANCH = "main"
EXPECTED_CHECK_INTEGRATION_ID = 15368  # GitHub Actions
REQUIRED_STATUS_CHECKS = frozenset(
    {
        "validate",
        "ai-runner-selftest",
        "history-secret-scan",
        "trusted-promotion-gate",
    }
)


class TrustRootConfigurationError(RuntimeError):
    pass


def die(message: str) -> None:
    print(f"MGNARFTEST TRUST ROOT: BLOCKED - {message}", file=sys.stderr)
    raise SystemExit(1)


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise TrustRootConfigurationError(message)


def _rule(detail: dict, rule_type: str) -> dict:
    matches = [rule for rule in detail.get("rules", []) if rule.get("type") == rule_type]
    _require(len(matches) == 1, f"ruleset must contain exactly one {rule_type} rule")
    return matches[0]


def verify_repository_trust_root(repo: str, token: str) -> dict:
    branch = api_get(f"https://api.github.com/repos/{repo}/branches/{TRUST_ROOT_BRANCH}", token)
    _require(branch.get("protected") is True, "main branch is not protected")

    summaries = api_get(f"https://api.github.com/repos/{repo}/rulesets?per_page=100", token)
    _require(isinstance(summaries, list), "invalid repository ruleset list")
    candidates = [
        row
        for row in summaries
        if row.get("name") == TRUST_ROOT_RULESET_NAME
        and row.get("target") == "branch"
        and row.get("source_type") == "Repository"
        and row.get("source") == repo
        and row.get("enforcement") == "active"
    ]
    _require(
        len(candidates) == 1,
        f"expected exactly one active repository ruleset named {TRUST_ROOT_RULESET_NAME!r}",
    )

    ruleset_id = candidates[0].get("id")
    _require(isinstance(ruleset_id, int), "ruleset id unavailable")
    detail = api_get(f"https://api.github.com/repos/{repo}/rulesets/{ruleset_id}", token)

    _require(detail.get("enforcement") == "active", "ruleset enforcement is not active")
    conditions = (detail.get("conditions") or {}).get("ref_name") or {}
    includes = set(conditions.get("include") or [])
    excludes = list(conditions.get("exclude") or [])
    _require("~DEFAULT_BRANCH" in includes, "ruleset does not target the default branch")
    _require(not excludes, "ruleset contains branch exclusions")
    _require(not (detail.get("bypass_actors") or []), "ruleset has bypass actors")

    _rule(detail, "deletion")
    _rule(detail, "non_fast_forward")

    pull_request = _rule(detail, "pull_request")
    pull_parameters = pull_request.get("parameters") or {}
    _require(
        pull_parameters.get("required_review_thread_resolution") is True,
        "pull-request rule does not require conversation resolution",
    )

    status_rule = _rule(detail, "required_status_checks")
    status_parameters = status_rule.get("parameters") or {}
    _require(
        status_parameters.get("strict_required_status_checks_policy") is True,
        "required status checks are not strict/up-to-date",
    )
    _require(
        status_parameters.get("do_not_enforce_on_create") is False,
        "required status checks are bypassed on branch creation",
    )

    configured = {}
    for check in status_parameters.get("required_status_checks") or []:
        context = check.get("context")
        if isinstance(context, str):
            configured[context] = check.get("integration_id")

    missing = sorted(REQUIRED_STATUS_CHECKS - set(configured))
    _require(not missing, f"required trust-root checks missing: {missing}")
    wrong_source = sorted(
        context
        for context in REQUIRED_STATUS_CHECKS
        if configured.get(context) != EXPECTED_CHECK_INTEGRATION_ID
    )
    _require(
        not wrong_source,
        f"required trust-root checks are not bound to GitHub Actions integration: {wrong_source}",
    )

    return {
        "status": "PROTECTED",
        "ruleset_id": ruleset_id,
        "ruleset_name": TRUST_ROOT_RULESET_NAME,
        "branch": TRUST_ROOT_BRANCH,
        "required_status_checks": sorted(REQUIRED_STATUS_CHECKS),
        "bypass_actors": 0,
    }


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

    if not stable_paths:
        print("MGNARFTEST TRUST ROOT: SKIP - no STABLE promotion requested")
        return 0

    try:
        live = verify_repository_trust_root(repo, token)
    except Exception as exc:
        die(f"repository trust-root verification failed: {type(exc).__name__}: {exc}")

    if not STABLE_PROMOTION_ENABLED or TRUST_ROOT_STATUS not in {"PROTECTED", "ENFORCED"}:
        die(
            f"STABLE promotion disabled while repository policy is {TRUST_ROOT_STATUS}; "
            f"live_ruleset={live['status']}, requested manifests: {stable_paths}"
        )

    print(
        f"MGNARFTEST TRUST ROOT: PASS - STABLE promotion enabled; "
        f"status={TRUST_ROOT_STATUS}, live_ruleset={live['status']}, "
        f"ruleset_id={live['ruleset_id']}, manifests={stable_paths}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
