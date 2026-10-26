"""Mission/KPI Dashboard — Simple FastAPI endpoint for metrics.

GNW Governed Agent - P3F: Mission Proof System & KPI Automation

Optional: Provides GET /metrics/kpis endpoint returning current KPI values with trends.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from gnw_secrets import secret_dir

app = FastAPI(title="GNW Mission & KPI Dashboard", version="1.0.0")


class KPISnapshotResponse(BaseModel):
    metric_name: str
    metric_value: float
    target_value: float | None
    threshold: float | None
    measured_at: str
    labels: dict[str, Any] | None
    trend: str
    status: str


class MissionResponse(BaseModel):
    mission_id: str
    name: str
    description: str | None
    owner_id: str
    tenant_id: str
    status: str
    proof_bundle: dict[str, Any] | None
    started_at: str | None
    completed_at: str | None
    created_at: str


class PoolManager:
    """Manages connection pool for the dashboard."""

    def __init__(self):
        self._pool: ConnectionPool | None = None
        self._dsn: str | None = None

    def get_pool(self) -> ConnectionPool:
        if self._pool is not None:
            return self._pool

        self._dsn = os.environ.get("GNW_PG_DSN")
        if not self._dsn:
            raise ValueError("GNW_PG_DSN environment variable not set")

        self._pool = ConnectionPool(
            self._dsn,
            min_size=1,
            max_size=10,
            kwargs={"row_factory": dict_row},
        )
        return self._pool

    def close(self):
        if self._pool is not None:
            self._pool.close()
            self._pool = None


pool_manager = PoolManager()


@app.on_event("shutdown")
def shutdown_event():
    pool_manager.close()


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "gnw-mission-dashboard"}


@app.get("/metrics/kpis", response_model=list[KPISnapshotResponse])
async def get_kpis(
    tenant_id: str = Query(..., description="Tenant UUID"),
    metric_names: list[str] | None = Query(None, description="Optional list of metric names to filter"),
    limit: int = Query(30, ge=1, le=100, description="Number of historical points per metric"),
):
    """Get current KPI values with trends for a tenant.

    Returns latest value for each metric plus trend direction and status.
    """
    pool = pool_manager.get_pool()
    tenant_uuid = uuid.UUID(tenant_id)

    # Build query
    conditions = ["tenant_id = %s"]
    params: list[Any] = [tenant_uuid]

    if metric_names:
        placeholders = ",".join(["%s"] * len(metric_names))
        conditions.append(f"metric_name IN ({placeholders})")
        params.extend(metric_names)

    # Use the kpi_dashboard view for current values with trend
    query = f"""
        SELECT * FROM kpi_dashboard
        WHERE {" AND ".join(conditions)}
        ORDER BY metric_name
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

    results = []
    for row in rows:
        results.append(KPISnapshotResponse(
            metric_name=row["metric_name"],
            metric_value=float(row["metric_value"]),
            target_value=float(row["target_value"]) if row["target_value"] is not None else None,
            threshold=float(row["threshold"]) if row["threshold"] is not None else None,
            measured_at=row["measured_at"].isoformat().replace("+00:00", "Z"),
            labels=row["labels"],
            trend=row["trend"],
            status=row["status"],
        ))

    return results


@app.get("/metrics/kpis/{metric_name}/history", response_model=list[KPISnapshotResponse])
async def get_kpi_history(
    metric_name: str,
    tenant_id: str = Query(..., description="Tenant UUID"),
    limit: int = Query(30, ge=1, le=1000, description="Number of historical points"),
):
    """Get historical trend for a specific KPI metric."""
    pool = pool_manager.get_pool()
    tenant_uuid = uuid.UUID(tenant_id)

    query = """
        SELECT * FROM kpi_snapshots
        WHERE tenant_id = %s AND metric_name = %s
        ORDER BY measured_at DESC
        LIMIT %s
    """

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (tenant_uuid, metric_name, limit))
            rows = cur.fetchall()

    results = []
    for i, row in enumerate(rows):
        prev_value = float(rows[i + 1]["metric_value"]) if i + 1 < len(rows) else None
        curr_value = float(row["metric_value"])

        if prev_value is None:
            trend = "stable"
        elif curr_value > prev_value:
            trend = "up"
        elif curr_value < prev_value:
            trend = "down"
        else:
            trend = "stable"

        threshold = float(row["threshold"]) if row["threshold"] is not None else None
        target = float(row["target_value"]) if row["target_value"] is not None else None

        if threshold is not None and curr_value < threshold and metric_name != "reconciliation_backlog":
            status = "breach"
        elif threshold is not None and metric_name == "reconciliation_backlog" and curr_value > threshold:
            status = "breach"
        elif target is not None and curr_value >= target:
            status = "on_target"
        else:
            status = "normal"

        results.append(KPISnapshotResponse(
            metric_name=row["metric_name"],
            metric_value=curr_value,
            target_value=target,
            threshold=threshold,
            measured_at=row["measured_at"].isoformat().replace("+00:00", "Z"),
            labels=row["labels"],
            trend=trend,
            status=status,
        ))

    return results


