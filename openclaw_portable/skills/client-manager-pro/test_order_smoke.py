import asyncio
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock

PACKAGE_ROOT = Path(__file__).resolve().parent
MODULE_ROOT = PACKAGE_ROOT / "openclaw" / "oc-001-client-manager-pro"
sys.path.insert(0, str(MODULE_ROOT))

from client_manager import (  # noqa: E402
    ApprovalGate,
    CircuitBreaker,
    ClientManagerPro,
    MessageStatus,
)


class OrderSmokeTests(unittest.TestCase):
    def run_async(self, awaitable):
        return asyncio.run(awaitable)

    def make_manager(self, *, dry_run=True):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        manager = ClientManagerPro(
            storage_path=tmp.name,
            dry_run=dry_run,
            provider_timeout=0.25,
            authorized_approvers=["alice"],
        )
        client = manager.add_client("Ada", "ada@example.test")
        return manager, client

    def test_external_provider_is_ordered_after_authorized_approval(self):
        manager, client = self.make_manager(dry_run=False)
        manager.email.send = AsyncMock(
            return_value={"success": True, "channel": "email"}
        )

        result = self.run_async(
            manager.send_message(
                client.id,
                "welcome",
                {
                    "client_name": "Ada",
                    "company_name": "Example",
                    "sender_name": "Team",
                    "sender_title": "Engineer",
                    "kickoff_days": 3,
                },
                channel="email",
            )
        )
        self.assertTrue(result["approval_required"])
        manager.email.send.assert_not_awaited()
        self.assertFalse(manager.approval.approve(result["approval_id"], "intruder"))
        manager.email.send.assert_not_awaited()

        sent = self.run_async(manager.approve_and_send(result["approval_id"], "alice"))
        self.assertTrue(sent["success"])
        self.assertEqual(sent["message_id"], result["message_id"])
        manager.email.send.assert_awaited_once()
        terminal_retry = self.run_async(manager.dispatch_approved(result["approval_id"]))
        self.assertFalse(terminal_retry["success"])
        manager.email.send.assert_awaited_once()

    def test_default_dry_run_never_calls_mocked_provider(self):
        manager, client = self.make_manager(dry_run=True)
        manager.email.send = AsyncMock(return_value={"success": True})
        result = self.run_async(
            manager.send_message(
                client.id,
                "follow_up_1",
                {
                    "client_name": "Ada",
                    "original_subject": "Hello",
                    "topic": "security",
                    "key_point_1": "safe",
                    "key_point_2": "bounded",
                    "sender_name": "Team",
                },
            )
        )
        sent = self.run_async(manager.approve_and_send(result["approval_id"], "alice"))
        self.assertTrue(sent["dry_run"])
        self.assertEqual(manager.messages[result["message_id"]].status, MessageStatus.DRY_RUN.value)
        manager.email.send.assert_not_awaited()

    def test_approval_gate_is_authorized_and_terminal(self):
        gate = ApprovalGate(authorized_approvers=["alice"])
        approval_id = gate.request_approval("external_send", {"value": "x"})
        self.assertFalse(gate.approve(approval_id, "bob"))
        self.assertTrue(gate.reject(approval_id, "alice", "not now"))
        self.assertFalse(gate.approve(approval_id, "alice"))
        self.assertFalse(gate.reject(approval_id, "alice", "again"))
        self.assertEqual(gate.get(approval_id)["status"], "rejected")

    def test_circuit_breaker_uses_total_seconds(self):
        breaker = CircuitBreaker(failure_threshold=1, reset_timeout=1)
        breaker.record_failure("email")
        breaker.last_failure["email"] = datetime.now(timezone.utc) - timedelta(seconds=2)
        allowed, message = breaker.check("email")
        self.assertTrue(allowed)
        self.assertIn("half-open", message)

    def test_schedule_and_sequence_steps_are_bounded(self):
        manager, client = self.make_manager()
        bad_schedule = self.run_async(
            manager.send_message(client.id, "follow_up_1", {}, schedule_at="tomorrow")
        )
        self.assertFalse(bad_schedule["success"])
        with self.assertRaises(ValueError):
            manager.create_sequence(
                client.id,
                "bad",
                [{"delay_hours": -1, "template_id": "welcome"}],
            )
        with self.assertRaises(ValueError):
            manager.create_sequence(
                client.id,
                "bad-template",
                [{"delay_hours": 1, "template_id": "missing"}],
            )
        sequence = manager.create_sequence(
            client.id,
            "valid",
            [{"delay_hours": 0, "template_id": "follow_up_1", "variables": {}}],
        )
        self.assertEqual(sequence.current_step, 0)
        self.assertIsNotNone(sequence.next_run)


if __name__ == "__main__":
    unittest.main()

# Intentional offline-only test: all provider calls are AsyncMock instances.
# No network, credentials, messaging, or external writes are used.
