import unittest

from tools.status_lattice_verifier import (
    DANGEROUS_PROMOTIONS,
    StatusLatticeError,
    _not_promoted,
    run_all,
    verify_acceptance_lifecycle,
)


class StatusLatticeVerifierTests(unittest.TestCase):
    def test_repository_wide_status_lattice_passes(self):
        report = run_all()
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["verifier"], "mgtest.status-lattice-v2")
        self.assertEqual(
            set(report["checks"]),
            {
                "single_aggregate",
                "dual_aggregate",
                "tool_aggregate",
                "cross_model_comparison",
                "acceptance_lifecycle",
                "live_readiness",
                "stable_promotion_guard",
            },
        )
        for value in report["checks"].values():
            self.assertEqual(value["status"], "PASS")

    def test_acceptance_lifecycle_is_fail_closed(self):
        result = verify_acceptance_lifecycle()
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["non_authoritative_states_checked"], 6)
        self.assertEqual(result["invalid_promotions_rejected"], 3)

    def test_dangerous_promotion_detector_rejects_stronger_states(self):
        for status in sorted(DANGEROUS_PROMOTIONS):
            with self.subTest(status=status):
                with self.assertRaises(StatusLatticeError):
                    _not_promoted(status, "synthetic degraded input")

    def test_non_promoting_states_are_accepted(self):
        for status in ("FAIL", "BLOCKED", "UNVERIFIED", "LIMITATION_CONFIRMED", "LIMITED"):
            with self.subTest(status=status):
                _not_promoted(status, "synthetic degraded input")


if __name__ == "__main__":
    unittest.main()
