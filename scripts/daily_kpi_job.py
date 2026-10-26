#!/usr/bin/env python3
"""Daily KPI Collection Job — Cron entry point.

GNW Governed Agent - P3F: Mission Proof System & KPI Automation

Runs all KPI collectors, stores snapshots, alerts on threshold breach.

Usage:
    python scripts/daily_kpi_job.py

Cron schedule (runs at 02:00 UTC daily):
    0 2 * * * /path/to/python scripts/daily_kpi_job.py
"""

from __future__ import annotations

import json
import logging
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from personal_agent.mission.kpi_collector import KPICollector, run_daily_collection

# Configure logging
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "daily_kpi_job.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("daily_kpi_job")


def get_tenant_ids() -> list[uuid.UUID]:
    """Get list of tenant IDs to process.

    In a multi-tenant system, this would query the tenants table.
    For now, supports single tenant via env var or defaults.
    """
    # Check for explicit tenant list
    tenant_env = os.environ.get("GNW_TENANT_IDS")
    if tenant_env:
        return [uuid.UUID(t.strip()) for t in tenant_env.split(",")]

    # Check for single tenant
    single_tenant = os.environ.get("GNW_TENANT_ID")
    if single_tenant:
        return [uuid.UUID(single_tenant)]

    # Default: try to discover from database
    # This requires a database connection
    try:
        import psycopg
        from psycopg.rows import dict_row

        dsn = os.environ.get("GNW_PG_DSN")
        if dsn:
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT DISTINCT tenant_id FROM missions")
                    rows = cur.fetchall()
                    return [uuid.UUID(str(row["tenant_id"])) for row in rows]
    except Exception as e:
        logger.warning(f"Could not discover tenants from database: {e}")

    # No tenants found
    logger.error("No tenant IDs configured. Set GNW_TENANT_ID or GNW_TENANT_IDS")
    return []


def load_thresholds(tenant_id: uuid.UUID) -> dict[str, float] | None:
    """Load custom thresholds for a tenant from config file or database.

    Returns None to use defaults.
    """
    # Try config file
    config_path = PROJECT_ROOT / "config" / f"kpi_thresholds_{tenant_id}.json"
    if config_path.exists():
        try:
            with config_path.open() as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load thresholds from {config_path}: {e}")

    # Try database (kpi_thresholds table if it exists)
    try:
        import psycopg
        from psycopg.rows import dict_row

        dsn = os.environ.get("GNW_PG_DSN")
        if dsn:
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT metric_name, threshold_value FROM kpi_thresholds WHERE tenant_id = %s",
                        (tenant_id,),
                    )
                    rows = cur.fetchall()
                    if rows:
                        return {row["metric_name"]: float(row["threshold_value"]) for row in rows}
    except Exception:
        pass

    return None


def send_alert(alert: dict, tenant_id: uuid.UUID) -> None:
    """Send alert notification.

    In production, this would integrate with:
    - PagerDuty / Opsgenie
    - Slack / Teams webhook
    - Email via SES
    - CloudWatch alarms
    """
    alert_msg = (
        f"🚨 KPI ALERT - Tenant: {tenant_id}\n"
        f"Metric: {alert['metric_name']}\n"
        f"Value: {alert['metric_value']:.4f}\n"
        f"Threshold: {alert['threshold']:.4f}\n"
        f"Breach: {alert['breach_type']}\n"
        f"Time: {alert['timestamp']}"
    )

    logger.warning(alert_msg)

    # Webhook integration example
    webhook_url = os.environ.get("GNW_ALERT_WEBHOOK")
    if webhook_url:
        try:
            import urllib.request
            data = json.dumps({"text": alert_msg}).encode("utf-8")
            req = urllib.request.Request(
                webhook_url,
                data=data,
                headers={"Content-Type": "application/json"},
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")


def main() -> int:
    """Main entry point for daily KPI collection job."""
    logger.info("=" * 60)
    logger.info("Starting daily KPI collection job")
    logger.info(f"Time: {datetime.now(timezone.utc).isoformat()}")
    logger.info("=" * 60)

    tenant_ids = get_tenant_ids()
    if not tenant_ids:
        logger.error("No tenants to process. Exiting.")
        return 1

    logger.info(f"Processing {len(tenant_ids)} tenant(s): {tenant_ids}")

    overall_success = True
    all_alerts = []

    for tenant_id in tenant_ids:
        logger.info(f"\n--- Processing tenant: {tenant_id} ---")

        try:
            thresholds = load_thresholds(tenant_id)
            if thresholds:
                logger.info(f"Loaded custom thresholds: {thresholds}")

            # Run collection
            result = run_daily_collection(tenant_id, thresholds=thresholds)

            metrics = result["metrics"]
            alerts = result["alerts"]

            logger.info(f"Collected {len(metrics)} metrics:")
            for name, value in metrics.items():
                threshold = thresholds.get(name) if thresholds else None
                threshold_str = f" (threshold: {threshold})" if threshold else ""
                logger.info(f"  {name}: {value:.4f}{threshold_str}")

            if alerts:
                logger.warning(f"⚠️  {len(alerts)} threshold breach(es) detected!")
                for alert in alerts:
                    logger.warning(
                        f"  BREACH: {alert['metric_name']} = {alert['metric_value']:.4f} "
                        f"({alert['breach_type']} threshold {alert['threshold']:.4f})"
                    )
                    send_alert(alert, tenant_id)
                all_alerts.extend(alerts)
            else:
                logger.info("✅ All metrics within thresholds")

        except Exception as e:
            logger.exception(f"Failed to process tenant {tenant_id}: {e}")
            overall_success = False

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("Daily KPI collection job complete")
    logger.info(f"Tenants processed: {len(tenant_ids)}")
    logger.info(f"Total alerts: {len(all_alerts)}")
    logger.info(f"Overall status: {'SUCCESS' if overall_success else 'PARTIAL FAILURE'}")
    logger.info("=" * 60)

    return 0 if overall_success else 1


if __name__ == "__main__":
    sys.exit(main())