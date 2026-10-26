"""Tests for approval binding and atomic consumption.

GNW Governed Agent - P3B: Approval Binding & Atomic Consumption
"""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from personal_agent.auth.approval_store import ApprovalStore


class TestApprovalStore:
    """Test suite for ApprovalStore."""

    @pytest.fixture
    def tenant_id(self) -> uuid.UUID:
        return uuid.uuid4()

    @pytest.fixture
    def mock_pool(self):
        """Create a mock connection pool for testing without database."""
        pool = MagicMock()
        conn = MagicMock()
        cur = MagicMock()

        pool.connection.return_value.__enter__.return_value = conn
        conn.cursor.return_value.__enter__.return_value = cur
        conn.commit = MagicMock()

        return pool, conn, cur

    @pytest.fixture
    def store(self, tenant_id, mock_pool):
        """Create an ApprovalStore with mocked database."""
        pool, conn, cur = mock_pool
        store = ApprovalStore(tenant_id, pool=pool)
        return store, cur

    def _make_approval_row(self, tenant_id, **overrides):
        """Create a mock approval row."""
        now = datetime.now(timezone.utc)
        base = {
            "approval_id": uuid.uuid4(),
            "approver_id": uuid.uuid4(),
            "actor_id": uuid.uuid4(),
            "agent_id": None,
            "tenant_id": tenant_id,
            "action_type": "file_write",
            "action_args_hash": "a" * 64,
            "resource_id": None,
            "scope": "tenant",
            "policy_version": "v1.0",
            "valid_from": now - timedelta(hours=1),
            "valid_until": now + timedelta(hours=24),
            "signature": b"\x00" * 32,
            "consumed_at": None,
            "created_at": now,
            "revoked_at": None,
        }
        base.update(overrides)
        return base

    def test_create_approval_generates_signature(self, store, tenant_id):
        """Test that create_approval generates an HMAC signature."""
        store_obj, cur = store

        # Mock the insert to return nothing (just verify call)
        cur.fetchone.return_value = None

        approval = store_obj.create_approval(
            approver_id=uuid.uuid4(),
            actor_id=uuid.uuid4(),
            action_type="file_write",
            action_args_hash="a" * 64,
            scope="tenant",
            policy_version="v1.0",
        )

        assert "approval_id" in approval
        assert "signature" in approval
        assert isinstance(approval["signature"], bytes)
        assert len(approval["signature"]) == 32  # SHA-256 = 32 bytes

        # Verify the INSERT was called
        cur.execute.assert_called()

    def test_create_approval_validates_inputs(self, store):
        """Test input validation in create_approval."""
        store_obj, _ = store

        with pytest.raises(ValueError, match="valid_until must be after valid_from"):
            store_obj.create_approval(
                approver_id=uuid.uuid4(),
                actor_id=uuid.uuid4(),
                action_type="test",
                action_args_hash="a" * 64,
                scope="tenant",
                policy_version="v1.0",
                valid_from=datetime.now(timezone.utc) + timedelta(hours=1),
                valid_until=datetime.now(timezone.utc),
            )

        with pytest.raises(ValueError, match="Invalid scope"):
            store_obj.create_approval(
                approver_id=uuid.uuid4(),
                actor_id=uuid.uuid4(),
                action_type="test",
                action_args_hash="a" * 64,
                scope="invalid_scope",
                policy_version="v1.0",
            )

        with pytest.raises(ValueError, match="action_args_hash must be 64-character hex"):
            store_obj.create_approval(
                approver_id=uuid.uuid4(),
                actor_id=uuid.uuid4(),
                action_type="test",
                action_args_hash="not_hex",
                scope="tenant",
                policy_version="v1.0",
            )

    def test_consume_approval_success(self, store, tenant_id):
        """Test successful approval consumption."""
        store_obj, cur = store

        approval_row = self._make_approval_row(tenant_id)
        # Compute correct signature
        approval_dict = store_obj._approval_to_dict(approval_row)
        correct_sig = store_obj._compute_signature(approval_dict)
        approval_row["signature"] = correct_sig

        cur.fetchone.return_value = approval_row

        result = store_obj.consume_approval(approval_row["approval_id"])

        assert result is not None
        assert result["approval_id"] == approval_row["approval_id"]
        # Verify the stored function was called
        cur.execute.assert_called()
        call_args = cur.execute.call_args[0][0]
        assert "consume_approval" in call_args

    def test_consume_approval_already_consumed_returns_none(self, store, tenant_id):
        """Test that consuming an already-consumed approval returns None."""
        store_obj, cur = store

        # Mock the stored function returning NULL (already consumed)
        cur.fetchone.return_value = None

        result = store_obj.consume_approval(uuid.uuid4())

        assert result is None

    def test_consume_approval_wrong_tenant_returns_none(self, store, tenant_id):
        """Test that consuming approval from different tenant returns None."""
        store_obj, cur = store

        # Stored function returns NULL for cross-tenant
        cur.fetchone.return_value = None

        result = store_obj.consume_approval(uuid.uuid4())

        assert result is None

    def test_consume_approval_tampered_signature_raises(self, store, tenant_id):
        """Test that tampered signature raises ValueError."""
        store_obj, cur = store

        approval_row = self._make_approval_row(tenant_id)
        # Tamper with signature
        approval_row["signature"] = b"\xff" * 32

        cur.fetchone.return_value = approval_row

        with pytest.raises(ValueError, match="HMAC verification failed"):
            store_obj.consume_approval(approval_row["approval_id"])

    def test_verify_approval_valid(self, store, tenant_id):
        """Test verifying a valid approval."""
        store_obj, cur = store

        approval_row = self._make_approval_row(tenant_id)
        approval_dict = store_obj._approval_to_dict(approval_row)
        correct_sig = store_obj._compute_signature(approval_dict)
        approval_row["signature"] = correct_sig

        cur.fetchone.return_value = approval_row

        result = store_obj.verify_approval(approval_row["approval_id"])

        assert result is not None
        assert result["approval_id"] == approval_row["approval_id"]

    def test_verify_approval_expired_returns_none(self, store, tenant_id):
        """Test that expired approval verification returns None."""
        store_obj, cur = store

        approval_row = self._make_approval_row(
            tenant_id,
            valid_until=datetime.now(timezone.utc) - timedelta(hours=1)
        )
        approval_dict = store_obj._approval_to_dict(approval_row)
        correct_sig = store_obj._compute_signature(approval_dict)
        approval_row["signature"] = correct_sig

        # Stored function returns NULL for expired
        cur.fetchone.return_value = None

        result = store_obj.verify_approval(approval_row["approval_id"])

        assert result is None

    def test_verify_approval_revoked_returns_none(self, store, tenant_id):
        """Test that revoked approval verification returns None."""
        store_obj, cur = store

        approval_row = self._make_approval_row(
            tenant_id,
            revoked_at=datetime.now(timezone.utc)
        )
        approval_dict = store_obj._approval_to_dict(approval_row)
        correct_sig = store_obj._compute_signature(approval_dict)
        approval_row["signature"] = correct_sig

        # Stored function returns NULL for revoked
        cur.fetchone.return_value = None

        result = store_obj.verify_approval(approval_row["approval_id"])

        assert result is None

    def test_verify_approval_tampered_signature_returns_none(self, store, tenant_id):
        """Test that tampered signature verification returns None."""
        store_obj, cur = store

        approval_row = self._make_approval_row(tenant_id)
        approval_row["signature"] = b"\xff" * 32  # Wrong signature

        cur.fetchone.return_value = approval_row

        result = store_obj.verify_approval(approval_row["approval_id"])

        assert result is None

    def test_revoke_approval_success(self, store, tenant_id):
        """Test successful approval revocation."""
        store_obj, cur = store

        # Mock revoke_approval returning True
        cur.fetchone.return_value = {"revoke_approval": True}

        result = store_obj.revoke_approval(uuid.uuid4())

        assert result is True

    def test_revoke_approval_not_found_returns_false(self, store, tenant_id):
        """Test revoking non-existent approval returns False."""
        store_obj, cur = store

        cur.fetchone.return_value = {"revoke_approval": False}

        result = store_obj.revoke_approval(uuid.uuid4())

        assert result is False

    def test_compute_action_args_hash(self, store):
        """Test action arguments hash computation."""
        store_obj, _ = store

        args = {"path": "/tmp/test.txt", "content": "hello", "mode": "w"}
        hash1 = store_obj.compute_action_args_hash(args)
        hash2 = store_obj.compute_action_args_hash(args)

        assert hash1 == hash2
        assert len(hash1) == 64
        assert all(c in "0123456789abcdef" for c in hash1)

        # Different args produce different hash
        args2 = {"path": "/tmp/test.txt", "content": "world", "mode": "w"}
        hash3 = store_obj.compute_action_args_hash(args2)
        assert hash1 != hash3

    def test_canonicalization_order(self, store):
        """Test that canonicalization uses fixed field order."""
        store_obj, _ = store

        approval = {
            "approval_id": uuid.uuid4(),
            "approver_id": uuid.uuid4(),
            "actor_id": uuid.uuid4(),
            "tenant_id": uuid.uuid4(),
            "action_type": "test",
            "action_args_hash": "a" * 64,
            "scope": "tenant",
            "policy_version": "v1",
            "valid_from": datetime.now(timezone.utc),
            "valid_until": datetime.now(timezone.utc) + timedelta(hours=1),
            "agent_id": None,
            "resource_id": None,
        }

        canonical1 = store_obj._canonicalize(approval)
        canonical2 = store_obj._canonicalize(approval)

        assert canonical1 == canonical2

        # Verify field order in JSON
        parsed = json.loads(canonical1)
        keys = list(parsed.keys())
        assert keys == store_obj.CANONICAL_FIELDS[:len(keys)]  # Only non-None fields


