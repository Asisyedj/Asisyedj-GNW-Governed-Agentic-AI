import unittest

from reference_governed_council import (
    CouncilState,
    ShadowCouncil,
    digest_evidence,
    evaluate_hypothetical_policy,
    redact_for_council,
)


class CouncilReferenceTests(unittest.TestCase):
    def test_happy_path_reaches_shadow_only_terminal_state(self):
        council = ShadowCouncil("task-1")
        for state in [
            CouncilState.STATIC_VALIDATED,
            CouncilState.COUNCIL_QUEUED,
            CouncilState.PLANNING,
            CouncilState.VERIFYING,
            CouncilState.CRITIQUING,
            CouncilState.JUDGING,
            CouncilState.POLICY_DECIDED,
            CouncilState.SHADOW_COMPLETED,
        ]:
            council.transition(state, "test")
        self.assertEqual(council.state, CouncilState.SHADOW_COMPLETED)
        self.assertEqual(len(council.history), 8)

    def test_invalid_transition_fails_closed(self):
        council = ShadowCouncil("task-2")
        with self.assertRaises(ValueError):
            council.transition(CouncilState.SHADOW_COMPLETED, "skip-work")
        council.fail_closed("schema_invalid")
        self.assertEqual(council.state, CouncilState.FAILED_CLOSED)
        with self.assertRaises(ValueError):
            council.transition(CouncilState.RECEIVED, "terminal-reversal")

    def test_policy_is_always_non_authorizing(self):
        for kwargs, expected in [
            ({"environment": "production", "evidence_complete": True, "critical_risk": False, "high_risk": False}, "require_human_approval"),
            ({"environment": "dev", "evidence_complete": False, "critical_risk": False, "high_risk": False}, "request_more_evidence"),
            ({"environment": "dev", "evidence_complete": True, "critical_risk": True, "high_risk": False}, "deny"),
            ({"environment": "dev", "evidence_complete": True, "critical_risk": False, "high_risk": False}, "allow_limited_execution"),
        ]:
            decision = evaluate_hypothetical_policy(**kwargs)
            self.assertEqual(decision.outcome, expected)
            self.assertFalse(decision.execution_authorized)

    def test_evidence_digest_and_redaction(self):
        self.assertEqual(len(digest_evidence("evidence")), 64)
        safe = redact_for_council({"password": "do-not-store", "nested": {"api_key": "do-not-store"}, "claim": "ok"})
        self.assertEqual(safe["password"], "[REDACTED]")
        self.assertEqual(safe["nested"]["api_key"], "[REDACTED]")
        self.assertEqual(safe["claim"], "ok")


if __name__ == "__main__":
    unittest.main()