@app.get("/missions", response_model=list[MissionResponse])
async def get_missions(
    tenant_id: str = Query(..., description="Tenant UUID"),
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
):
    """List missions for a tenant."""
    pool = pool_manager.get_pool()
    tenant_uuid = uuid.UUID(tenant_id)

    conditions = ["tenant_id = %s"]
    params: list[Any] = [tenant_uuid]

    if status:
        conditions.append("status = %s")
        params.append(status)

    query = f"""
        SELECT * FROM missions
        WHERE {" AND ".join(conditions)}
        ORDER BY created_at DESC
        LIMIT %s OFFSET %s
    """
    params.extend([limit, offset])

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            rows = cur.fetchall()

    results = []
    for row in rows:
        results.append(MissionResponse(
            mission_id=str(row["mission_id"]),
            name=row["name"],
            description=row["description"],
            owner_id=str(row["owner_id"]),
            tenant_id=str(row["tenant_id"]),
            status=row["status"],
            proof_bundle=row["proof_bundle"],
            started_at=row["started_at"].isoformat().replace("+00:00", "Z") if row["started_at"] else None,
            completed_at=row["completed_at"].isoformat().replace("+00:00", "Z") if row["completed_at"] else None,
            created_at=row["created_at"].isoformat().replace("+00:00", "Z"),
        ))

    return results


@app.get("/missions/{mission_id}", response_model=MissionResponse)
async def get_mission(
    mission_id: str,
    tenant_id: str = Query(..., description="Tenant UUID"),
):
    """Get a specific mission by ID."""
    pool = pool_manager.get_pool()
    tenant_uuid = uuid.UUID(tenant_id)
    mission_uuid = uuid.UUID(mission_id)

    query = "SELECT * FROM missions WHERE mission_id = %s AND tenant_id = %s"

    with pool.connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, (mission_uuid, tenant_uuid))
            row = cur.fetchone()

    if row is None:
        raise HTTPException(status_code=404, detail="Mission not found")

    return MissionResponse(
        mission_id=str(row["mission_id"]),
        name=row["name"],
        description=row["description"],
        owner_id=str(row["owner_id"]),
        tenant_id=str(row["tenant_id"]),
        status=row["status"],
        proof_bundle=row["proof_bundle"],
        started_at=row["started_at"].isoformat().replace("+00:00", "Z") if row["started_at"] else None,
        completed_at=row["completed_at"].isoformat().replace("+00:00", "Z") if row["completed_at"] else None,
        created_at=row["created_at"].isoformat().replace("+00:00", "Z"),
    )


@app.post("/missions/{mission_id}/verify")
async def verify_mission(
    mission_id: str,
    tenant_id: str = Query(..., description="Tenant UUID"),
):
    """Verify a mission's proof bundle."""
    from personal_agent.mission.verifier import MissionVerifier

    tenant_uuid = uuid.UUID(tenant_id)
    mission_uuid = uuid.UUID(mission_id)

    verifier = MissionVerifier(tenant_uuid)
    try:
        is_valid, proof_bundle = verifier.verify_mission(mission_uuid)
        return {
            "mission_id": mission_id,
            "valid": is_valid,
            "proof_bundle": proof_bundle,
            "verified_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        }
    finally:
        verifier.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)