class TestApprovalStoreConcurrency:
    """Concurrency tests for atomic approval consumption."""

    @pytest.fixture
    def tenant_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def real_store(self, tenant_id):
        """Create a store with in-memory SQLite for concurrency testing."""
        # Use SQLite in-memory for real concurrency testing
        import sqlite3
        from contextlib import contextmanager

        class SQLitePool:
            def __init__(self):
                self.conn = sqlite3.connect(":memory:", check_same_thread=False)
                self.conn.row_factory = sqlite3.Row
                self._init_schema()

            def _init_schema(self):
                cur = self.conn.cursor()
                cur.execute("""
                    CREATE TABLE approvals (
                        approval_id TEXT PRIMARY KEY,
                        approver_id TEXT NOT NULL,
                        actor_id TEXT NOT NULL,
                        agent_id TEXT,
                        tenant_id TEXT NOT NULL,
                        action_type TEXT NOT NULL,
                        action_args_hash TEXT NOT NULL,
                        resource_id TEXT,
                        scope TEXT NOT NULL,
                        policy_version TEXT NOT NULL,
                        valid_from TEXT NOT NULL,
                        valid_until TEXT NOT NULL,
                        signature BLOB NOT NULL,
                        consumed_at TEXT,
                        created_at TEXT DEFAULT (datetime('now')),
                        revoked_at TEXT,
                        UNIQUE (actor_id, action_type, action_args_hash, valid_from)
                    )
                """)
                cur.execute("CREATE INDEX idx_approvals_tenant_valid ON approvals(tenant_id, valid_from, valid_until)")
                self.conn.commit()

            @contextmanager
            def connection(self):
                yield self.conn

            def close(self):
                self.conn.close()

        pool = SQLitePool()
        store = ApprovalStore(tenant_id, pool=pool)
        yield store
        pool.close()

    def test_concurrent_consume_same_approval_only_one_succeeds(self, real_store, tenant_id):
        """Test that only one worker can consume the same approval."""
        store = real_store
        actor_id = uuid.uuid4()
        approver_id = uuid.uuid4()
        action_args_hash = "a" * 64

        # Create approval
        approval = store.create_approval(
            approver_id=approver_id,
            actor_id=actor_id,
            action_type="file_write",
            action_args_hash=action_args_hash,
            scope="tenant",
            policy_version="v1.0",
        )
        approval_id = approval["approval_id"]

        # Try to consume from multiple threads
        results = []
        errors = []

        def consume():
            try:
                result = store.consume_approval(approval_id)
                results.append(result)
            except Exception as e:
                errors.append(e)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(consume) for _ in range(10)]
            for f in as_completed(futures):
                f.result()

        # Exactly one should succeed, rest should get None
        successes = [r for r in results if r is not None]
        failures = [r for r in results if r is None]

        assert len(successes) == 1, f"Expected 1 success, got {len(successes)}"
        assert len(failures) == 9, f"Expected 9 failures, got {len(failures)}"
        assert len(errors) == 0, f"Unexpected errors: {errors}"

        # Verify the successful one has consumed_at set
        assert successes[0]["consumed_at"] is not None

    def test_concurrent_consume_different_approvals_all_succeed(self, real_store, tenant_id):
        """Test that consuming different approvals concurrently all succeed."""
        store = real_store
        actor_id = uuid.uuid4()
        approver_id = uuid.uuid4()

        # Create 10 different approvals
        approval_ids = []
        for i in range(10):
            approval = store.create_approval(
                approver_id=approver_id,
                actor_id=actor_id,
                action_type="file_write",
                action_args_hash=hashlib.sha256(f"args{i}".encode()).hexdigest(),
                scope="tenant",
                policy_version="v1.0",
            )
            approval_ids.append(approval["approval_id"])

        # Consume all concurrently
        results = []

        def consume(aid):
            result = store.consume_approval(aid)
            results.append((aid, result))

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(consume, aid) for aid in approval_ids]
            for f in as_completed(futures):
                f.result()

        # All should succeed
        assert len(results) == 10
        for aid, result in results:
            assert result is not None, f"Approval {aid} should have been consumed"
            assert result["approval_id"] == aid
            assert result["consumed_at"] is not None


