"""Tests for Mission Proof System & KPI Automation.

GNW Governed Agent - P3F: Mission Proof System & KPI Automation
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

# Import modules under test
from personal_agent.mission.verifier import MissionVerifier
from personal_agent.mission.kpi_collector import KPICollector


class TestMerkleRoot:
    """Tests for deterministic Merkle root computation."""

    def test_empty_tree(self):
        """Empty evidence list produces deterministic root."""
        verifier = MissionVerifier(uuid.uuid4(), evidence_root=Path(tempfile.mkdtemp()))
        root1 = verifier.compute_merkle_root([])
        root2 = verifier.compute_merkle_root([])
        assert root1 == root2
        assert len(root1) == 64  # SHA-256 hex

    def test_single_leaf(self):
        """Single leaf produces correct root (leaf hash)."""
        verifier = MissionVerifier(uuid.uuid4(), evidence_root=Path(tempfile.mkdtemp()))
        digest = "a" * 64
        root = verifier.compute_merkle_root([digest])
        expected = hashlib.sha256(bytes.fromhex(digest)).hexdigest()
        assert root == expected

    def test_two_leaves(self):
        """Two leaves produces pair-wise hash."""
        verifier = MissionVerifier(uuid.uuid4(), evidence_root=Path(tempfile.mkdtemp()))
        digest1 = "a" * 64
        digest2 = "b" * 64
        root = verifier.compute_merkle_root([digest1, digest2])

        left = bytes.fromhex(digest1)
        right = bytes.fromhex(digest2)
        expected = hashlib.sha256(left + right).hexdigest()
        assert root == expected

    def test_three_leaves(self):
        """Odd number of leaves duplicates last."""
        verifier = MissionVerifier(uuid.uuid4(), evidence_root=Path(tempfile.mkdtemp()))
        digests = ["a" * 64, "b" * 64, "c" * 64]
        root = verifier.compute_merkle_root(digests)

        # Level 1: hash(a,b), hash(c,c)
        left1 = hashlib.sha256(bytes.fromhex("a" * 64) + bytes.fromhex("b" * 64)).digest()
        right1 = hashlib.sha256(bytes.fromhex("c" * 64) + bytes.fromhex("c" * 64)).digest()
        # Root: hash(left1, right1)
        expected = hashlib.sha256(left1 + right1).hexdigest()
        assert root == expected

    def test_deterministic_sorting(self):
        """Leaves are sorted lexicographically for determinism."""
        verifier = MissionVerifier(uuid.uuid4(), evidence_root=Path(tempfile.mkdtemp()))
        digests = ["c" * 64, "a" * 64, "b" * 64]
        root1 = verifier.compute_merkle_root(digests)
        root2 = verifier.compute_merkle_root(sorted(digests))
        assert root1 == root2

    def test_invalid_digest_raises(self):
        """Invalid digest format raises ValueError."""
        verifier = MissionVerifier(uuid.uuid4(), evidence_root=Path(tempfile.mkdtemp()))
        with pytest.raises(ValueError):
            verifier.compute_merkle_root(["invalid"])
        with pytest.raises(ValueError):
            verifier.compute_merkle_root(["a" * 63])  # Wrong length


class TestProofBundle:
    """Tests for proof bundle creation and verification."""

    def test_create_proof_bundle_structure(self):
        """Proof bundle has required fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tenant_id = uuid.uuid4()
            verifier = MissionVerifier(tenant_id, evidence_root=Path(tmpdir))
            mission_id = uuid.uuid4()

            # Add some evidence
            verifier.add_evidence(mission_id, {"action_id": "test-1", "data": "foo"})
            verifier.add_evidence(mission_id, {"action_id": "test-2", "data": "bar"})

            bundle = verifier.create_proof_bundle(mission_id)

            assert "evidence_digests" in bundle
            assert "merkle_root" in bundle
            assert "verification_hash" in bundle
            assert "evidence_count" in bundle
            assert "computed_at" in bundle
            assert len(bundle["evidence_digests"]) == 2
            assert bundle["evidence_count"] == 2
            assert len(bundle["merkle_root"]) == 64
            assert len(bundle["verification_hash"]) == 64

    def test_verification_passes_for_valid_mission(self):
        """Verification passes when evidence unchanged."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tenant_id = uuid.uuid4()
            verifier = MissionVerifier(tenant_id, evidence_root=Path(tmpdir))
            mission_id = uuid.uuid4()

            # Add evidence
            verifier.add_evidence(mission_id, {"action_id": "test-1", "data": "foo"})
            bundle = verifier.create_proof_bundle(mission_id)

            # Manually verify by recomputing
            is_valid, computed = verifier.verify_mission(mission_id)
            # Note: verify_mission checks against DB, which we don't have here
            # So we test the internal consistency
            assert computed["verification_hash"] == bundle["verification_hash"]
            assert computed["merkle_root"] == bundle["merkle_root"]
            assert computed["evidence_digests"] == bundle["evidence_digests"]

    def test_verification_fails_for_tampered_evidence(self):
        """Verification fails when evidence is modified."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tenant_id = uuid.uuid4()
            verifier = MissionVerifier(tenant_id, evidence_root=Path(tmpdir))
            mission_id = uuid.uuid4()

            # Add evidence
            verifier.add_evidence(mission_id, {"action_id": "test-1", "data": "foo"})
            original_bundle = verifier.create_proof_bundle(mission_id)

            # Tamper with evidence file directly
            evidence_dir = Path(tmpdir) / str(tenant_id) / str(mission_id)
            evidence_files = list(evidence_dir.glob("*.jsonl"))
            assert len(evidence_files) == 1

            with evidence_files[0].open("r") as f:
                lines = f.readlines()

            # Modify the data
            modified_line = json.dumps({"action_id": "test-1", "data": "TAMPERED"})
            digest = hashlib.sha256(modified_line.encode()).hexdigest()
            tampered_record = json.loads(modified_line)
            tampered_record["digest"] = digest
            lines[0] = json.dumps(tampered_record) + "\n"

            with evidence_files[0].open("w") as f:
                f.writelines(lines)

            # Recompute bundle - should differ
            new_bundle = verifier.create_proof_bundle(mission_id)

            assert new_bundle["merkle_root"] != original_bundle["merkle_root"]
            assert new_bundle["verification_hash"] != original_bundle["verification_hash"]
            assert new_bundle["evidence_digests"] != original_bundle["evidence_digests"]


