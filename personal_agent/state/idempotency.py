"""Idempotency Keys & Dispatch Records for GNW Governed Agent.

Provides deterministic action IDs, canonical argument serialization,
and a store for tracking provider dispatch records with reconciliation support.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Database path - uses the same data directory as memory store
DB_PATH = Path(__file__).parent.parent / "data" / "idempotency.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# Default tenant ID for single-tenant deployments
DEFAULT_TENANT_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _get_conn() -> sqlite3.Connection:
    """Get a database connection with the dispatch_records table created."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS dispatch_records (
            id TEXT PRIMARY KEY,
            action_id TEXT NOT NULL UNIQUE,
            requirement_id TEXT NOT NULL,
            canonical_args_hash TEXT NOT NULL,
            component TEXT NOT NULL,
            provider_request_id TEXT,
            idempotency_key TEXT,
            status TEXT NOT NULL,
            response_hash TEXT,
            attempts INTEGER DEFAULT 0,
            last_attempt_at TEXT,
            reconciled_at TEXT,
            reconciled_by TEXT,
            reconciled_action TEXT,
            created_at TEXT NOT NULL,
            tenant_id TEXT NOT NULL
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_dispatch_action ON dispatch_records(action_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_dispatch_status ON dispatch_records(status)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_dispatch_tenant ON dispatch_records(tenant_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_dispatch_requirement ON dispatch_records(requirement_id)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_dispatch_created ON dispatch_records(created_at)"
    )
    return conn


def _now_iso() -> str:
    """Current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def canonicalize_args(args_dict: Dict[str, Any]) -> str:
    """Canonicalize arguments to a deterministic JSON string.

    - Keys sorted lexicographically
    - No whitespace
    - Consistent number formatting
    - Ensures same args always produce same hash
    """
    return json.dumps(
        args_dict,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def generate_action_id(requirement_id: str, args_dict: Dict[str, Any]) -> str:
    """Generate a deterministic SHA256 action ID from requirement_id and args.

    The action_id is computed as:
        SHA256(requirement_id || "|" || canonical_args)

    This ensures:
    - Same requirement + same args = same action_id (idempotency)
    - Different args = different action_id
    - Requirement ID provides namespace isolation
    """
    canonical_args = canonicalize_args(args_dict)
    combined = f"{requirement_id}|{canonical_args}"
    return hashlib.sha256(combined.encode("utf-8")).hexdigest()


def generate_idempotency_key(action_id: str, attempt: int = 1) -> str:
    """Generate an idempotency key for provider calls.

    Format: {action_id}-{attempt}
    This allows retry with same action_id but different attempt number.
    """
    return f"{action_id}-{attempt}"


def hash_response(response: Any) -> str:
    """Compute SHA256 hash of provider response for audit verification."""
    if isinstance(response, (dict, list)):
        content = json.dumps(response, sort_keys=True, separators=(",", ":"))
    else:
        content = str(response)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@dataclass
class DispatchRecord:
    """Represents a dispatch record from the database."""

    id: str
    action_id: str
    requirement_id: str
    canonical_args_hash: str
    component: str
    provider_request_id: Optional[str]
    idempotency_key: Optional[str]
    status: str
    response_hash: Optional[str]
    attempts: int
    last_attempt_at: Optional[str]
    reconciled_at: Optional[str]
    reconciled_by: Optional[str]
    reconciled_action: Optional[str]
    created_at: str
    tenant_id: str

    @classmethod
    def from_row(cls, row: Tuple) -> "DispatchRecord":
        """Create DispatchRecord from database row."""
        return cls(
            id=row[0],
            action_id=row[1],
            requirement_id=row[2],
            canonical_args_hash=row[3],
            component=row[4],
            provider_request_id=row[5],
            idempotency_key=row[6],
            status=row[7],
            response_hash=row[8],
            attempts=row[9],
            last_attempt_at=row[10],
            reconciled_at=row[11],
            reconciled_by=row[12],
            reconciled_action=row[13],
            created_at=row[14],
            tenant_id=row[15],
        )


class IdempotencyStore:
    """Store for managing dispatch records and idempotency keys.

    Provides methods to record dispatches, track provider responses,
    detect ambiguous actions, and reconcile them.
    """

    def __init__(self, tenant_id: Optional[uuid.UUID] = None):
        """Initialize the store with an optional tenant ID."""
        self.tenant_id = str(tenant_id) if tenant_id else str(DEFAULT_TENANT_ID)

    def record_dispatch(
        self,
        action_id: str,
        requirement_id: str,
        canonical_args_hash: str,
        component: str,
        idempotency_key: str,
    ) -> str:
        """Record a new dispatch attempt or increment attempt counter.

        Returns the dispatch record ID.
        """
        conn = _get_conn()
        try:
            dispatch_id = str(uuid.uuid4())
            now = _now_iso()
            conn.execute(
                """
                INSERT INTO dispatch_records (
                    id, action_id, requirement_id, canonical_args_hash,
                    component, idempotency_key, status, attempts,
                    last_attempt_at, created_at, tenant_id
                ) VALUES (?, ?, ?, ?, ?, ?, 'dispatched', 1, ?, ?, ?)
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
                    now,
                    now,
                    self.tenant_id,
                ),
            )
            conn.commit()
            return dispatch_id
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

        Returns True if record was updated, False if not found.
        """
        if status not in ("succeeded", "failed"):
            raise ValueError(f"Invalid status: {status}. Must be 'succeeded' or 'failed'")

        conn = _get_conn()
        try:
            now = _now_iso()
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
                    provider_request_id,
                    response_hash,
                    status,
                    now,
                    action_id,
                    self.tenant_id,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_dispatch(self, action_id: str) -> Optional[DispatchRecord]:
        """Get a dispatch record by action_id.

        Returns None if not found.
        """
        conn = _get_conn()
        try:
            cursor = conn.execute(
                "SELECT * FROM dispatch_records WHERE action_id = ? AND tenant_id = ?",
                (action_id, self.tenant_id),
            )
            row = cursor.fetchone()
            if row:
                return DispatchRecord.from_row(row)
            return None
        finally:
            conn.close()

    def get_ambiguous_actions(self, older_than_minutes: int = 5) -> List[DispatchRecord]:
        """Find actions stuck in 'dispatched' status with no response.

        These are candidates for reconciliation - the provider call was made
        but we never received a definitive response.
        """
        cutoff = datetime.now(timezone.utc).timestamp() - (older_than_minutes * 60)
        cutoff_iso = datetime.fromtimestamp(cutoff, tz=timezone.utc).isoformat()

        conn = _get_conn()
        try:
            cursor = conn.execute(
                """
                SELECT * FROM dispatch_records
                WHERE tenant_id = ?
                  AND status = 'dispatched'
                  AND last_attempt_at < ?
                ORDER BY last_attempt_at ASC
                """,
                (self.tenant_id, cutoff_iso),
            )
            return [DispatchRecord.from_row(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def reconcile(
        self,
        action_id: str,
        action: str,  # 'mark_succeeded', 'mark_failed', 'retry'
        operator_id: uuid.UUID,
    ) -> bool:
        """Reconcile an ambiguous dispatch record.

        Args:
            action_id: The action to reconcile
            action: One of 'mark_succeeded', 'mark_failed', 'retry'
            operator_id: UUID of the operator performing reconciliation

        Returns:
            True if reconciled, False if not found or invalid state
        """
        if action not in ("mark_succeeded", "mark_failed", "retry"):
            raise ValueError(f"Invalid action: {action}")

        conn = _get_conn()
        try:
            # First check current status
            cursor = conn.execute(
                "SELECT status FROM dispatch_records WHERE action_id = ? AND tenant_id = ?",
                (action_id, self.tenant_id),
            )
            row = cursor.fetchone()
            if not row:
                return False

            current_status = row[0]
            if current_status not in ("dispatched", "ambiguous"):
                raise ValueError(f"Cannot reconcile action with status: {current_status}")

            now = _now_iso()
            operator_str = str(operator_id)

            if action == "mark_succeeded":
                conn.execute(
                    """
                    UPDATE dispatch_records
                    SET status = 'reconciled',
                        reconciled_at = ?,
                        reconciled_by = ?,
                        reconciled_action = 'mark_succeeded'
                    WHERE action_id = ? AND tenant_id = ?
                    """,
                    (now, operator_str, action_id, self.tenant_id),
                )
            elif action == "mark_failed":
                conn.execute(
                    """
                    UPDATE dispatch_records
                    SET status = 'reconciled',
                        reconciled_at = ?,
                        reconciled_by = ?,
                        reconciled_action = 'mark_failed'
                    WHERE action_id = ? AND tenant_id = ?
                    """,
                    (now, operator_str, action_id, self.tenant_id),
                )
            elif action == "retry":
                conn.execute(
                    """
                    UPDATE dispatch_records
                    SET status = 'dispatched',
                        reconciled_at = ?,
                        reconciled_by = ?,
                        reconciled_action = 'retry',
                        attempts = attempts + 1,
                        last_attempt_at = ?
                    WHERE action_id = ? AND tenant_id = ?
                    """,
                    (now, operator_str, now, action_id, self.tenant_id),
                )

            conn.commit()
            return True
        finally:
            conn.close()

    def list_all(self, limit: int = 100, offset: int = 0) -> List[DispatchRecord]:
        """List all dispatch records for the tenant (for admin/debug)."""
        conn = _get_conn()
        try:
            cursor = conn.execute(
                """
                SELECT * FROM dispatch_records
                WHERE tenant_id = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (self.tenant_id, limit, offset),
            )
            return [DispatchRecord.from_row(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_stats(self) -> Dict[str, int]:
        """Get statistics about dispatch records."""
        conn = _get_conn()
        try:
            cursor = conn.execute(
                """
                SELECT status, COUNT(*) FROM dispatch_records
                WHERE tenant_id = ?
                GROUP BY status
                """,
                (self.tenant_id,),
            )
            return {row[0]: row[1] for row in cursor.fetchall()}
        finally:
            conn.close()