class TestHMACVerification:
    """Tests specifically for HMAC signature verification."""

    def test_hmac_constant_time_comparison(self):
        """Test that hmac.compare_digest is used for constant-time comparison."""
        import hmac
        from personal_agent.auth.approval_store import ApprovalStore

        # Verify the store uses hmac.compare_digest
        import inspect
        source = inspect.getsource(ApprovalStore._verify_signature)
        assert "hmac.compare_digest" in source
        assert "==" not in source or "compare_digest" in source

    def test_hmac_different_keys_produce_different_signatures(self):
        """Test that different HMAC keys produce different signatures."""
        tenant1 = uuid.uuid4()
        tenant2 = uuid.uuid4()

        store1 = ApprovalStore(tenant1, dsn="postgresql://fake")
        store2 = ApprovalStore(tenant2, dsn="postgresql://fake")

        approval = {
            "approval_id": uuid.uuid4(),
            "approver_id": uuid.uuid4(),
            "actor_id": uuid.uuid4(),
            "tenant_id": tenant1,
            "action_type": "test",
            "action_args_hash": "a" * 64,
            "scope": "tenant",
            "policy_version": "v1",
            "valid_from": datetime.now(timezone.utc),
            "valid_until": datetime.now(timezone.utc) + timedelta(hours=1),
        }

        sig1 = store1._compute_signature(approval)
        sig2 = store2._compute_signature(approval)

        assert sig1 != sig2
        assert len(sig1) == 32
        assert len(sig2) == 32

    def test_hmac_same_inputs_produce_same_signature(self):
        """Test deterministic HMAC signatures."""
        tenant_id = uuid.uuid4()
        store1 = ApprovalStore(tenant_id, dsn="postgresql://fake")
        store2 = ApprovalStore(tenant_id, dsn="postgresql://fake")

        approval = {
            "approval_id": uuid.uuid4(),
            "approver_id": uuid.uuid4(),
            "actor_id": uuid.uuid4(),
            "tenant_id": tenant_id,
            "action_type": "test",
            "action_args_hash": "a" * 64,
            "scope": "tenant",
            "policy_version": "v1",
            "valid_from": datetime.now(timezone.utc),
            "valid_until": datetime.now(timezone.utc) + timedelta(hours=1),
        }

        sig1 = store1._compute_signature(approval)
        sig2 = store2._compute_signature(approval)

        assert sig1 == sig2


