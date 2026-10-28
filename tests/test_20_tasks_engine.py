"""
Unit Tests for GNW 20 Heavy Continuous Tasks Orchestration Engine
=================================================================
Verifies task registry, batching logic, execution isolation, and report generation.
Compatible with standard library unittest and pytest.
"""

import os
import json
import unittest
from pathlib import Path
import sys

# Fast deterministic mode for unit tests
os.environ["GNW_SKIP_LIVE_SWARM"] = "1"

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from scripts.run_20_heavy_tasks import (
    TASK_DEFINITIONS,
    TASK_HANDLERS,
    execute_single_task,
    run_20_tasks_batched,
    generate_reports,
)

class Test20TasksEngine(unittest.TestCase):

    def test_task_registry_completeness(self):
        """Ensure all 20 tasks have definitions and registered handlers."""
        self.assertEqual(len(TASK_DEFINITIONS), 20)
        self.assertEqual(len(TASK_HANDLERS), 20)
        for tid in range(1, 21):
            self.assertIn(tid, TASK_DEFINITIONS)
            self.assertIn(tid, TASK_HANDLERS)
            self.assertTrue(len(TASK_DEFINITIONS[tid]["title"]) > 0)
            self.assertTrue(len(TASK_DEFINITIONS[tid]["pillar"]) > 0)

    def test_four_pillars_coverage(self):
        """Verify each of the 4 pillars contains exactly 5 tasks."""
        pillars = {}
        for tid, defn in TASK_DEFINITIONS.items():
            p = defn["pillar"]
            pillars[p] = pillars.get(p, 0) + 1

        expected_pillars = [
            "Frontier Cognitive Swarm",
            "Cryptographic Core",
            "AWS Cloud & Distributed Scale",
            "Autonomous Agent & MCP Engine",
        ]
        for ep in expected_pillars:
            self.assertIn(ep, pillars, f"Missing pillar: {ep}")
            self.assertEqual(pillars[ep], 5, f"Pillar {ep} does not have exactly 5 tasks")

    def test_execute_single_crypto_and_system_tasks(self):
        """Verify individual execution of representative core tasks."""
        # Test Task 6 (Crypto tokens)
        res6 = execute_single_task(6)
        self.assertEqual(res6["task_id"], 6)
        self.assertEqual(res6["status"], "passed")
        self.assertGreaterEqual(res6["duration_ms"], 0)

        # Test Task 8 (Merkle tree)
        res8 = execute_single_task(8)
        self.assertEqual(res8["task_id"], 8)
        self.assertEqual(res8["status"], "passed")

        # Test Task 10 (Anti-replay nonce)
        res10 = execute_single_task(10)
        self.assertEqual(res10["task_id"], 10)
        self.assertEqual(res10["status"], "passed")

    def test_run_batched_suite_execution(self):
        """Verify executing 20 tasks in batches of 4 produces 20 valid results."""
        results = run_20_tasks_batched(batch_size=4)
        self.assertEqual(len(results), 20)

        # Ensure all task IDs from 1 to 20 are present and unique
        tids = [r["task_id"] for r in results]
        self.assertEqual(sorted(tids), list(range(1, 21)))

        # Verify no fatal unhandled exceptions
        for r in results:
            self.assertIn(r["status"], ["passed", "failed"])
            self.assertIn("duration_ms", r)
            self.assertIn("pillar", r)

    def test_report_generation(self):
        """Verify generation and structural validity of Markdown and JSON reports."""
        results = run_20_tasks_batched(batch_size=4)
        paths = generate_reports(results, WORKSPACE_ROOT)

        md_path = paths["md"]
        json_path = paths["json"]

        self.assertTrue(md_path.exists())
        self.assertTrue(json_path.exists())

        # Inspect JSON report schema
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["schema_version"], "1.0")
        self.assertIn("run_id", data)
        self.assertEqual(data["summary"]["total_tasks"], 20)
        self.assertEqual(len(data["tasks"]), 20)

        # Verify Markdown content
        md_text = md_path.read_text(encoding="utf-8")
        self.assertIn("# GNW System 20 Heavy Continuous Tasks Evaluation Report", md_text)
        self.assertIn("| ID | Pillar | Task Name | Status |", md_text)

if __name__ == "__main__":
    unittest.main()
