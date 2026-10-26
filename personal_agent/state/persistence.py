"""Execution State Machine Persistence for GNW.

Provides SQLite/PostgreSQL-backed persistence for supervisor and router state machines,
enabling crash survival and complete audit trails.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Try to import PostgreSQL support
try:
    import psycopg
    import psycopg.rows
    PSYCOPG_AVAILABLE = True
except ImportError:
    PSYCOPG_AVAILABLE = False

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
DB_PATH = Path(__file__).parent.parent / "data" / "state_machine.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# PostgreSQL connection string from environment
POSTGRES_DSN = os.getenv("GNW_STATE_DB_DSN")  # e.g., "postgresql://user:pass@host:5432/db?sslmode=verify-full"

# Tenant ID for multi-tenancy (default to a fixed UUID for single-tenant deployments)
DEFAULT_TENANT_ID = uuid.UUID(os.getenv("GNW_TENANT_ID", "00000000-0000-0000-0000-000000000001"))

# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------
@dataclass
class ExecutionState:
    """Current state of a component."""
    execution_id: uuid.UUID
    component: str
    state: str
    prev_state: Optional[str]
    transition_reason: Optional[str]
    metadata: Dict[str, Any]
    created_at: float  # Unix timestamp


@dataclass
class StateTransition:
    """Single state transition record (append-only audit trail)."""
    id: uuid.UUID
    execution_id: uuid.UUID
    from_state: str
    to_state: str
    trigger: str
    actor: Optional[str]
    timestamp: float  # Unix timestamp
    metadata: Dict[str, Any]


# ---------------------------------------------------------------------------
# Connection Management
# ---------------------------------------------------------------------------
def _get_sqlite_conn() -> sqlite3.Connection:
    """Get a new SQLite connection (not thread-local to avoid locking issues)."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.row_factory = sqlite3.Row
    return conn


def _get_pg_conn():
    """Get a new PostgreSQL connection."""
    if not PSYCOPG_AVAILABLE:
        raise RuntimeError("psycopg not installed; cannot use PostgreSQL backend")
    return psycopg.connect(POSTGRES_DSN, autocommit=False, row_factory=psycopg.rows.dict_row)


@contextmanager
def _sqlite_transaction():
    """Context manager for SQLite transactions."""
    conn = _get_sqlite_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


@contextmanager
def _pg_transaction():
    """Context manager for PostgreSQL transactions."""
    conn = _get_pg_conn()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _transaction():
    """Get the appropriate transaction context manager."""
    use_pg = POSTGRES_DSN is not None and PSYCOPG_AVAILABLE
    if use_pg:
        return _pg_transaction()
    else:
        return _sqlite_transaction()