class TestApprovalSchemaValidation:
    """Tests for approval schema validation."""

    def test_approval_schema_exists(self):
        """Test that approval schema file exists and is valid JSON."""
        schema_path = Path(__file__).parent.parent / "auth" / "approval_schema.json"
        assert schema_path.exists()

        with open(schema_path) as f:
            schema = json.load(f)

        assert schema["$schema"] == "http://json-schema.org/draft-07/schema#"
        assert "properties" in schema
        assert "required" in schema
        assert "propertyOrder" in schema

    def test_approval_schema_required_fields(self):
        """Test that schema has all required fields."""
        schema_path = Path(__file__).parent.parent / "auth" / "approval_schema.json"
        with open(schema_path) as f:
            schema = json.load(f)

        required = schema["required"]
        expected_required = [
            "approval_id", "approver_id", "actor_id", "tenant_id",
            "action_type", "action_args_hash", "scope", "policy_version",
            "valid_from", "valid_until"
        ]
        for field in expected_required:
            assert field in required, f"Missing required field: {field}"

    def test_approval_schema_property_order_matches_store(self):
        """Test that schema propertyOrder matches store CANONICAL_FIELDS."""
        schema_path = Path(__file__).parent.parent / "auth" / "approval_schema.json"
        with open(schema_path) as f:
            schema = json.load(f)

        # Schema propertyOrder should match store CANONICAL_FIELDS
        assert schema["propertyOrder"] == ApprovalStore.CANONICAL_FIELDS


