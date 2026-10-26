"""KPI Collector — Daily GNW governance metrics.

GNW Governed Agent - P3F: Mission Proof System & KPI Automation

Computes and stores daily KPI snapshots per GNW_STATE.json verification section.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from gnw_secrets import secret_dir


class KPICollector:
    """Collects and stores daily KPI snapshots for governance metrics.

    All metrics are scoped to tenant_id and stored in kpi_snapshots table (append-only).
    """

    # Default thresholds (can be overridden per-tenant via configuration)
    DEFAULT_THRESHOLDS = {
        "authorization_enforcement": 0.99,
        "approval_integrity": 0.99,
        "evidence_completeness": 0.95,
        "reconciliation_backlog": 0.05,  # max 5% ambiguous
        "supervisor_availability": 0.95,
        "router_success_rate": 0.95,
    }

    def __init__(
        self,
        tenant_id: str | uuid.UUID,
        dsn: str | None = None,
        pool: ConnectionPool | None = None,
        thresholds: dict[str, float] | None = None,
    ):
        """Initialize KPI collector for a specific tenant.

        Args:
            tenant_id: Tenant UUID for multi-tenant isolation
            dsn: PostgreSQL connection string (optional if pool provided)
            pool: Pre-configured connection pool (optional if dsn provided)
            thresholds: Optional custom thresholds (merges with defaults)
        """
        self.tenant_id = uuid.UUID(str(tenant_id))
        self._pool = pool
        self._dsn = dsn
        self._local = __import__("threading").local()

        self.thresholds = {**self.DEFAULT_THRESHOLDS, **(thresholds or {})}

    def _get_pool(self) -> ConnectionPool:
        """Get or create the connection pool."""
        if self._pool is not None:
            return self._pool

        if self._dsn is None:
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

    def _insert_snapshot(
        self,
        metric_name: str,
        metric_value: float,
        target_value: float | None = None,
        threshold: float | None = None,
        labels: dict[str, Any] | None = None,
    ) -> None:
        """Insert a KPI snapshot (append-only)."""
        pool = self._get_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO kpi_snapshots (tenant_id, metric_name, metric_value, target_value, threshold, labels)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        self.tenant_id,
                        metric_name,
                        metric_value,
                        target_value,
                        threshold,
                        json.dumps(labels) if labels else None,
                    ),
                )
                conn.commit()

    def _get_threshold(self, metric_name: str) -> float | None:
        """Get threshold for a metric."""
        return self.thresholds.get(metric_name)

    def _query_scalar(self, query: str, params: tuple = ()) -> float | int | None:
        """Execute a query returning a single scalar value."""
        pool = self._get_pool()
        with pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(query, params)
                row = cur.fetchone()
                return row[0] if row else None

    def collect_authorization_enforcement(self) -> float:
        """authorization_enforcement = authorized_protected_actions / total_protected_actions

        Measures the fraction of protected actions that had valid authorization.
        """
        # Total protected actions attempted (from audit log or approvals)
        total_query = """
            SELECT COUNT(*) FROM approvals
            WHERE tenant_id = %s
              AND created_at >= NOW() - INTERVAL '24 hours'
        """
        total = self._query_scalar(total_query, (self.tenant_id,)) or 0

        if total == 0:
            return 1.0  # No protected actions = perfect enforcement

        # Authorized actions (approvals that were consumed/verified successfully)
        authorized_query = """
            SELECT COUNT(*) FROM approvals
            WHERE tenant_id = %s
              AND created_at >= NOW() - INTERVAL '24 hours'
              AND consumed_at IS NOT NULL
              AND revoked_at IS NULL
              AND valid_until > NOW()
        """
        authorized = self._query_scalar(authorized_query, (self.tenant_id,)) or 0

        return authorized / total

    def collect_approval_integrity(self) -> float:
        """approval_integrity = approval_bound_successful / approval_required_actions

        Measures the fraction of actions requiring approval that were bound to valid approvals.
        """
        # Actions that required approval (from audit log - placeholder for now)
        # In practice, this would come from an action_audit table
        required_query = """
            SELECT COUNT(*) FROM approvals
            WHERE tenant_id = %s
              AND created_at >= NOW() - INTERVAL '24 hours'
        """
        required = self._query_scalar(required_query, (self.tenant_id,)) or 0

        if required == 0:
            return 1.0

        # Actions successfully bound to valid approvals
        bound_query = """
            SELECT COUNT(*) FROM approvals
            WHERE tenant_id = %s
              AND created_at >= NOW() - INTERVAL '24 hours'
              AND consumed_at IS NOT NULL
              AND revoked_at IS NULL
              AND valid_until > NOW()
        """
        bound = self._query_scalar(bound_query, (self.tenant_id,)) or 0

        return bound / required

    def collect_evidence_completeness(self) -> float:
        """evidence_completeness = actions_with_complete_proof / total_actions_requiring_proof

        Measures the fraction of actions requiring proof that have complete evidence.
        """
        # For now, use missions table as proxy
        # Actions requiring proof = missions in ACTIVE or COMPLETED status
        total_query = """
            SELECT COUNT(*) FROM missions
            WHERE tenant_id = %s
              AND status IN ('ACTIVE', 'COMPLETED')
              AND created_at >= NOW() - INTERVAL '24 hours'
        """
        total = self._query_scalar(total_query, (self.tenant_id,)) or 0

        if total == 0:
            return 1.0

        # Actions with complete proof = missions with non-null proof_bundle and verification_hash
        complete_query = """
            SELECT COUNT(*) FROM missions
            WHERE tenant_id = %s
              AND status IN ('ACTIVE', 'COMPLETED')
              AND created_at >= NOW() - INTERVAL '24 hours'
              AND proof_bundle IS NOT NULL
              AND proof_bundle->>'verification_hash' IS NOT NULL
        """
        complete = self._query_scalar(complete_query, (self.tenant_id,)) or 0

        return complete / total

    def collect_reconciliation_backlog(self) -> float:
        """reconciliation_backlog = ambiguous_actions / total_actions

        Measures the fraction of actions in ambiguous/uncertain state.
        """
        # Total actions in last 24h
        total_query = """
            SELECT COUNT(*) FROM approvals
            WHERE tenant_id = %s
              AND created_at >= NOW() - INTERVAL '24 hours'
        """
        total = self._query_scalar(total_query, (self.tenant_id,)) or 0

        if total == 0:
            return 0.0

        # Ambiguous actions: not consumed, not revoked, but expired or near-expiry
        ambiguous_query = """
            SELECT COUNT(*) FROM approvals
            WHERE tenant_id = %s
              AND created_at >= NOW() - INTERVAL '24 hours'
              AND consumed_at IS NULL
              AND revoked_at IS NULL
              AND valid_until <= NOW() + INTERVAL '1 hour'
        """
        ambiguous = self._query_scalar(ambiguous_query, (self.tenant_id,)) or 0

        return ambiguous / total

    def collect_supervisor_availability(self) -> float:
        """supervisor_availability = healthy_checks / total_checks (last 24h)

        Measures the fraction of supervisor health checks that passed.
        """
        # This would typically come from a supervisor_health_checks table
        # For now, simulate with a placeholder - in production, query actual health check logs
        # We can check the supervisor state from the bridge supervisor module

        try:
            # Try to import and check supervisor status
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from personal_agent.bridge.supervisor import global_bridge_supervisor

            status = global_bridge_supervisor.status()
            is_healthy = status.get("state") == "HEALTHY"

            # For daily metric, we'd aggregate over 24h of checks
            # Here we return a point-in-time approximation
            return 1.0 if is_healthy else 0.0

        except Exception:
            # If supervisor not available, return 0
            return 0.0

    def collect_router_success_rate(self) -> float:
        """router_success_rate = successful_routes / total_routes (last 24h)

        Measures the fraction of model routing attempts that succeeded.
        """
        # This would come from router metrics / audit logs
        # Placeholder: query from a router_metrics table if it exists
        # For now, return a reasonable default based on model health registry

        try:
            import sys
            sys.path.insert(0, str(Path(__file__).parent.parent.parent))
            from personal_agent.health.model_health import global_health_registry, HealthState

            records = list(global_health_registry.records.values())
            if not records:
                return 0.0

            healthy = sum(1 for r in records if r.health_state == HealthState.HEALTHY)
            total = len(records)

            return healthy / total if total > 0 else 0.0

        except Exception:
            return 0.0

    def collect_all(self) -> dict[str, float]:
        """Collect all KPI metrics and store snapshots.

        Returns:
            Dict of metric_name -> metric_value
        """
        results = {}

        # Collect each metric
        metrics = {
            "authorization_enforcement": self.collect_authorization_enforcement,
            "approval_integrity": self.collect_approval_integrity,
            "evidence_completeness": self.collect_evidence_completeness,
            "reconciliation_backlog": self.collect_reconciliation_backlog,
            "supervisor_availability": self.collect_supervisor_availability,
            "router_success_rate": self.collect_router_success_rate,
        }

        for name, collector_fn in metrics.items():
            try:
                value = collector_fn()
                results[name] = value

                threshold = self._get_threshold(name)
                target = 1.0 if name != "reconciliation_backlog" else 0.0

                labels = {"collection_method": "automated", "window": "24h"}
                self._insert_snapshot(name, value, target, threshold, labels)

            except Exception as e:
                # Log error but continue with other metrics
                error_labels = {"collection_method": "automated", "window": "24h", "error": str(e)}
                self._insert_snapshot(name, 0.0, None, None, error_labels)
                results[name] = 0.0

        return results

    def check_alerts(self, metrics: dict[str, float]) -> list[dict[str, Any]]:
        """Check if any KPI breaches its threshold.

        Args:
            metrics: Dict of metric_name -> metric_value from collect_all()

        Returns:
            List of alert dicts for breached metrics
        """
        alerts = []

        for name, value in metrics.items():
            threshold = self._get_threshold(name)
            if threshold is None:
                continue

            # For reconciliation_backlog, breach is when value > threshold
            # For others, breach is when value < threshold
            if name == "reconciliation_backlog":
                breached = value > threshold
            else:
                breached = value < threshold

            if breached:
                alerts.append({
                    "metric_name": name,
                    "metric_value": value,
                    "threshold": threshold,
                    "breach_type": "above" if name == "reconciliation_backlog" else "below",
                    "tenant_id": str(self.tenant_id),
                    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                })

        return alerts

    def close(self) -> None:
        """Close the connection pool."""
        if self._pool is not None:
            self._pool.close()
            self._pool = None


def run_daily_collection(tenant_id: str | uuid.UUID, dsn: str | None = None) -> dict[str, Any]:
    """Convenience function to run daily KPI collection.

    Args:
        tenant_id: Tenant UUID
        dsn: Optional PostgreSQL DSN

    Returns:
        Dict with metrics and alerts
    """
    collector = KPICollector(tenant_id, dsn=dsn)
    try:
        metrics = collector.collect_all()
        alerts = collector.check_alerts(metrics)
        return {"metrics": metrics, "alerts": alerts}
    finally:
        collector.close()