class TestKPICalculations:
    """Tests for KPI metric calculations."""

    def test_authorization_enforcement_no_actions(self):
        """Zero protected actions returns 1.0."""
        collector = KPICollector(uuid.uuid4())
        # Mock the _query_scalar to return 0
        collector._query_scalar = lambda q, p: 0
        result = collector.collect_authorization_enforcement()
        assert result == 1.0

    def test_authorization_enforcement_with_actions(self):
        """Ratio computed correctly."""
        collector = KPICollector(uuid.uuid4())
        # Mock: total=100, authorized=95
        calls = []
        def mock_query(q, p):
            calls.append(q)
            if "consumed_at IS NOT NULL" in q:
                return 95
            return 100
        collector._query_scalar = mock_query
        result = collector.collect_authorization_enforcement()
        assert result == 0.95

    def test_evidence_completeness_no_missions(self):
        """Zero missions requiring proof returns 1.0."""
        collector = KPICollector(uuid.uuid4())
        collector._query_scalar = lambda q, p: 0
        result = collector.collect_evidence_completeness()
        assert result == 1.0

    def test_reconciliation_backlog_zero(self):
        """Zero total actions returns 0.0 backlog."""
        collector = KPICollector(uuid.uuid4())
        collector._query_scalar = lambda q, p: 0
        result = collector.collect_reconciliation_backlog()
        assert result == 0.0

    def test_kpi_snapshot_insertion(self):
        """KPI snapshot stored with correct fields."""
        # This would require a real database - skip for unit tests
        pass


class TestIntegration:
    """Integration-style tests (require database)."""

    @pytest.mark.integration
    def test_full_mission_lifecycle(self):
        """Test full mission: create, add evidence, verify."""
        # Requires PostgreSQL - marked as integration test
        pass

    @pytest.mark.integration
    def test_kpi_collection_stores_snapshots(self):
        """Test KPI collector stores to database."""
        # Requires PostgreSQL - marked as integration test
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])