#!/usr/bin/env python3
import copy
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest import mock

from tools import verify_stable_promotion_pr as gate


class TrustedPromotionVerifierTests(unittest.TestCase):
    PR_NUMBER = 7
    HEAD_SHA = "h" * 40
    BASE_SHA = "b" * 40
    SUBJECT_SHA = "c" * 40
    TARGET_SHA = "d" * 40
    MANIFEST_PATH = "tests/MGTEST-NARF-ORDER-001/v1/manifest.json"

    def base_manifest(self):
        return {
            "schema_version": 1,
            "test_id": "MGTEST-NARF-ORDER-001",
            "test_version": 1,
            "status": "PROPOSED",
            "target": {
                "project": "MGnarf",
                "repository": "miguelkolli/mgnarf",
                "release": "v1.70",
                "commit": self.TARGET_SHA,
            },
            "purpose": "Exercise a frozen external security invariant.",
            "expected": {
                "allowed_results": ["PASS", "FAIL", "BLOCKED", "UNVERIFIED"],
                "safe_condition": "The protected boundary must reject the frozen attack condition.",
            },
            "execution": {
                "entrypoint": "python3 tests/MGTEST-NARF-ORDER-001/v1/test.py",
                "network": False,
                "privileges": "none",
                "external_dependencies": [],
                "timeout_seconds": 30,
            },
            "limits": ["This fixture only exercises promotion-gate policy semantics."],
            "review": {
                "author": "miguelkolli",
                "reviewer_a": None,
                "reviewer_b": None,
                "promotion_pr": None,
            },
            "evidence": {
                "result": "UNVERIFIED",
                "run_id": None,
                "artifact_hash": None,
                "receipt_sha256": None,
                "mgtest_commit": None,
                "target_commit": None,
            },
        }

    def stable_manifest(self, promotion_pr=None):
        data = copy.deepcopy(self.base_manifest())
        data["status"] = "STABLE"
        data["review"] = {
            "author": "miguelkolli",
            "reviewer_a": "reviewer-a",
            "reviewer_b": "reviewer-b",
            "promotion_pr": self.PR_NUMBER if promotion_pr is None else promotion_pr,
        }
        data["evidence"] = {
            "result": "PASS",
            "run_id": "123",
            "artifact_hash": "a" * 64,
            "receipt_sha256": "e" * 64,
            "mgtest_commit": self.SUBJECT_SHA,
            "target_commit": self.TARGET_SHA,
        }
        return data

    def event_file(self):
        event = {
            "pull_request": {
                "number": self.PR_NUMBER,
                "head": {"sha": self.HEAD_SHA},
                "base": {"sha": self.BASE_SHA},
                "user": {"login": "promoter"},
            }
        }
        handle = tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False)
        json.dump(event, handle)
        handle.close()
        self.addCleanup(lambda: os.path.exists(handle.name) and os.unlink(handle.name))
        return handle.name

    def run_main(self, *, files, head=None, base=None, subject=None, approvals=None, verify=True):
        head = head or self.stable_manifest()
        base = base or self.base_manifest()
        subject = subject or self.base_manifest()
        event_path = self.event_file()

        def repo_manifest(_repo, sha, _path, _token):
            if sha == self.HEAD_SHA:
                return copy.deepcopy(head)
            if sha == self.BASE_SHA:
                return copy.deepcopy(base)
            if sha == self.SUBJECT_SHA:
                return copy.deepcopy(subject)
            raise AssertionError(f"unexpected SHA: {sha}")

        patches = [
            mock.patch.dict(
                os.environ,
                {
                    "GITHUB_TOKEN": "test-token",
                    "GITHUB_EVENT_PATH": event_path,
                    "GITHUB_REPOSITORY": gate.REGISTRY_REPOSITORY,
                },
                clear=False,
            ),
            mock.patch.object(gate, "changed_files", return_value=list(files)),
            mock.patch.object(gate, "json_repo_file", side_effect=repo_manifest),
            mock.patch.object(gate, "latest_approvals", return_value=set(approvals or set())),
        ]
        if verify:
            patches.append(mock.patch.object(gate, "verify_evidence", return_value=None))

        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)
        return gate.main()

    def test_non_stable_development_skips(self):
        result = self.run_main(files=["schema/mgtest-manifest-v1.schema.json"])
        self.assertEqual(result, 0)

    def test_non_stable_manifest_development_skips(self):
        proposed = self.base_manifest()
        result = self.run_main(files=[self.MANIFEST_PATH], head=proposed, base=proposed)
        self.assertEqual(result, 0)

    def test_existing_stable_manifest_cannot_be_demoted(self):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as ctx:
                self.run_main(
                    files=[self.MANIFEST_PATH],
                    head=self.base_manifest(),
                    base=self.stable_manifest(),
                )
        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("existing STABLE manifest is immutable", stderr.getvalue())

    def test_existing_stable_manifest_cannot_be_modified_in_place(self):
        head = self.stable_manifest()
        head["review"]["reviewer_a"] = "different-reviewer"
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as ctx:
                self.run_main(
                    files=[self.MANIFEST_PATH],
                    head=head,
                    base=self.stable_manifest(),
                )
        self.assertEqual(ctx.exception.code, 1)
        self.assertIn("existing STABLE manifest is immutable", stderr.getvalue())

    def test_mixed_code_and_stable_promotion_fails_closed(self):
        with self.assertRaises(SystemExit) as ctx:
            self.run_main(files=[self.MANIFEST_PATH, "tests/MGTEST-NARF-ORDER-001/v1/test.py"])
        self.assertEqual(ctx.exception.code, 1)

    def test_wrong_promotion_pr_fails_closed(self):
        with self.assertRaises(SystemExit) as ctx:
            self.run_main(files=[self.MANIFEST_PATH], head=self.stable_manifest(promotion_pr=99))
        self.assertEqual(ctx.exception.code, 1)

    def test_missing_second_exact_head_approval_fails_closed(self):
        with self.assertRaises(SystemExit) as ctx:
            self.run_main(files=[self.MANIFEST_PATH], approvals={"reviewer-a"})
        self.assertEqual(ctx.exception.code, 1)

    def test_review_pagination_uses_latest_state_across_pages(self):
        page_one = [
            {
                "id": 1,
                "user": {"login": "reviewer-a"},
                "state": "APPROVED",
                "commit_id": self.HEAD_SHA,
                "submitted_at": "2026-10-15T10:00:00Z",
            }
        ]
        for index in range(2, 101):
            page_one.append(
                {
                    "id": index,
                    "user": {"login": f"filler-{index}"},
                    "state": "COMMENTED",
                    "commit_id": self.HEAD_SHA,
                    "submitted_at": "2026-10-15T10:00:00Z",
                }
            )
        page_two = [
            {
                "id": 101,
                "user": {"login": "reviewer-a"},
                "state": "CHANGES_REQUESTED",
                "commit_id": self.HEAD_SHA,
                "submitted_at": "2026-10-15T11:00:00Z",
            },
            {
                "id": 102,
                "user": {"login": "reviewer-b"},
                "state": "APPROVED",
                "commit_id": self.HEAD_SHA,
                "submitted_at": "2026-10-15T11:01:00Z",
            },
        ]

        def fake_api_get(url, _token):
            if "&page=1" in url:
                return page_one
            if "&page=2" in url:
                return page_two
            raise AssertionError(f"unexpected URL: {url}")

        with mock.patch.object(gate, "api_get", side_effect=fake_api_get) as api_get:
            approvals = gate.latest_approvals(
                gate.REGISTRY_REPOSITORY,
                self.PR_NUMBER,
                self.HEAD_SHA,
                set(),
                "test-token",
            )
        self.assertEqual(approvals, {"reviewer-b"})
        self.assertEqual(api_get.call_count, 2)

    def test_pr_run_evidence_is_rejected(self):
        manifest = self.stable_manifest()

        def fake_api_get(url, _token):
            if "/compare/" in url:
                return {"merge_base_commit": {"sha": self.SUBJECT_SHA}}
            if url.endswith("/actions/runs/123"):
                return {
                    "status": "completed",
                    "conclusion": "success",
                    "event": "pull_request",
                    "head_branch": "dev/attacker",
                    "head_sha": self.SUBJECT_SHA,
                    "path": gate.REGISTRY_WORKFLOW_PATH,
                }
            raise AssertionError(f"unexpected URL: {url}")

        with mock.patch.object(gate, "api_get", side_effect=fake_api_get):
            with self.assertRaises(SystemExit) as ctx:
                gate.verify_evidence(
                    gate.REGISTRY_REPOSITORY,
                    self.BASE_SHA,
                    self.MANIFEST_PATH,
                    manifest,
                    "test-token",
                )
        self.assertEqual(ctx.exception.code, 1)

    def test_valid_simulated_promotion_passes(self):
        result = self.run_main(
            files=[self.MANIFEST_PATH, "REGISTRY.md"],
            approvals={"reviewer-a", "reviewer-b"},
        )
        self.assertEqual(result, 0)


    # Ten fail-closed adversarial regression cases. These exercise trusted
    # promotion policy with mocked GitHub API state, not live external reviews.
    def assert_attack_blocked(self, error_part, **kwargs):
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            with self.assertRaises(SystemExit) as ctx:
                self.run_main(files=[self.MANIFEST_PATH], **kwargs)
        self.assertEqual(ctx.exception.code, 1)
        self.assertIn(error_part, stderr.getvalue())

    def test_attack_01_forged_pass_evidence_rejected(self):
        forged = self.stable_manifest()
        forged["evidence"]["result"] = "FAIL"
        self.assert_attack_blocked("STABLE requires PASS evidence", head=forged)

    def test_attack_02_evidence_target_swap_rejected(self):
        forged = self.stable_manifest()
        forged["evidence"]["target_commit"] = "0" * 40
        self.assert_attack_blocked("evidence.target_commit mismatch", head=forged)

    def test_attack_03_semantic_promotion_drift_rejected(self):
        forged = self.stable_manifest()
        forged["purpose"] = "A broader untested safety claim."
        self.assert_attack_blocked("may not change test semantics", head=forged)

    def test_attack_04_test_author_spoof_rejected(self):
        forged = self.stable_manifest()
        forged["review"]["author"] = "different-author"
        self.assert_attack_blocked("review.author may not change", head=forged)

    def test_attack_05_missing_test_author_rejected(self):
        base = self.base_manifest()
        base["review"]["author"] = ""
        forged = self.stable_manifest()
        forged["review"]["author"] = ""
        self.assert_attack_blocked("missing test author", head=forged, base=base)

    def counted_real_approvals(self, names):
        reviews = [
            {
                "id": 100 + i,
                "user": {"login": login},
                "state": "APPROVED",
                "commit_id": self.HEAD_SHA,
                "submitted_at": "2026-10-17T11:00:00Z",
            }
            for i, login in enumerate(names)
        ]
        with mock.patch.object(gate, "api_get", return_value=reviews) as api_get:
            result = gate.latest_approvals(
                gate.REGISTRY_REPOSITORY,
                self.PR_NUMBER,
                self.HEAD_SHA,
                {"promoter", "miguelkolli"},
                "test-token",
            )
        self.assertEqual(api_get.call_count, 1)
        return result

    def test_attack_06_promotion_author_approval_excluded(self):
        counted = self.counted_real_approvals(["promoter", "reviewer-a"])
        self.assertEqual(counted, {"reviewer-a"})
        self.assert_attack_blocked(
            "requires 2 authenticated approvals",
            approvals=counted,
        )

    def test_attack_07_test_author_approval_excluded(self):
        counted = self.counted_real_approvals(["miguelkolli", "reviewer-b"])
        self.assertEqual(counted, {"reviewer-b"})
        self.assert_attack_blocked(
            "requires 2 authenticated approvals",
            approvals=counted,
        )

    def test_attack_08_duplicate_reviewer_identity_rejected(self):
        forged = self.stable_manifest()
        forged["review"]["reviewer_b"] = "reviewer-a"
        self.assert_attack_blocked(
            "reviewer_a and reviewer_b must be distinct",
            head=forged,
            approvals={"reviewer-a", "reviewer-b"},
        )

    def test_attack_09_manifest_reviewer_not_approved_rejected(self):
        forged = self.stable_manifest()
        forged["review"]["reviewer_b"] = "unapproved-user"
        self.assert_attack_blocked(
            "manifest reviewers are not authenticated exact-head approvers",
            head=forged,
            approvals={"reviewer-a", "reviewer-b"},
        )

    def test_attack_10_stale_exact_head_reviews_not_counted(self):
        old_head = "f" * 40
        reviews = [
            {
                "id": 41 + i,
                "user": {"login": user},
                "state": "APPROVED",
                "commit_id": old_head,
                "submitted_at": "2026-10-17T10:00:00Z",
            }
            for i, user in enumerate(("reviewer-a", "reviewer-b"))
        ]
        with mock.patch.object(gate, "api_get", return_value=reviews) as api_get:
            counted = gate.latest_approvals(
                gate.REGISTRY_REPOSITORY,
                self.PR_NUMBER,
                self.HEAD_SHA,
                {"promoter", "miguelkolli"},
                "test-token",
            )
        self.assertEqual(counted, set())
        self.assertEqual(api_get.call_count, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
