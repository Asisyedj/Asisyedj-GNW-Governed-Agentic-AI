"""Idempotency Keys & Dispatch Records for GNW Governed Agent.

Provides deterministic action IDs, canonical argument serialization,
and a store for tracking provider dispatch records with reconciliation support.

Every outbound provider call is recorded *before* it is made so that a crash
between "call sent" and "response received" leaves an auditable trail that a
human operator can reconcile later (see ``personal_agent/tools/reconcile.py``).

Storage is SQLite-backed (``personal_agent/data/idempotency.db`` by default),
with timestamps stored as unix epoch seconds (REAL) to stay compatible with
``database/migrations/003_idempotency.sql``. UUIDs are stored as TEXT.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

# Database path - uses the same data directory as the other state stores
DB_PATH = Path(__file__).parent.parent / "data" / "idempotency.db"

# Default tenant ID for single-tenant deployments
DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000001"

# Dispatch lifecycle statuses
STATUS_DISPATCHED = "dispatched"
STATUS_SUCCEEDED = "succeeded"
STATUS_FAILED = "failed"
STATUS_RECONCILED = "reconciled"
STATUS_AMBIGUOUS = "ambiguous"

# Reconciliation actions (accepted spellings)
_RECONCILE_ALIASES = {
    "succeeded": "mark_succeeded",
    "mark_succeeded": "mark_succeeded",
    "failed": "mark_failed",
    "mark_failed": "mark_failed",
    "retry": "retry",
}
_VALID_RESPONSE_STATUSES = (STATUS_SUCCEEDED, STATUS_FAILED)
_RECONCILABLE_STATUSES = (STATUS_DISPATCHED, STATUS_AMBIGUOUS)

# ---------------------------------------------------------------------------
# Canonicalization & hashing
# ---------------------------------------------------------------------------


def canonicalize_args(args_dict: Dict[str, Any]) -> str:
    """Canonicalize arguments to a deterministic JSON string.

    - Keys sorted lexicographically
    - No whitespace
    - Non-ASCII preserved (escaped consistently by the encoder)

    Same logical arguments always produce the identical string, which is what
    makes the derived hashes stable and safe to bind cryptographically.
    """
    return json.dumps(
        args_dict,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def canonical_args_hash(args_dict: Dict[str, Any]) -> str:
    """SHA-256 over the canonical serialization of ``args_dict``."""
    return hashlib.sha256(canonicalize_args(args_dict).encode("utf-8")).hexdigest()


def generate_action_id(requirement_id: str, args_dict: Dict[str, Any]) -> str:
    """Generate a deterministic SHA-256 action ID from requirement_id and args.

    The action_id is computed as::

        SHA256(requirement_id || "|" || canonical_args)

    This ensures:
    - Same requirement + same args = same action_id (idempotency)
    - Different args = different action_id
    - The requirement ID provides namespacing

    Args:
        requirement_id: Requirement being fulfilled.
        args_dict: The exact arguments of the action.

    Returns:
        64-character lowercase hex digest.
    """
    canonical_args = canonicalize_args(args_dict)
    combined = f"{requirement_id}|{canonical_args}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def generate_idempotency_key(action_id: str, attempt: int = 1) -> str:
    """Generate an idempotency key for provider calls.

    Format: ``{action_id}-{attempt}``

    This allows a retry to reuse the same action_id (same logical work) while
    carrying a distinct provider-side key for the new attempt.
    """
    return f"{action_id}-{attempt}"


def hash_response(response: Any) -> str:
    """Compute a SHA-256 hash of a provider response for audit verification."""
    if isinstance(response, (dict, list)):
        content = json.dumps(response, sort_keys=True, separators=(",", ":"))
    else:
        content = str(response)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class IdempotencyError(RuntimeError):
    """Base error for idempotency store operations."""


class CrossTenantConflictError(IdempotencyError):
    """Raised when an action_id already exists under a different tenant.

    Fail-closed: silently writing would break strict multi-tenant isolation.
    """


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS dispatch_records (
    id TEXT PRIMARY KEY,
    action_id TEXT NOT NULL UNIQUE,
    requirement_id TEXT NOT NULL,
    canonical_args_hash TEXT NOT NULL,
    component TEXT NOT NULL,
    provider_request_id TEXT,
    idempotency_key TEXT,
    status TEXT NOT NULL DEFAULT 'dispatched',
    response_hash TEXT,
    attempts INTEGER DEFAULT 0,
    last_attempt_at REAL,
    reconciled_at REAL,
    reconciled_by TEXT,
    reconciled_action TEXT,
    created_at REAL NOT NULL,
    tenant_id TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_dispatch_action ON dispatch_records(action_id);
CREATE INDEX IF NOT EXISTS idx_dispatch_status ON dispatch_records(status);
CREATE INDEX IF NOT EXISTS idx_dispatch_tenant ON dispatch_records(tenant_id);
CREATE INDEX IF NOT EXISTS idx_dispatch_requirement ON dispatch_records(requirement_id);
CREATE INDEX IF NOT EXISTS idx_dispatch_provider_req ON dispatch_records(provider_request_id);
CREATE INDEX IF NOT EXISTS idx_dispatch_created ON dispatch_records(created_at);
CREATE UNIQUE INDEX IF NOT EXISTS uq_dispatch_tenant_action ON dispatch_records(tenant_id, action_id);
"""

