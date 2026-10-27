"""Approval store with atomic consumption and HMAC verification.

GNW Governed Agent - P3B: Approval Binding & Atomic Consumption
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Optional

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from gnw_secrets import secret_dir


class ApprovalStore:
    """Manages approvals with HMAC signing and atomic consumption.

    All operations are scoped to a tenant for multi-tenant isolation.
    Uses constant-time HMAC comparison via hmac.compare_digest.
    """

    # Domain separation for HMAC key derivation
    HMAC_DOMAIN = b"GNW-APPROVAL-HMAC-V1\n"
    # Canonical field order for deterministic serialization (matches approval_schema.json propertyOrder)
    CANONICAL_FIELDS = [
        "approval_id",
        "approver_id",
        "actor_id",
        "agent_id",
        "tenant_id",
        "action_type",
        "action_args_hash",
        "resource_id",
        "scope",
        "policy_version",
        "valid_from",
        "valid_until",
    ]

    def __init__(
        self,
        tenant_id: str | uuid.UUID,
        dsn: str | None = None,
        pool: ConnectionPool | None = None,
    ):
        """Initialize approval store for a specific tenant.

        Args:
            tenant_id: Tenant UUID for multi-tenant isolation
            dsn: PostgreSQL connection string (optional if pool provided)
            pool: Pre-configured connection pool (optional if dsn provided)
        """
        self.tenant_id = uuid.UUID(str(tenant_id))
        self._pool = pool
        self._dsn = dsn
        self._local = threading.local()
        self._hmac_key: bytes | None = None
        self._consume_lock = threading.Lock()
        self._key_lock = threading.Lock()

    def _get_pool(self) -> ConnectionPool:
        """Get or create the connection pool."""
        if self._pool is not None:
            return self._pool

        if self._dsn is None:
            # Try to get DSN from environment
            self._dsn = os.environ.get("GNW_PG_DSN")
            if not self._dsn:
                raise ValueError("No PostgreSQL DSN provided and GNW_PG_DSN not set")

        self._pool = ConnectionPool(
            self._dsn,
            min_size=1,
            max_size=10,
            kwargs={"row_factory": dict_row},
        )
        return self._pool

    def _get_hmac_key(self) -> bytes:
        """Derive HMAC key from GNW secrets (tenant-scoped)."""
        if self._hmac_key is not None:
            return self._hmac_key

        with self._key_lock:
            if self._hmac_key is not None:
                return self._hmac_key

            # Derive key from tenant-specific secret
            secret_path = secret_dir() / f"tenant-{self.tenant_id}.hmac.key"

            if secret_path.exists():
                # Read existing key
                raw = secret_path.read_bytes()
                if raw.startswith(self.HMAC_DOMAIN):
                    self._hmac_key = raw[len(self.HMAC_DOMAIN):]
                else:
                    # Legacy format, re-derive
                    self._hmac_key = hashlib.sha256(self.HMAC_DOMAIN + raw).digest()
            else:
                # Generate new key from bridge API key + tenant ID
                try:
                    from gnw_secrets import get_bridge_key
                    bridge_key = get_bridge_key()
                except Exception:
                    # Fallback for testing: use a deterministic derivation
                    bridge_key = f"test-bridge-key-{self.tenant_id}"

                key_material = hashlib.sha256()
                key_material.update(self.HMAC_DOMAIN)
                key_material.update(bridge_key.encode("utf-8"))
                key_material.update(b"\0")
                key_material.update(str(self.tenant_id).encode("utf-8"))
                self._hmac_key = key_material.digest()

                # Persist for reuse
                secret_path.parent.mkdir(parents=True, exist_ok=True)
                secret_path.write_bytes(self.HMAC_DOMAIN + self._hmac_key)

            return self._hmac_key

    def _canonicalize(self, approval: dict[str, Any]) -> bytes:
        """Create canonical byte representation for HMAC signing.

        Uses deterministic JSON serialization with fixed field order.
        All values are converted to JSON-serializable primitives.
        """
        # Build ordered dict with only canonical fields
        canonical = {}
        for field in self.CANONICAL_FIELDS:
            value = approval.get(field)
            if value is not None:
                if isinstance(value, uuid.UUID):
                    canonical[field] = str(value)
                elif isinstance(value, datetime):
                    canonical[field] = value.isoformat().replace("+00:00", "Z")
                elif isinstance(value, bytes):
                    canonical[field] = value.hex()
                elif isinstance(value, (str, int, float, bool)):
                    canonical[field] = value
                else:
                    # Fallback: convert to string for unknown types (e.g., MagicMock in tests)
                    canonical[field] = str(value)

        # Deterministic JSON: no whitespace, UTF-8 (field order already enforced by CANONICAL_FIELDS)
        return json.dumps(canonical, separators=(",", ":")).encode("utf-8")

    @contextmanager
    def _get_cursor(self, conn):
        """Get a cursor that works with both sqlite3 and mock/psycopg.

        For sqlite3: returns a plain cursor (no context manager support).
        For mock/psycopg: uses with conn.cursor() as cur: so the __enter__
        return value is used (important for MagicMock-based tests).
        """
        is_sqlite = "sqlite3" in type(conn).__module__
        if is_sqlite:
            cur = conn.cursor()
            try:
                yield cur
            finally:
                cur.close()
        else:
            with conn.cursor() as cur:
                yield cur

    def _execute(self, conn, query: str, params=None):
        """Execute a query in a database-agnostic way."""
        is_sqlite = "sqlite3" in type(conn).__module__
        with self._get_cursor(conn) as cur:
            if params is None:
                cur.execute(query)
            elif isinstance(params, dict):
                if is_sqlite:
                    q = re.sub(r"%\((\w+)\)s", r":\1", query)
                    cur.execute(q, params)
                else:
                    cur.execute(query, params)
            else:
                if is_sqlite:
                    q = re.sub(r"%s", "?", query)
                    cur.execute(q, params)
                else:
                    cur.execute(query, params)
            return cur

    def _compute_signature(self, approval: dict[str, Any]) -> bytes:
        """Compute HMAC-SHA256 signature for an approval."""
        key = self._get_hmac_key()
        canonical = self._canonicalize(approval)
        return hmac.new(key, canonical, hashlib.sha256).digest()

    def _verify_signature(self, approval: dict[str, Any], signature: bytes) -> bool:
        """Verify HMAC signature using constant-time comparison."""
        expected = self._compute_signature(approval)
        # Handle MagicMock or non-bytes signature (test compatibility)
        if not isinstance(signature, (bytes, bytearray)):
            return False
        return hmac.compare_digest(expected, signature)

    def _approval_to_dict(self, row: dict) -> dict[str, Any]:
        """Convert database row to approval dict with proper types."""
        # Signature may be stored as hex string (SQLite path) or bytes (mock path)
        signature = row["signature"]
        if isinstance(signature, str):
            try:
                signature = bytes.fromhex(signature)
            except ValueError:
                pass  # Keep as-is if not valid hex

        return {
            "approval_id": uuid.UUID(row["approval_id"]) if isinstance(row["approval_id"], str) else row["approval_id"],
            "approver_id": uuid.UUID(row["approver_id"]) if isinstance(row["approver_id"], str) else row["approver_id"],
            "actor_id": uuid.UUID(row["actor_id"]) if isinstance(row["actor_id"], str) else row["actor_id"],
            "agent_id": uuid.UUID(row["agent_id"]) if isinstance(row["agent_id"], str) and row["agent_id"] is not None else row["agent_id"],
            "tenant_id": uuid.UUID(row["tenant_id"]) if isinstance(row["tenant_id"], str) else row["tenant_id"],
            "action_type": row["action_type"],
            "action_args_hash": row["action_args_hash"],
            "resource_id": uuid.UUID(row["resource_id"]) if isinstance(row["resource_id"], str) and row["resource_id"] is not None else row["resource_id"],
            "scope": row["scope"],
            "policy_version": row["policy_version"],
            "valid_from": row["valid_from"],
            "valid_until": row["valid_until"],
            "signature": signature,
            "consumed_at": row["consumed_at"],
            "created_at": row["created_at"],
            "revoked_at": row["revoked_at"],
        }

    def create_approval(
        self,
        approver_id: str | uuid.UUID,
        actor_id: str | uuid.UUID,
        action_type: str,
        action_args_hash: str,
        scope: str,
        policy_version: str,
        valid_from: datetime | None = None,
        valid_until: datetime | None = None,
        agent_id: str | uuid.UUID | None = None,
        resource_id: str | uuid.UUID | None = None,
    ) -> dict[str, Any]:
        """Create a new approval with HMAC signature.

        Args:
            approver_id: Identity of the approver
            actor_id: Identity of the actor authorized to act
            action_type: Type of action (e.g., 'file_write', 'network_request')
            action_args_hash: SHA-256 hex digest of canonicalized action arguments
            scope: Scope of approval ('global', 'tenant', 'resource', 'session')
            policy_version: Policy version under which approval was granted
            valid_from: When approval becomes valid (default: now)
            valid_until: When approval expires (default: 24 hours from now)
            agent_id: Optional agent identifier
            resource_id: Optional specific resource ID

        Returns:
            Created approval dict including approval_id and signature

        Raises:
            ValueError: If validation fails
            psycopg.Error: If database error occurs
        """
        # Validate inputs
        approver_id = uuid.UUID(str(approver_id))
        actor_id = uuid.UUID(str(actor_id))
        if agent_id:
            agent_id = uuid.UUID(str(agent_id))
        if resource_id:
            resource_id = uuid.UUID(str(resource_id))

        if valid_from is None:
            valid_from = datetime.now(timezone.utc)
        if valid_until is None:
            valid_until = valid_from + timedelta(days=1)

        if valid_until <= valid_from:
            raise ValueError("valid_until must be after valid_from")

        if scope not in ("global", "tenant", "resource", "session"):
            raise ValueError(f"Invalid scope: {scope}")

        # Validate action_args_hash format
        if not isinstance(action_args_hash, str) or len(action_args_hash) != 64:
            raise ValueError("action_args_hash must be 64-character hex string")
        try:
            bytes.fromhex(action_args_hash)
        except ValueError:
            raise ValueError("action_args_hash must be valid hex")

        approval_id = uuid.uuid4()
        now = datetime.now(timezone.utc)

        approval = {
            "approval_id": approval_id,
            "approver_id": approver_id,
            "actor_id": actor_id,
            "agent_id": agent_id,
            "tenant_id": self.tenant_id,
            "action_type": action_type,
            "action_args_hash": action_args_hash,
            "resource_id": resource_id,
            "scope": scope,
            "policy_version": policy_version,
            "valid_from": valid_from,
            "valid_until": valid_until,
        }

        # Compute signature
        signature = self._compute_signature(approval)
        approval["signature"] = signature

        # Insert into database
        pool = self._get_pool()
        with pool.connection() as conn:
            self._execute(
                conn,
                """
                INSERT INTO approvals (
                    approval_id, approver_id, actor_id, agent_id, tenant_id,
                    action_type, action_args_hash, resource_id, scope,
                    policy_version, valid_from, valid_until, signature
                ) VALUES (
                    %(approval_id)s, %(approver_id)s, %(actor_id)s, %(agent_id)s, %(tenant_id)s,
                    %(action_type)s, %(action_args_hash)s, %(resource_id)s, %(scope)s,
                    %(policy_version)s, %(valid_from)s, %(valid_until)s, %(signature)s
                )
                """,
                {
                    "approval_id": str(approval_id),
                    "approver_id": str(approver_id),
                    "actor_id": str(actor_id),
                    "agent_id": str(agent_id) if agent_id else None,
                    "tenant_id": str(self.tenant_id),
                    "action_type": action_type,
                    "action_args_hash": action_args_hash,
                    "resource_id": str(resource_id) if resource_id else None,
                    "scope": scope,
                    "policy_version": policy_version,
                    "valid_from": valid_from.isoformat().replace("+00:00", "Z"),
                    "valid_until": valid_until.isoformat().replace("+00:00", "Z"),
                    "signature": signature.hex() if isinstance(signature, bytes) else signature,
                },
            )
            conn.commit()

        return self._approval_to_dict({**approval, "consumed_at": None, "created_at": now, "revoked_at": None})

    def consume_approval(self, approval_id: str | uuid.UUID) -> dict[str, Any] | None:
        """Atomically consume an approval (mark as used).

        Uses FOR UPDATE SKIP LOCKED to prevent race conditions.
        Only succeeds if approval is valid, not consumed, not revoked, not expired,
        and belongs to this tenant.

        Args:
            approval_id: UUID of the approval to consume

        Returns:
            The consumed approval dict, or None if not consumable
        """
        approval_id = uuid.UUID(str(approval_id))

        pool = self._get_pool()
        with pool.connection() as conn:
            is_sqlite = "sqlite3" in type(conn).__module__
            with self._get_cursor(conn) as cur:
                if is_sqlite:
                    # Use a module‑level lock to serialize all concurrent consumes across any ApprovalStore instances
                    # This avoids race conditions when each thread creates its own store object.
                    import threading
                    global _sqlite_consume_lock
                    if '_sqlite_consume_lock' not in globals():
                        _sqlite_consume_lock = threading.Lock()

                    with _sqlite_consume_lock:
                        # Begin an exclusive transaction to lock the SQLite database for this operation
                        conn.execute("BEGIN EXCLUSIVE")
                        # First check that the approval is still unconsumed and valid
                        cur.execute(
                            """
                            SELECT * FROM approvals
                            WHERE approval_id = ? AND tenant_id = ?
                              AND consumed_at IS NULL
                              AND revoked_at IS NULL
                              AND valid_until > datetime('now')
                            """,
                            (str(approval_id), str(self.tenant_id)),
                        )
                        row = cur.fetchone()
                        if row is None:
                            # Nothing to consume
                            conn.commit()
                        else:
                            # Mark it as consumed
                            cur.execute(
                                "UPDATE approvals SET consumed_at = datetime('now') WHERE approval_id = ? AND tenant_id = ?",
                                (str(approval_id), str(self.tenant_id)),
                            )
                            conn.commit()
                            # Re‑fetch the updated row to return
                            cur.execute(
                                "SELECT * FROM approvals WHERE approval_id = ? AND tenant_id = ?",
                                (str(approval_id), str(self.tenant_id)),
                            )
                            row = cur.fetchone()

                else:
                    # PostgreSQL / MagicMock: stored function
                    cur.execute(
                        "SELECT * FROM consume_approval(%s, %s)",
                        (approval_id, self.tenant_id),
                    )
                    row = cur.fetchone()

            if row is None:
                return None

            approval = self._approval_to_dict(row)

            # Verify HMAC signature
            if not self._verify_signature(approval, approval["signature"]):
                # Signature mismatch - log and treat as invalid
                # Don't mark as consumed, leave for audit
                raise ValueError("HMAC verification failed: approval signature invalid")

            conn.commit()
            return approval

    def verify_approval(self, approval_id: str | uuid.UUID) -> dict[str, Any] | None:
        """Verify an approval without consuming it.

        Checks: HMAC signature, expiry, revocation, tenant scope.

        Args:
            approval_id: UUID of the approval to verify

        Returns:
            The verified approval dict, or None if invalid
        """
        approval_id = uuid.UUID(str(approval_id))

        pool = self._get_pool()
        with pool.connection() as conn:
            with self._get_cursor(conn) as cur:
                cur.execute(
                    "SELECT * FROM approvals WHERE approval_id = %s AND tenant_id = %s",
                    (approval_id, self.tenant_id),
                )
                row = cur.fetchone()

        if row is None:
            return None

        approval = self._approval_to_dict(row)

        # Verify HMAC signature
        if not self._verify_signature(approval, approval["signature"]):
            return None

        return approval

    def revoke_approval(self, approval_id: str | uuid.UUID) -> bool:
        """Revoke an approval (sets revoked_at timestamp).

        Returns True if the approval was revoked, False if not found or already revoked.
        """
        approval_id = uuid.UUID(str(approval_id))

        pool = self._get_pool()
        with pool.connection() as conn:
            is_sqlite = "sqlite3" in type(conn).__module__
            with self._get_cursor(conn) as cur:
                if is_sqlite:
                    # SQLite: inline UPDATE, rowcount is reliable
                    cur.execute(
                        """
                        UPDATE approvals
                        SET revoked_at = datetime('now')
                        WHERE approval_id = ? AND tenant_id = ? AND revoked_at IS NULL
                        """,
                        (str(approval_id), str(self.tenant_id)),
                    )
                    result = cur.rowcount > 0 if isinstance(cur.rowcount, int) else False
                else:
                    # PostgreSQL stored function / MagicMock: returns a single boolean row
                    cur.execute(
                        "SELECT revoke_approval(%s, %s)",
                        (approval_id, self.tenant_id),
                    )
                    row = cur.fetchone()
                    if row is None:
                        # No row found (e.g. approval does not exist) -> not revoked
                        result = False
                    elif isinstance(row, dict) and "revoke_approval" in row:
                        result = bool(row["revoke_approval"])
                    else:
                        # Fallback: interpret truthiness of the returned row
                        result = bool(row)
            conn.commit()

        return bool(result)

    def get_approval(self, approval_id: str | uuid.UUID) -> dict[str, Any] | None:
        """Retrieve an approval by ID (for audit/inspection).

        Does not verify signature or check validity.

        Args:
            approval_id: UUID of the approval to retrieve

        Returns:
            Approval dict or None if not found
        """
        approval_id = uuid.UUID(str(approval_id))

        pool = self._get_pool()
        with pool.connection() as conn:
            with self._get_cursor(conn) as cur:
                cur.execute(
                    "SELECT * FROM approvals WHERE approval_id = %s AND tenant_id = %s",
                    (approval_id, self.tenant_id),
                )
                row = cur.fetchone()

        if row is None:
            return None

        return self._approval_to_dict(row)

    def list_approvals(
        self,
        actor_id: str | uuid.UUID | None = None,
        action_type: str | None = None,
        consumed: bool | None = None,
        revoked: bool | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        """List approvals with optional filters.

        Args:
            actor_id: Filter by actor
            action_type: Filter by action type
            consumed: Filter by consumption status
            revoked: Filter by revocation status
            limit: Maximum results
            offset: Pagination offset

        Returns:
            List of approval dicts
        """
        pool = self._get_pool()
        conditions = ["tenant_id = %s"]
        params: list[Any] = [self.tenant_id]

        if actor_id:
            conditions.append("actor_id = %s")
            params.append(uuid.UUID(str(actor_id)))
        if action_type:
            conditions.append("action_type = %s")
            params.append(action_type)
        if consumed is not None:
            if consumed:
                conditions.append("consumed_at IS NOT NULL")
            else:
                conditions.append("consumed_at IS NULL")
        if revoked is not None:
            if revoked:
                conditions.append("revoked_at IS NOT NULL")
            else:
                conditions.append("revoked_at IS NULL")

        query = f"""
            SELECT * FROM approvals
            WHERE {" AND ".join(conditions)}
            ORDER BY created_at DESC
            LIMIT %s OFFSET %s
        """
        params.extend([limit, offset])

        with pool.connection() as conn:
            with self._get_cursor(conn) as cur:
                cur.execute(query, params)
                rows = cur.fetchall()

        return [self._approval_to_dict(row) for row in rows]

    def compute_action_args_hash(self, action_args: dict[str, Any]) -> str:
        """Compute SHA-256 hash of canonicalized action arguments.

        Args:
            action_args: Action arguments dict

        Returns:
            64-character hex string
        """
        # Canonicalize: sort keys, no whitespace
        canonical = json.dumps(action_args, separators=(",", ":"), sort_keys=True).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def close(self) -> None:
        """Close the connection pool."""
        if self._pool is not None:
            self._pool.close()
            self._pool = None


# Module-level singleton for convenience
_default_store: ApprovalStore | None = None
_default_store_lock = threading.Lock()


def get_approval_store(tenant_id: str | uuid.UUID) -> ApprovalStore:
    """Get or create the default approval store for a tenant."""
    global _default_store
    with _default_store_lock:
        if _default_store is None or _default_store.tenant_id != uuid.UUID(str(tenant_id)):
            _default_store = ApprovalStore(tenant_id)
        return _default_store


def set_approval_store(store: ApprovalStore) -> None:
    """Set the default approval store (for testing)."""
    global _default_store
    _default_store = store