class TestIntegrationWithDatabase:
    """Integration tests that require a real PostgreSQL database.
    
    These tests are skipped unless GNW_PG_DSN is set.
    """
    
    @pytest.fixture
    def tenant_id(self):
        return uuid.uuid4()

    @pytest.fixture
    def dsn(self):
        dsn = os.environ.get("GNW_PG_DSN")
        if not dsn:
            pytest.skip("GNW_PG_DSN not set, skipping integration tests")
        return dsn

    def test_full_lifecycle_with_real_db(self, dsn, tenant_id):
        """Test full approval lifecycle with real database."""
        store = ApprovalStore(tenant_id, dsn=dsn)

        try:
            actor_id = uuid.uuid4()
            approver_id = uuid.uuid4()
            action_args_hash = hashlib.sha256(b"test action args").hexdigest()

            # Create
            approval = store.create_approval(
                approver_id=approver_id,
                actor_id=actor_id,
                action_type="file_write",
                action_args_hash=action_args_hash,
                scope="tenant",
                policy_version="v1.0",
                valid_until=datetime.now(timezone.utc) + timedelta(hours=1),
            )
            assert approval["approval_id"] is not None
            assert approval["signature"] is not None

            approval_id = approval["approval_id"]

            # Verify (not consumed)
            verified = store.verify_approval(approval_id)
            assert verified is not None
            assert verified["approval_id"] == approval_id
            assert verified["consumed_at"] is None

            # Consume
            consumed = store.consume_approval(approval_id)
            assert consumed is not None
            assert consumed["approval_id"] == approval_id
            assert consumed["consumed_at"] is not None

            # Verify after consume returns None (already consumed)
            verified_after = store.verify_approval(approval_id)
            assert verified_after is not None  # verify doesn't check consumption
            # But consume again returns None
            consumed_again = store.consume_approval(approval_id)
            assert consumed_again is None

            # Revoke
            revoked = store.revoke_approval(approval_id)
            assert revoked is True

            # Verify after revoke returns None
            verified_revoked = store.verify_approval(approval_id)
            assert verified_revoked is None

        finally:
            store.close()

    def test_cross_tenant_isolation(self, dsn):
        """Test that approvals are isolated by tenant."""
        tenant1 = uuid.uuid4()
        tenant2 = uuid.uuid4()

        store1 = ApprovalStore(tenant1, dsn=dsn)
        store2 = ApprovalStore(tenant2, dsn=dsn)

        try:
            actor_id = uuid.uuid4()
            approver_id = uuid.uuid4()
            action_args_hash = hashlib.sha256(b"test").hexdigest()

            # Create approval in tenant1
            approval = store1.create_approval(
                approver_id=approver_id,
                actor_id=actor_id,
                action_type="test",
                action_args_hash=action_args_hash,
                scope="tenant",
                policy_version="v1.0",
            )

            # Try to consume from tenant2 - should fail
            result = store2.consume_approval(approval["approval_id"])
            assert result is None

            # Try to verify from tenant2 - should fail
            result = store2.verify_approval(approval["approval_id"])
            assert result is None

            # Consume from tenant1 - should succeed
            result = store1.consume_approval(approval["approval_id"])
            assert result is not None

        finally:
            store1.close()
            store2.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])