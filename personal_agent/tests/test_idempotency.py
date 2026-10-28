"""Tests for Idempotency Keys & Dispatch Records (P3D).

Tests cover:
- Deterministic action IDs (same args -> same id, different args -> different id)
- Dispatch / provider-response recording
- Ambiguous action detection (dispatched but never answered)
- Reconciliation marks actions for operators
- Duplicate dispatch handling (upsert, no double rows)
- Strict multi-tenant isolation (cross-tenant reads/writes are refused)
"""

from __future__ import annotations

import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

from personal_agent.state.idempotency import (
    CrossTenantConflictError,
    IdempotencyStore,
    canonicalize_args,
    generate_action_id,
    generate_idempotency_key,
    hash_response,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

OPERATOR_ID = uuid.UUID("22222222-2222-2222-2222-222222222222")


def _unique_requirement(prefix: str = "req") -> str:
    """A fresh requirement id so tests never collide on action_id."""
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def _resolve(db_path: Path, action_id: str) -> Optional[Dict[str, Any]]:
    """Read a dispatch row directly from SQLite, bypassing tenant filters."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM dispatch_records WHERE action_id = ?", (action_id,)
        ).fetchone()
        return dict(row) if row is not None else None
    finally:
        conn.close()


def _backdate(db_path: Path, action_id: str, seconds: float) -> None:
    """Age a dispatch's last_attempt_at so it looks stale."""
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute(
            "UPDATE dispatch_records SET last_attempt_at = ? WHERE action_id = ?",
            (time.time() - seconds, action_id),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def store(tmp_path: Path) -> IdempotencyStore:
    """A per-test store on an isolated database file and tenant."""
    return IdempotencyStore(db_path=tmp_path / "idempotency.db", tenant_id=uuid.uuid4())


def _dispatch(store: IdempotencyStore, requirement_id: str, args: Dict[str, Any]) -> str:
    """Record a dispatch for `args` under `requirement_id`; returns action_id."""
    action_id = generate_action_id(requirement_id, args)
    store.record_dispatch(
        action_id=action_id,
        requirement_id=requirement_id,
        canonical_args_hash=hash_response(args),
        component="router",
        idempotency_key=generate_idempotency_key(action_id, 1),
    )
    return action_id


# ---------------------------------------------------------------------------
# Deterministic action IDs
# ---------------------------------------------------------------------------


class TestDeterministicActionIds:
    """Action IDs must be a pure function of (requirement_id, args)."""

    def test_same_args_same_action_id(self) -> None:
        """Identical requirement + args always yield the same action_id."""
        args = {"model": "gpt-x", "messages": [{"role": "user", "content": "hi"}], "timeout": 30.0}

        first = generate_action_id("req-1", args)
        second = generate_action_id("req-1", args)

        assert first == second
        assert len(first) == 64  # SHA-256 hex digest

    def test_canonicalization_is_key_order_independent(self) -> None:
        """Key ordering must not affect the derived id."""
        a = generate_action_id("req-1", {"b": 2, "a": 1})
        b = generate_action_id("req-1", {"a": 1, "b": 2})
        assert a == b

        # Canonical JSON is sorted and whitespace-free
        assert canonicalize_args({"b": 2, "a": 1}) == '{"a":1,"b":2}'

    def test_different_args_different_action_id(self) -> None:
        """Any change to the arguments produces a different action_id."""
        base = {"model": "gpt-x", "timeout": 30.0}

        a = generate_action_id("req-1", base)
        b = generate_action_id("req-1", {**base, "timeout": 60.0})
        c = generate_action_id("req-1", {**base, "model": "gpt-y"})

        assert len({a, b, c}) == 3

    def test_different_requirement_different_action_id(self) -> None:
        """The requirement_id namespaces the action."""
        args = {"model": "gpt-x"}

        assert generate_action_id("req-1", args) != generate_action_id("req-2", args)


# ---------------------------------------------------------------------------
# Dispatch recording
# ---------------------------------------------------------------------------


class TestDispatchRecords:
    """Dispatch records persist the pre-call intent of every provider call."""

    def test_dispatch_recorded(self, store: IdempotencyStore) -> None:
        """A recorded dispatch is retrievable with its dispatch metadata."""
        requirement_id = _unique_requirement()
        args = {"model": "gpt-x", "messages": [{"role": "user", "content": "hi"}]}
        action_id = _dispatch(store, requirement_id, args)

        record = store.get_dispatch(action_id)

        assert record is not None
        assert record["action_id"] == action_id
        assert record["requirement_id"] == requirement_id
        assert record["component"] == "router"
        assert record["status"] == "dispatched"
        assert record["attempts"] == 1
        assert record["tenant_id"] == store.tenant_id
        assert record["canonical_args_hash"] == hash_response(args)
        assert record["idempotency_key"] == generate_idempotency_key(action_id, 1)
        assert record["created_at"] > 0.0
        assert record["provider_request_id"] is None
        assert record["response_hash"] is None

    def test_dispatch_not_recorded_returns_none(self, store: IdempotencyStore) -> None:
        """Unknown action ids have no record."""
        assert store.get_dispatch("0" * 64) is None

    def test_provider_response_recorded(self, store: IdempotencyStore) -> None:
        """A provider response closes the dispatch and stores its hash."""
        action_id = _dispatch(store, _unique_requirement(), {"model": "gpt-x"})
        response = {"id": "resp-123", "choices": [{"message": {"content": "hello"}}]}
        digest = hash_response(response)

        updated = store.record_provider_response(
            action_id=action_id,
            provider_request_id="resp-123",
            response_hash=digest,
            status="succeeded",
        )

        assert updated is True
        record = store.get_dispatch(action_id)
        assert record is not None
        assert record["status"] == "succeeded"
        assert record["provider_request_id"] == "resp-123"
        assert record["response_hash"] == digest

    def test_provider_response_recorded_for_other_tenant(self, store: IdempotencyStore, tmp_path: Path) -> None:
        """A response cannot be written into another tenant's row."""
        action_id = _dispatch(store, _unique_requirement(), {"model": "gpt-x"})

        other = IdempotencyStore(db_path=store.db_path, tenant_id=uuid.uuid4())
        assert other.get_dispatch(action_id) is None
        assert (
            other.record_provider_response(
                action_id=action_id,
                provider_request_id="resp-999",
                response_hash="deadbeef",
                status="succeeded",
            )
            is False
        )

        # Original row untouched
        assert store.get_dispatch(action_id)["provider_request_id"] is None

    def test_invalid_response_status_rejected(self, store: IdempotencyStore) -> None:
        """Only 'succeeded' / 'failed' are valid terminal statuses."""
        action_id = _dispatch(store, _unique_requirement(), {"model": "gpt-x"})

        with pytest.raises(ValueError):
            store.record_provider_response(
                action_id=action_id,
                provider_request_id="resp-1",
                response_hash="abc",
                status="dispatched",
            )


# ---------------------------------------------------------------------------
# Ambiguity detection
# ---------------------------------------------------------------------------


class TestAmbiguousActions:
    """Dispatches without a response are what operators must reconcile."""

    def test_ambiguous_detection(self, store: IdempotencyStore, tmp_path: Path) -> None:
        """A stale 'dispatched' row with no response is ambiguous."""
        action_id = _dispatch(store, _unique_requirement(), {"model": "gpt-x"})

        # A fresh dispatch is not ambiguous yet
        assert store.get_ambiguous_actions(older_than_minutes=5) == []

        _backdate(Path(store.db_path), action_id, 3600)

        ambiguous = store.get_ambiguous_actions(older_than_minutes=5)
        assert [r["action_id"] for r in ambiguous] == [action_id]
        assert ambiguous[0]["status"] == "dispatched"
        assert ambiguous[0]["response_hash"] is None
        assert ambiguous[0]["tenant_id"] == store.tenant_id

    def test_answered_dispatch_is_not_ambiguous(self, store: IdempotencyStore) -> None:
        """Once the provider answered, the action is no longer ambiguous."""
        action_id = _dispatch(store, _unique_requirement(), {"model": "gpt-x"})
        store.record_provider_response(action_id, "resp-1", "digest", "succeeded")

        assert store.get_ambiguous_actions(older_than_minutes=0) == []

    def test_ambiguous_threshold_respected(self, store: IdempotencyStore) -> None:
        """An action younger than the threshold is not reported."""
        action_id = _dispatch(store, _unique_requirement(), {"model": "gpt-x"})
        _backdate(Path(store.db_path), action_id, 120)  # 2 minutes old

        assert store.get_ambiguous_actions(older_than_minutes=5) == []
        assert [r["action_id"] for r in store.get_ambiguous_actions(older_than_minutes=1)] == [action_id]


# ---------------------------------------------------------------------------
# Reconciliation
# ---------------------------------------------------------------------------


class TestReconciliation:
    """Operators close out ambiguous actions with an audit stamp."""

    def test_reconciliation_marks_action(self, store: IdempotencyStore) -> None:
        """reconcile() stamps reconciled_at/by/action and closes the record."""
        action_id = _dispatch(store, _unique_requirement(), {"model": "gpt-x"})

        ok = store.reconcile(action_id, "succeeded", OPERATOR_ID)

        assert ok is True
        record = store.get_dispatch(action_id)
        assert record is not None
        assert record["status"] == "reconciled"
        assert record["reconciled_action"] == "mark_succeeded"
        assert record["reconciled_by"] == str(OPERATOR_ID)
        assert record["reconciled_at"] > 0.0

    def test_reconciliation_with_mark_alias(self, store: IdempotencyStore) -> None:
        """The 'mark_*' spellings are accepted for backwards compatibility."""
        action_id = _dispatch(store, _unique_requirement(), {"model": "gpt-x"})

        assert store.reconcile(action_id, "mark_failed", OPERATOR_ID) is True
        assert store.get_dispatch(action_id)["reconciled_action"] == "mark_failed"

    def test_reconciliation_retry_reopens_action(self, store: IdempotencyStore) -> None:
        """'retry' re-opens the dispatch (audited) and bumps the attempt count."""
        action_id = _dispatch(store, _unique_requirement(), {"model": "gpt-x"})

        assert store.reconcile(action_id, "retry", OPERATOR_ID) is True

        record = store.get_dispatch(action_id)
        assert record is not None
        assert record["status"] == "dispatched"
        assert record["reconciled_action"] == "retry"
        assert record["attempts"] == 2
        assert record["reconciled_by"] == str(OPERATOR_ID)

    def test_reconcile_rejects_unknown_action(self, store: IdempotencyStore) -> None:
        """Fail closed on an unrecognised reconciliation verb."""
        action_id = _dispatch(store, _unique_requirement(), {"model": "gpt-x"})

        with pytest.raises(ValueError):
            store.reconcile(action_id, "maybe", OPERATOR_ID)

    def test_reconcile_unknown_action_id_returns_false(self, store: IdempotencyStore) -> None:
        """Reconciling a record that does not exist is a no-op."""
        assert store.reconcile("0" * 64, "succeeded", OPERATOR_ID) is False

    def test_reconcile_refuses_terminal_status(self, store: IdempotencyStore) -> None:
        """A completed dispatch cannot be silently re-reconciled."""
        action_id = _dispatch(store, _unique_requirement(), {"model": "gpt-x"})
        store.record_provider_response(action_id, "resp-1", "digest", "succeeded")

        with pytest.raises(ValueError):
            store.reconcile(action_id, "failed", OPERATOR_ID)


# ---------------------------------------------------------------------------
# Duplicate dispatch
# ---------------------------------------------------------------------------


class TestNoDuplicateDispatch:
    """Repeating the same work must not produce a second dispatch row."""

    def test_no_duplicate_dispatch(self, store: IdempotencyStore) -> None:
        """The same action_id upserts: one row, attempts incremented."""
        requirement_id = _unique_requirement()
        args = {"model": "gpt-x", "messages": [{"role": "user", "content": "hi"}]}
        action_id = generate_action_id(requirement_id, args)

        first = store.record_dispatch(action_id, requirement_id, hash_response(args), "router", "k-1")
        second = store.record_dispatch(action_id, requirement_id, hash_response(args), "router", "k-2")

        # Same underlying record, no duplicate row created
        assert first == second
        assert len(store.list_all()) == 1

        record = store.get_dispatch(action_id)
        assert record is not None
        assert record["attempts"] == 2
        assert record["idempotency_key"] == "k-2"
        assert record["status"] == "dispatched"

    def test_no_duplicate_dispatch_preserves_success(self, store: IdempotencyStore) -> None:
        """A succeeded action must not be re-opened by a repeat dispatch."""
        requirement_id = _unique_requirement()
        args = {"model": "gpt-x"}
        action_id = generate_action_id(requirement_id, args)

        store.record_dispatch(action_id, requirement_id, hash_response(args), "router", "k-1")
        store.record_provider_response(action_id, "resp-1", "digest", "succeeded")
        store.record_dispatch(action_id, requirement_id, hash_response(args), "router", "k-2")

        record = store.get_dispatch(action_id)
        assert record is not None
        assert record["status"] == "succeeded"
        assert record["attempts"] == 2

    def test_distinct_actions_produce_distinct_rows(self, store: IdempotencyStore) -> None:
        """Different logical work still gets its own record."""
        _dispatch(store, _unique_requirement(), {"model": "gpt-x"})
        _dispatch(store, _unique_requirement(), {"model": "gpt-y"})

        assert len(store.list_all()) == 2


# ---------------------------------------------------------------------------
# Multi-tenant isolation
# ---------------------------------------------------------------------------


class TestMultiTenantIsolation:
    """Tenant rows are invisible and unwritable across tenant boundaries."""

    def test_multi_tenant_isolation(self, tmp_path: Path) -> None:
        """Tenant A's dispatches are unreachable from tenant B."""
        db_path = tmp_path / "idempotency.db"
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()
        store_a = IdempotencyStore(db_path=db_path, tenant_id=tenant_a)
        store_b = IdempotencyStore(db_path=db_path, tenant_id=tenant_b)

        # Tenant A dispatches two actions
        a1 = _dispatch(store_a, _unique_requirement(), {"model": "gpt-x"})
        a2 = _dispatch(store_a, _unique_requirement(), {"model": "gpt-y"})

        # Tenant A can see its own records
        assert store_a.get_dispatch(a1) is not None
        assert store_a.get_dispatch(a2) is not None

        # Tenant B cannot see them
        assert store_b.get_dispatch(a1) is None
        assert store_b.get_dispatch(a2) is None
        assert store_b.list_all() == []
        assert {r["action_id"] for r in store_b.get_ambiguous_actions(older_than_minutes=0)} == set()

        # Tenant A's records are aged so they'd be ambiguous if visible
        _backdate(db_path, a1, 3600)
        _backdate(db_path, a2, 3600)

        assert {r["action_id"] for r in store_a.get_ambiguous_actions(older_than_minutes=5)} == {a1, a2}
        assert store_b.get_ambiguous_actions(older_than_minutes=0) == []

        # Tenant B cannot reconcile tenant A's actions
        assert store_b.reconcile(a1, "succeeded", OPERATOR_ID) is False
        assert _resolve(db_path, a1)["status"] == "dispatched"
        assert store_b.record_provider_response(a1, "resp-x", "digest", "succeeded") is False

        # Tenant B writing the same action_id is refused (fail closed)
        with pytest.raises(CrossTenantConflictError):
            store_b.record_dispatch(a1, "req", "hash", "router", "k")

        # Tenant B's own dispatch is visible only to it
        b1 = _dispatch(store_b, _unique_requirement(), {"model": "gpt-z"})
        assert store_b.get_dispatch(b1) is not None
        assert store_a.get_dispatch(b1) is None
        assert len(store_a.list_all()) == 2
        assert len(store_b.list_all()) == 1

    def test_stats_are_tenant_scoped(self, tmp_path: Path) -> None:
        """Aggregate counts never leak across tenants."""
        db_path = tmp_path / "idempotency.db"
        store_a = IdempotencyStore(db_path=db_path, tenant_id=uuid.uuid4())
        store_b = IdempotencyStore(db_path=db_path, tenant_id=uuid.uuid4())

        _dispatch(store_a, _unique_requirement(), {"model": "gpt-x"})
        _dispatch(store_b, _unique_requirement(), {"model": "gpt-y"})

        assert store_a.get_stats() == {"dispatched": 1}
        assert store_b.get_stats() == {"dispatched": 1}


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------


def test_global_store_singleton() -> None:
    """The module-level singleton is a real IdempotencyStore instance."""
    from personal_agent.state.idempotency import global_idempotency_store

    assert isinstance(global_idempotency_store, IdempotencyStore)
    assert global_idempotency_store.tenant_id == "00000000-0000-0000-0000-000000000001"