_COLUMNS = (
    "id",
    "action_id",
    "requirement_id",
    "canonical_args_hash",
    "component",
    "provider_request_id",
    "idempotency_key",
    "status",
    "response_hash",
    "attempts",
    "last_attempt_at",
    "reconciled_at",
    "reconciled_by",
    "reconciled_action",
    "created_at",
    "tenant_id",
)


def _connect(db_path: str) -> sqlite3.Connection:
    """Open a connection and make sure the schema exists."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    return conn


def _row_to_dict(row: Optional[sqlite3.Row]) -> Optional[Dict[str, Any]]:
    """Convert a dispatch_records row to a plain dict."""
    if row is None:
        return None
    return {key: row[key] for key in _COLUMNS}


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


class IdempotencyStore:
    """Store for managing dispatch records and idempotency keys.

    Provides methods to record dispatches, track provider responses, detect
    ambiguous actions, and reconcile them.

    Args:
        db_path: SQLite database path (defaults to ``personal_agent/data/idempotency.db``).
        tenant_id: Tenant UUID/text for strict multi-tenant row isolation.
    """

    def __init__(
        self,
        db_path: Optional[Union[str, Path]] = None,
        tenant_id: Optional[Union[str, uuid.UUID]] = None,
    ):
        self.db_path = str(db_path) if db_path else str(DB_PATH)
        self.tenant_id = str(tenant_id) if tenant_id else DEFAULT_TENANT_ID

    # -- context manager convenience ------------------------------------
    def __enter__(self) -> "IdempotencyStore":
        return self

    def __exit__(self, *exc_info) -> None:
        return None

    # -- dispatch lifecycle --------------------------------------------
    def record_dispatch(
        self,
        action_id: str,
        requirement_id: str,
        canonical_args_hash: str,
        component: str,
        idempotency_key: Optional[str] = None,
    ) -> str:
        """Record a dispatch attempt (must be called BEFORE the provider call).

        The action_id is the idempotency anchor: a repeat call for the same
        action_id does not create a second row, it increments ``attempts``.

        Returns:
            The dispatch record ID.
        """
        dispatch_id = str(uuid.uuid4())
        now = time.time()
        conn = _connect(self.db_path)
        try:
            existing = conn.execute(
                "SELECT tenant_id FROM dispatch_records WHERE action_id = ?",
                (action_id,),
            ).fetchone()
            if existing is not None and existing["tenant_id"] != self.tenant_id:
                raise CrossTenantConflictError(
                    f"action_id {action_id} is already recorded by tenant "
                    f"{existing['tenant_id']}; refusing cross-tenant write"
                )

            conn.execute(
                """
                INSERT INTO dispatch_records (
                    id, action_id, requirement_id, canonical_args_hash,
                    component, idempotency_key, status, attempts,
                    last_attempt_at, created_at, tenant_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
                ON CONFLICT(action_id) DO UPDATE SET
                    attempts = attempts + 1,
                    last_attempt_at = excluded.last_attempt_at,
                    status = CASE
                        WHEN status IN ('succeeded', 'reconciled') THEN status
                        ELSE 'dispatched'
                    END,
                    idempotency_key = excluded.idempotency_key
                """,
                (
                    dispatch_id,
                    action_id,
                    requirement_id,
                    canonical_args_hash,
                    component,
                    idempotency_key,
                    STATUS_DISPATCHED,
                    now,
                    now,
                    self.tenant_id,
                ),
            )
            row = conn.execute(
                "SELECT id FROM dispatch_records WHERE action_id = ?", (action_id,)
            ).fetchone()
            conn.commit()
            return row["id"] if row is not None else dispatch_id
        finally:
            conn.close()

    def record_provider_response(
        self,
        action_id: str,
        provider_request_id: str,
        response_hash: str,
        status: str,  # 'succeeded' or 'failed'
    ) -> bool:
        """Record the provider's response for a dispatch.

        Returns:
            True if a record was updated, False if not found for this tenant.
        """
        if status not in _VALID_RESPONSE_STATUSES:
            raise ValueError(f"Invalid status: {status}. Must be one of {_VALID_RESPONSE_STATUSES}")

        conn = _connect(self.db_path)
        try:
            cursor = conn.execute(
                """
                UPDATE dispatch_records
                SET provider_request_id = ?,
                    response_hash = ?,
                    status = ?,
                    last_attempt_at = ?
                WHERE action_id = ? AND tenant_id = ?
                """,
                (
                    provider_request_id or "",
                    response_hash,
                    status,
                    time.time(),
                    action_id,
                    self.tenant_id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    # -- queries --------------------------------------------------------
    def get_dispatch(self, action_id: str) -> Optional[Dict[str, Any]]:
        """Get a dispatch record by action_id (tenant-scoped).

        Returns:
            A dict of all record fields, or None if not found.
        """
        conn = _connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT * FROM dispatch_records WHERE action_id = ? AND tenant_id = ?",
                (action_id, self.tenant_id),
            ).fetchone()
            return _row_to_dict(row)
        finally:
            conn.close()

    def get_ambiguous_actions(self, older_than_minutes: int = 5) -> List[Dict[str, Any]]:
        """Find actions stuck in 'dispatched' with no provider response.

        These are candidates for reconciliation: the provider call was made but
        no definitive response was ever recorded (crash, timeout, lost reply).

        Args:
            older_than_minutes: Minimum age of the last attempt to be ambiguous.

        Returns:
            Records ordered oldest attempt first.
        """
        cutoff = time.time() - (older_than_minutes * 60)
        conn = _connect(self.db_path)
        try:
            rows = conn.execute(
                """
                SELECT * FROM dispatch_records
                WHERE tenant_id = ?
                  AND status = 'dispatched'
                  AND COALESCE(last_attempt_at, created_at) < ?
                ORDER BY COALESCE(last_attempt_at, created_at) ASC
                """,
                (self.tenant_id, cutoff),
            ).fetchall()
            return [_row_to_dict(row) for row in rows]
        finally:
            conn.close()

    def list_all(self, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
        """List all dispatch records for the tenant (admin/debug)."""
        conn = _connect(self.db_path)
        try:
            rows = conn.execute(
                """
                SELECT * FROM dispatch_records
                WHERE tenant_id = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (self.tenant_id, limit, offset),
            ).fetchall()
            return [_row_to_dict(row) for row in rows]
        finally:
            conn.close()

    def get_stats(self) -> Dict[str, int]:
        """Get dispatch record counts grouped by status for the tenant."""
        conn = _connect(self.db_path)
        try:
            rows = conn.execute(
                """
                SELECT status, COUNT(*) FROM dispatch_records
                WHERE tenant_id = ?
                GROUP BY status
                """,
                (self.tenant_id,),
            ).fetchall()
            return {row[0]: row[1] for row in rows}
        finally:
            conn.close()

    # -- reconciliation --------------------------------------------------
    def reconcile(
        self,
        action_id: str,
        action: str,  # 'succeeded' | 'failed' | 'retry' (aliases: 'mark_*')
        operator_id: Union[str, uuid.UUID],
    ) -> bool:
        """Reconcile an ambiguous dispatch record.

        Args:
            action_id: The action to reconcile.
            action: One of ``succeeded``/``failed``/``retry`` (the CLI spellings;
                ``mark_succeeded``/``mark_failed`` are accepted as aliases).
            operator_id: Operator UUID performing the reconciliation.

        Returns:
            True if reconciled, False if not found for this tenant.

        Raises:
            ValueError: if the action is unknown or the record is in a
                non-reconcilable state.
        """
        normalized = _RECONCILE_ALIASES.get(action)
        if normalized is None:
            raise ValueError(
                f"Invalid action: {action!r}. Expected one of "
                f"{sorted(set(_RECONCILE_ALIASES.keys()))}"
            )
        operator_str = str(operator_id)

        conn = _connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT status FROM dispatch_records WHERE action_id = ? AND tenant_id = ?",
                (action_id, self.tenant_id),
            ).fetchone()
            if row is None:
                return False

            current_status = row["status"]
            if current_status not in _RECONCILABLE_STATUSES:
                raise ValueError(
                    f"Cannot reconcile action with status: {current_status}"
                )

            now = time.time()
            if normalized == "retry":
                # A retry mark re-opens the dispatch (with an audit stamp) so it
                # can be re-sent and becomes ambiguous again if it stalls.
                conn.execute(
                    """
                    UPDATE dispatch_records
                    SET status = ?,
                        reconciled_at = ?,
                        reconciled_by = ?,
                        reconciled_action = ?,
                        attempts = attempts + 1,
                        last_attempt_at = ?
                    WHERE action_id = ? AND tenant_id = ?
                    """,
                    (
                        STATUS_DISPATCHED,
                        now,
                        operator_str,
                        normalized,
                        now,
                        action_id,
                        self.tenant_id,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE dispatch_records
                    SET status = ?,
                        reconciled_at = ?,
                        reconciled_by = ?,
                        reconciled_action = ?
                    WHERE action_id = ? AND tenant_id = ?
                    """,
                    (
                        STATUS_RECONCILED,
                        now,
                        operator_str,
                        normalized,
                        action_id,
                        self.tenant_id,
                    ),
                )
            conn.commit()
            return True
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------

_global_idempotency_store: Optional[IdempotencyStore] = None
_global_store_lock = threading.Lock()


def get_idempotency_store(
    db_path: Optional[Union[str, Path]] = None,
    tenant_id: Optional[Union[str, uuid.UUID]] = None,
) -> IdempotencyStore:
    """Get or create the global idempotency store singleton.

    The first caller's arguments win; later calls return the same instance.
    """
    global _global_idempotency_store
    with _global_store_lock:
        if _global_idempotency_store is None:
            _global_idempotency_store = IdempotencyStore(db_path=db_path, tenant_id=tenant_id)
        return _global_idempotency_store


# Module-level singleton for one-liner use: `from ... import global_idempotency_store`
global_idempotency_store: IdempotencyStore = get_idempotency_store()
