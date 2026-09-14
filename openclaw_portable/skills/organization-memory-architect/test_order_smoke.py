import asyncio
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path


SOURCE = Path(__file__).parent / "openclaw/oc-048-organization-memory-architect/memory_architect.py"
SPEC = importlib.util.spec_from_file_location("oc048_memory_architect", SOURCE)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)

MemoryArchitect = MODULE.MemoryArchitect
AtomicStorage = MODULE.AtomicStorage


class OrderSmokeTests(unittest.TestCase):
    def run_async(self, awaitable):
        return asyncio.run(awaitable)

    def test_scope_is_explicit_and_unknown_scopes_are_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            architect = MemoryArchitect(directory)
            self.run_async(architect.initialize())
            self.assertTrue(self.run_async(architect.capture("private", "value", scope="personal"))["success"])
            self.assertIsNone(self.run_async(architect.retrieve("private")))
            self.assertIsNone(self.run_async(architect.retrieve("private", scope="not-a-scope")))
            self.assertEqual([], self.run_async(architect.search("value", scope="not-a-scope")))

    def test_scope_filter_and_secret_findings_do_not_echo_material(self):
        with tempfile.TemporaryDirectory() as directory:
            architect = MemoryArchitect(directory)
            self.run_async(architect.initialize())
            self.assertTrue(self.run_async(architect.capture("team-note", "visible", scope="team"))["success"])
            self.assertEqual([], self.run_async(architect.search("visible", scope="personal")))
            self.assertEqual("team-note", self.run_async(architect.search("visible", scope="organization"))[0]["key"])

            token = "sk-" + "a" * 24
            blocked = self.run_async(architect.capture("secret-note", {"token": token}, scope="personal"))
            self.assertFalse(blocked["success"])
            self.assertNotIn(token, json.dumps(blocked))
            self.assertEqual("[REDACTED]", blocked["secrets_found"][0]["match"])
            metadata_blocked = self.run_async(architect.capture("metadata-note", "safe", scope="personal", tags=[token]))
            self.assertFalse(metadata_blocked["success"])
            self.assertNotIn(token, json.dumps(metadata_blocked))

    def test_collision_resistant_filenames_and_containment(self):
        with tempfile.TemporaryDirectory() as directory:
            architect = MemoryArchitect(directory)
            self.run_async(architect.initialize())
            self.assertTrue(self.run_async(architect.capture("a/b", 1, scope="personal"))["success"])
            self.assertTrue(self.run_async(architect.capture("a_b", 2, scope="personal"))["success"])
            json_files = list(Path(directory).glob("*.json"))
            self.assertEqual(2, len(json_files))
            self.assertEqual(1, self.run_async(architect.retrieve("a/b", scope="personal")))
            self.assertEqual(2, self.run_async(architect.retrieve("a_b", scope="personal")))

            storage = AtomicStorage(Path(directory))
            with self.assertRaises(ValueError):
                self.run_async(storage.read("../outside.json"))

    def test_integrity_is_verified_before_return(self):
        with tempfile.TemporaryDirectory() as directory:
            architect = MemoryArchitect(directory)
            self.run_async(architect.initialize())
            self.assertTrue(self.run_async(architect.capture("checked", {"answer": 42}, scope="personal"))["success"])
            filename = architect._filename_for_key("checked")
            path = Path(directory) / filename
            payload = json.loads(path.read_text())
            payload["value"]["answer"] = "tampered"
            path.write_text(json.dumps(payload))
            architect._cache.clear()
            self.assertIsNone(self.run_async(architect.retrieve("checked", scope="personal")))

    def test_expired_entry_is_promoted_without_being_deleted(self):
        with tempfile.TemporaryDirectory() as directory:
            architect = MemoryArchitect(directory)
            self.run_async(architect.initialize())
            self.assertTrue(self.run_async(architect.capture("expiring", "keep", scope="personal", tier=2))["success"])
            entry = architect._cache["expiring"]
            entry.updated_at = (datetime.now(timezone.utc) - timedelta(seconds=entry.ttl + 1)).isoformat()
            entry.checksum = entry._compute_checksum()
            self.run_async(architect._save_entry(entry))

            self.assertIsNone(self.run_async(architect.retrieve("expiring", scope="personal")))
            self.assertEqual(3, architect._cache["expiring"].tier)
            self.assertEqual("keep", self.run_async(architect.retrieve("expiring", scope="personal")))


if __name__ == "__main__":
    unittest.main()

# Offline-only smoke test: no provider, messaging, credential, or network calls.
# The filename intentionally starts with test_ so standard discovery runs it first.
# (The package's implementation remains importable without installation.)
# test_order_smoke.py