# ---------------------------------------------------------------------------
# Schema Initialization
# ---------------------------------------------------------------------------
_SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS execution_states (
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    component TEXT NOT NULL,
    state TEXT NOT NULL,
    prev_state TEXT,
    transition_reason TEXT,
    metadata TEXT,  -- JSON
    created_at REAL NOT NULL,
    tenant_id TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS state_transitions (
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    from_state TEXT NOT NULL,
    to_state TEXT NOT NULL,
    trigger TEXT NOT NULL,
    actor TEXT,
    timestamp REAL NOT NULL,
    metadata TEXT,  -- JSON
    tenant_id TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_executions_component ON execution_states(component);
CREATE INDEX IF NOT EXISTS idx_executions_tenant ON execution_states(tenant_id);
CREATE INDEX IF NOT EXISTS idx_executions_execution_id ON execution_states(execution_id);
CREATE INDEX IF NOT EXISTS idx_transitions_execution ON state_transitions(execution_id);
CREATE INDEX IF NOT EXISTS idx_transitions_tenant ON state_transitions(tenant_id);
CREATE INDEX IF NOT EXISTS idx_transitions_timestamp ON state_transitions(timestamp);

-- Enforce uniqueness of (execution_id, component, tenant_id) for current state tracking
CREATE UNIQUE INDEX IF NOT EXISTS uq_execution_component_tenant
    ON execution_states(execution_id, component, tenant_id);
"""


def initialize_schema() -> None:
    """Create tables if they don't exist (SQLite only; PostgreSQL uses migrations)."""
    if POSTGRES_DSN and PSYCOPG_AVAILABLE:
        # PostgreSQL schema managed by migration files
        return
    with _sqlite_transaction() as conn:
        conn.executescript(_SQLITE_SCHEMA)


# ---------------------------------------------------------------------------
# ExecutionStateStore
# ---------------------------------------------------------------------------
class ExecutionStateStore:
    """Persistent state store for supervisor and router state machines.

    Provides:
    - record_transition(): Atomically record a state change with row locking
    - get_current_state(): Latest state per component
    - get_execution_history(): Full transition chain for an execution_id
    - recover_on_startup(): Restore supervisor/router state from DB
    """

    def __init__(self, tenant_id: Optional[uuid.UUID] = None):
        self.tenant_id = tenant_id or DEFAULT_TENANT_ID
        self._use_pg = POSTGRES_DSN is not None and PSYCOPG_AVAILABLE
        if not self._use_pg:
            initialize_schema()

    # -------------------------------------------------------------------
    # Core Persistence Methods
    # -------------------------------------------------------------------
    def record_transition(
        self,
        execution_id: uuid.UUID,
        component: str,
        from_state: str,
        to_state: str,
        trigger: str,
        actor: Optional[str],
        metadata: Optional[Dict[str, Any]] = None,
    ) -> uuid.UUID:
        """Atomically record a state transition with row-level locking.

        Args:
            execution_id: Logical action ID (groups related transitions)
            component: 'supervisor', 'router', or 'bridge'
            from_state: Previous state
            to_state: New state
            trigger: 'health_check', 'auth_check', 'restart', 'manual', etc.
            actor: 'supervisor', 'router', 'admin', etc.
            metadata: Additional JSON-serializable context

        Returns:
            The transition ID (UUID)
        """
        metadata = metadata or {}
        transition_id = uuid.uuid4()
        now = time.time()
        metadata_json = json.dumps(metadata, ensure_ascii=False)

        if self._use_pg:
            return self._record_transition_pg(
                execution_id, component, from_state, to_state,
                trigger, actor, metadata_json, now, transition_id
            )
        else:
            return self._record_transition_sqlite(
                execution_id, component, from_state, to_state,
                trigger, actor, metadata_json, now, transition_id
            )

    def _record_transition_sqlite(
        self,
        execution_id: uuid.UUID,
        component: str,
        from_state: str,
        to_state: str,
        trigger: str,
        actor: Optional[str],
        metadata_json: str,
        now: float,
        transition_id: uuid.UUID,
    ) -> uuid.UUID:
        """SQLite implementation with row locking via IMMEDIATE transaction."""
        # Use a dedicated connection for this transaction to ensure proper locking
        conn = _get_sqlite_conn()
        try:
            # Use IMMEDIATE transaction to acquire write lock early
            conn.execute("BEGIN IMMEDIATE")
            
            # Lock the execution_states row (SELECT FOR UPDATE equivalent in SQLite)
            conn.execute(
                "SELECT 1 FROM execution_states WHERE execution_id = ? AND component = ? AND tenant_id = ?",
                (str(execution_id), component, str(self.tenant_id)),
            )

            # Upsert execution_states
            conn.execute(
                """
                INSERT INTO execution_states (id, execution_id, component, state, prev_state, transition_reason, metadata, created_at, tenant_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(execution_id, component, tenant_id) DO UPDATE SET
                    state = excluded.state,
                    prev_state = excluded.prev_state,
                    transition_reason = excluded.transition_reason,
                    metadata = excluded.metadata,
                    created_at = excluded.created_at
                """,
                (
                    str(uuid.uuid4()), str(execution_id), component, to_state, from_state,
                    trigger, metadata_json, now, str(self.tenant_id)
                ),
            )

            # Append-only insert into state_transitions
            conn.execute(
                """
                INSERT INTO state_transitions (id, execution_id, from_state, to_state, trigger, actor, timestamp, metadata, tenant_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(transition_id), str(execution_id), from_state, to_state,
                    trigger, actor, now, metadata_json, str(self.tenant_id)
                ),
            )

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
        return transition_id

    def _record_transition_pg(
        self,
        execution_id: uuid.UUID,
        component: str,
        from_state: str,
        to_state: str,
        trigger: str,
        actor: Optional[str],
        metadata_json: str,
        now: float,
        transition_id: uuid.UUID,
    ) -> uuid.UUID:
        """PostgreSQL implementation using the record_state_transition function."""
        with _pg_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT record_state_transition(%s, %s, %s, %s, %s, %s, %s, %s::jsonb)",
                    (
                        str(execution_id), component, from_state, to_state,
                        trigger, actor, str(self.tenant_id), metadata_json
                    ),
                )
                result = cur.fetchone()
                # The function returns the transition_id
                return uuid.UUID(result[0]) if result else transition_id

    def get_current_state(self, component: str) -> Optional[ExecutionState]:
        """Get the latest state for a component.

        Args:
            component: 'supervisor', 'router', or 'bridge'

        Returns:
            ExecutionState or None if no state recorded
        """
        if self._use_pg:
            return self._get_current_state_pg(component)
        else:
            return self._get_current_state_sqlite(component)

    def _get_current_state_sqlite(self, component: str) -> Optional[ExecutionState]:
        conn = _get_sqlite_conn()
        try:
            row = conn.execute(
                """
                SELECT execution_id, component, state, prev_state, transition_reason, metadata, created_at
                FROM execution_states
                WHERE component = ? AND tenant_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (component, str(self.tenant_id)),
            ).fetchone()

            if not row:
                return None

            return ExecutionState(
                execution_id=uuid.UUID(row["execution_id"]),
                component=row["component"],
                state=row["state"],
                prev_state=row["prev_state"],
                transition_reason=row["transition_reason"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                created_at=row["created_at"],
            )
        finally:
            conn.close()

    def _get_current_state_pg(self, component: str) -> Optional[ExecutionState]:
        with _pg_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM get_current_state(%s, %s)",
                    (component, str(self.tenant_id)),
                )
                row = cur.fetchone()
                if not row:
                    return None
                return ExecutionState(
                    execution_id=uuid.UUID(row["execution_id"]),
                    component=row["component"],
                    state=row["state"],
                    prev_state=row["prev_state"],
                    transition_reason=row["transition_reason"],
                    metadata=row["metadata"] if isinstance(row["metadata"], dict) else json.loads(row["metadata"]),
                    created_at=row["created_at"].timestamp(),
                )

    def get_execution_history(self, execution_id: uuid.UUID) -> List[StateTransition]:
        """Get full transition chain for an execution_id (audit trail).

        Args:
            execution_id: Logical action ID

        Returns:
            List of StateTransition ordered by timestamp ascending
        """
        if self._use_pg:
            return self._get_execution_history_pg(execution_id)
        else:
            return self._get_execution_history_sqlite(execution_id)

    def _get_execution_history_sqlite(self, execution_id: uuid.UUID) -> List[StateTransition]:
        conn = _get_sqlite_conn()
        try:
            rows = conn.execute(
                """
                SELECT id, execution_id, from_state, to_state, trigger, actor, timestamp, metadata
                FROM state_transitions
                WHERE execution_id = ? AND tenant_id = ?
                ORDER BY timestamp ASC
                """,
                (str(execution_id), str(self.tenant_id)),
            ).fetchall()

            return [
                StateTransition(
                    id=uuid.UUID(row["id"]),
                    execution_id=uuid.UUID(row["execution_id"]),
                    from_state=row["from_state"],
                    to_state=row["to_state"],
                    trigger=row["trigger"],
                    actor=row["actor"],
                    timestamp=row["timestamp"],
                    metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                )
                for row in rows
            ]
        finally:
            conn.close()

    def _get_execution_history_pg(self, execution_id: uuid.UUID) -> List[StateTransition]:
        with _pg_transaction() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT * FROM get_execution_history(%s, %s)",
                    (str(execution_id), str(self.tenant_id)),
                )
                rows = cur.fetchall()
                return [
                    StateTransition(
                        id=uuid.UUID(row["id"]),
                        execution_id=uuid.UUID(row["execution_id"]),
                        from_state=row["from_state"],
                        to_state=row["to_state"],
                        trigger=row["trigger"],
                        actor=row["actor"],
                        timestamp=row["timestamp"].timestamp(),
                        metadata=row["metadata"] if isinstance(row["metadata"], dict) else json.loads(row["metadata"]),
                    )
                    for row in rows
                ]

    def recover_on_startup(self, component: str) -> Optional[ExecutionState]:
        """Restore component state from database on startup.

        Args:
            component: 'supervisor', 'router', or 'bridge'

        Returns:
            Latest ExecutionState or None if no prior state
        """
        # For recovery, we just need the current state
        return self.get_current_state(component)

    # -------------------------------------------------------------------
    # Convenience Methods for Supervisor
    # -------------------------------------------------------------------
    def get_supervisor_state(self) -> Optional[ExecutionState]:
        """Get current supervisor state."""
        return self.get_current_state("supervisor")

    def get_router_state(self) -> Optional[ExecutionState]:
        """Get current router state."""
        return self.get_current_state("router")

    def get_bridge_state(self) -> Optional[ExecutionState]:
        """Get current bridge state."""
        return self.get_current_state("bridge")

    # -------------------------------------------------------------------
    # Router-specific: Circuit Breaker Persistence
    # -------------------------------------------------------------------
    def record_circuit_breaker_change(
        self,
        model_id: str,
        from_state: str,
        to_state: str,
        trigger: str = "circuit_breaker",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> uuid.UUID:
        """Record a circuit breaker state change for a model.

        Uses a synthetic execution_id based on model_id for grouping.
        """
        # Create deterministic execution_id from model_id for grouping
        execution_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"circuit-breaker:{model_id}")
        metadata = metadata or {}
        metadata["model_id"] = model_id
        return self.record_transition(
            execution_id=execution_id,
            component="router",
            from_state=from_state,
            to_state=to_state,
            trigger=trigger,
            actor="router",
            metadata=metadata,
        )

    def record_model_metrics(self, model_id: str, metrics: Dict[str, Any]) -> uuid.UUID:
        """Record model metrics snapshot (for periodic persistence)."""
        execution_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"metrics:{model_id}")
        metadata = {"model_id": model_id, **metrics}
        return self.record_transition(
            execution_id=execution_id,
            component="router",
            from_state="metrics_snapshot",
            to_state="metrics_snapshot",
            trigger="periodic_metrics",
            actor="router",
            metadata=metadata,
        )

    # -------------------------------------------------------------------
    # Supervisor-specific: State Recovery
    # -------------------------------------------------------------------
    def restore_supervisor_state(self) -> Tuple[Optional[str], int, int]:
        """Restore supervisor's _state, _failures, _restart_count from DB.

        Returns:
            Tuple of (state, failures, restart_count) or (None, 0, 0) if no prior state
        """
        state = self.get_supervisor_state()
        if not state:
            return None, 0, 0

        metadata = state.metadata
        failures = metadata.get("failures", 0)
        restart_count = metadata.get("restart_count", 0)

        return state.state, failures, restart_count

    def save_supervisor_state(self, state: str, failures: int, restart_count: int, execution_id: uuid.UUID) -> uuid.UUID:
        """Save supervisor state with metadata."""
        metadata = {"failures": failures, "restart_count": restart_count}
        return self.record_transition(
            execution_id=execution_id,
            component="supervisor",
            from_state=metadata.get("prev_state", "UNKNOWN"),
            to_state=state,
            trigger="state_change",
            actor="supervisor",
            metadata=metadata,
        )


# ---------------------------------------------------------------------------
# Global singleton
# ---------------------------------------------------------------------------
_global_state_store: Optional[ExecutionStateStore] = None
_global_store_lock = __import__("threading").Lock()


def get_state_store(tenant_id: Optional[uuid.UUID] = None) -> ExecutionStateStore:
    """Get or create the global state store singleton."""
    global _global_state_store
    with _global_store_lock:
        if _global_state_store is None:
            _global_state_store = ExecutionStateStore(tenant_id)
        return _global_state_store