"""Model health registry and status tracking.

The health of a model is more than the catalog's `status` field. It requires a
live, bounded probe through the approved `ModelRouter`. This module provides a
singleton ``global_health_registry`` that the swarm layer can query for "eligible"
models.
"""

from __future__ import annotations

import json
import logging
import time
import urllib.request
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional

import httpx

from gnw_secrets import get_bridge_key
from personal_agent.agent.router import (
    TaskCategory,
    global_router,
    ModelRouter,
    PolicyViolationError,
    RouterExhaustionError,
)

logger = logging.getLogger(__name__)

# ----------------------------------------------------------------------
# Health state definition
# ----------------------------------------------------------------------
class HealthState(str, Enum):
    UNVERIFIED = "unverified"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    QUARANTINED = "quarantined"
    UNKNOWN = "unknown"
    UNAVAILABLE = "unavailable"

# ----------------------------------------------------------------------
# Simple per‑model health record
# ----------------------------------------------------------------------
@dataclass
class ModelHealthRecord:
    model_id: str
    catalog_status: str  # raw status from bridge catalog (available/unknown/unavailable)
    health_state: HealthState = HealthState.UNVERIFIED
    last_probe_ts: Optional[float] = None  # epoch seconds
    last_error: Optional[Exception] = None
    # Optional extra fields for future extension (e.g., latency avg)
    latency_ms: List[float] = field(default_factory=list)

    def update_probe_success(self, latency: float) -> None:
        self.health_state = HealthState.HEALTHY
        self.last_probe_ts = time.time()
        self.last_error = None
        self.latency_ms.append(latency)

    def update_probe_failure(self, exc: Exception) -> None:
        self.health_state = HealthState.QUARANTINED
        self.last_probe_ts = time.time()
        self.last_error = exc
        # keep latency list unchanged

# ----------------------------------------------------------------------
# Registry singleton
# ----------------------------------------------------------------------
class ModelHealthRegistry:
    """Maintain health information for all models known to the bridge.

    The registry is intentionally lightweight – it loads the catalog on
    instantiation and performs on‑demand probes. All state lives in memory;
    persistence is outside the current scope.
    """

    def __init__(self, router: ModelRouter | None = None):
        self.router = router or global_router
        self.records: Dict[str, ModelHealthRecord] = {}
        self._load_catalog()
        # Load any persisted snapshot to retain health state across restarts
        try:
            self.load_snapshot()
        except Exception as exc:
            logger.warning("Failed to load health snapshot on init: %s", exc)
        self.records: Dict[str, ModelHealthRecord] = {}
        self._load_catalog()

    # ------------------------------------------------------------------
    # Catalog handling
    # ------------------------------------------------------------------
    def _load_catalog(self) -> None:
        """Populate ``self.records`` from the authenticated /v1/models endpoint.

        The bridge returns a JSON object with a ``data`` list where each entry
        contains an ``id`` and a nested ``perplexity`` dict that includes a
        ``status`` field. Models not present are ignored.
        """
        key = get_bridge_key()
        req = urllib.request.Request(
            "http://127.0.0.1:8000/v1/models",
            headers={"Authorization": f"Bearer {key}"},
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            catalog = json.load(resp)
        for entry in catalog.get("data", []):
            model_id = entry.get("id")
            if not model_id:
                continue
            status = entry.get("perplexity", {}).get("status", "unknown")
            # Map catalog status to initial health state
            if status == "available":
                health = HealthState.UNVERIFIED
            elif status == "unknown":
                health = HealthState.UNKNOWN
            else:
                health = HealthState.UNAVAILABLE
            self.records[model_id] = ModelHealthRecord(
                model_id=model_id, catalog_status=status, health_state=health
            )

    def refresh_catalog(self) -> None:
        """Reload the catalog and preserve any existing health information.
        New entries are added; missing entries are removed.
        """
        old = {mid: rec.health_state for mid, rec in self.records.items()}
        self.records.clear()
        self._load_catalog()
        # Restore previous health where possible
        for mid, state in old.items():
            if mid in self.records:
                self.records[mid].health_state = state

    # ------------------------------------------------------------------
    # Probe handling
    # ------------------------------------------------------------------
    def probe_model(self, model_id: str, timeout: float = 30.0) -> HealthState:
        """Run a minimal health‑check probe via the router.

        The probe sends a tiny chat request expecting the exact token
        ``GNW_HEALTH_CHECK``. A successful response updates the record to
        ``HEALTHY``. HTTP 503 from the bridge is treated as permanent
        unavailability (model marked ``UNAVAILABLE``). All other failures are
        recorded as a normal probe failure (``QUARANTINED``).
        """
        if model_id not in self.records:
            raise ValueError(f"Model {model_id!r} not known in catalog")
        record = self.records[model_id]
        # Skip probing if catalog says unavailable/unknown – keep that state.
        if record.catalog_status != "available":
            return record.health_state
        # Build a trivial message payload.
        messages = [{"role": "user", "content": "GNW_HEALTH_CHECK"}]
        start = time.perf_counter()
        try:
            result = self.router.execute_with_fallback(
                messages=messages,
                requested_model=model_id,
                task_category=TaskCategory.DEFAULT,
                timeout=timeout,
            )
            latency = (time.perf_counter() - start) * 1000.0
            # Very basic validation – content must contain the probe token.
            if isinstance(result.get("content"), str) and "GNW_HEALTH_CHECK" in result["content"]:
                record.update_probe_success(latency)
            else:
                raise RuntimeError("Unexpected probe response content")
        except Exception as exc:
            # Distinguish HTTP 503 (upstream service unavailable) and treat as permanently unavailable via bridge
            if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None and exc.response.status_code == 503:
                record.health_state = HealthState.UNAVAILABLE
                record.last_error = exc
                record.last_probe_ts = time.time()
                logger.warning("Model %s received 503 from bridge – marking as UNAVAILABLE", model_id)
            else:
                record.update_probe_failure(exc)
        return record.health_state
        """Run a minimal health‑check probe via the router.

        The probe sends a tiny chat request expecting the exact token
        ``GNW_HEALTH_CHECK``. A successful response updates the record to
        ``HEALTHY``; any exception (including policy violations) marks the model as
        ``QUARANTINED``.
        """
        if model_id not in self.records:
            raise ValueError(f"Model {model_id!r} not known in catalog")
        record = self.records[model_id]
        # Skip probing if catalog says unavailable/unknown – keep that state.
        if record.catalog_status != "available":
            return record.health_state
        # Build a trivial message payload.
        messages = [{"role": "user", "content": "GNW_HEALTH_CHECK"}]
        start = time.perf_counter()
        try:
            result = self.router.execute_with_fallback(
                messages=messages,
                requested_model=model_id,
                task_category=TaskCategory.DEFAULT,
                timeout=timeout,
            )
            latency = (time.perf_counter() - start) * 1000.0
            # Very basic validation – content must contain the probe token.
            if isinstance(result.get("content"), str) and "GNW_HEALTH_CHECK" in result["content"]:
                record.update_probe_success(latency)
            else:
                raise RuntimeError("Unexpected probe response content")
        except Exception as exc:  # includes RouterExhaustionError, HTTP errors, etc.
            # Distinguish HTTP 503 (upstream service unavailable) and treat as permanently unavailable via bridge
            if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None and exc.response.status_code == 503:
                # Mark as unavailable so it is excluded from future bridge routing
                record.health_state = HealthState.UNAVAILABLE
                record.last_error = exc
                record.last_probe_ts = time.time()
                logger.warning("Model %s received 503 from bridge – marking as UNAVAILABLE", model_id)
            else:
                record.update_probe_failure(exc)

            # Distinguish HTTP 503 (upstream service unavailable) and treat as permanently unavailable via bridge
            if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None and exc.response.status_code == 503:
                # Mark as unavailable so it is excluded from future bridge routing
                record.health_state = HealthState.UNAVAILABLE
                record.last_error = exc
                record.last_probe_ts = time.time()
                logger.warning("Model %s received 503 from bridge – marking as UNAVAILABLE", model_id)
            else:
                record.update_probe_failure(exc)

            record.update_probe_failure(exc)
        return record.health_state

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def save_snapshot(self, path: Path | None = None) -> None:
        """Persist the current health registry to a JSON file.

        The default location is ``health_snapshot.json`` alongside this module.
        """
        out_path = path or Path(__file__).with_name("health_snapshot.json")
        snapshot = {
            mid: {
                "catalog_status": rec.catalog_status,
                "health_state": rec.health_state.value,
                "last_probe_ts": rec.last_probe_ts,
                "latency_ms": rec.latency_ms,
                "last_error": str(rec.last_error) if rec.last_error else None,
            }
            for mid, rec in self.records.items()
        }
        out_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True))
        logger.info("ModelHealthRegistry snapshot saved to %s", out_path)

    def load_snapshot(self, path: Path | None = None) -> None:
        """Load a previously saved snapshot, merging into the current registry.

        Existing records are updated; missing records are left unchanged.
        """
        in_path = path or Path(__file__).with_name("health_snapshot.json")
        if not in_path.is_file():
            logger.debug("Health snapshot %s not found; skipping load", in_path)
            return
        try:
            data = json.loads(in_path.read_text())
        except Exception as exc:
            logger.error("Failed to read health snapshot %s: %s", in_path, exc)
            return
        for mid, rec_data in data.items():
            if mid in self.records:
                rec = self.records[mid]
                rec.catalog_status = rec_data.get("catalog_status", rec.catalog_status)
                rec.health_state = HealthState(rec_data.get("health_state", rec.health_state.value))
                rec.last_probe_ts = rec_data.get("last_probe_ts", rec.last_probe_ts)
                rec.latency_ms = rec_data.get("latency_ms", rec.latency_ms)
                err = rec_data.get("last_error")
                rec.last_error = Exception(err) if err else None
            else:
                # Create a new record for models that were not in the catalog at load time.
                self.records[mid] = ModelHealthRecord(
                    model_id=mid,
                    catalog_status=rec_data.get("catalog_status", "unknown"),
                    health_state=HealthState(rec_data.get("health_state", "unknown")),
                    last_probe_ts=rec_data.get("last_probe_ts"),
                    latency_ms=rec_data.get("latency_ms", []),
                    last_error=Exception(rec_data["last_error"]) if rec_data.get("last_error") else None,
                )
        logger.info("ModelHealthRegistry snapshot loaded from %s", in_path)

    def eligible_models(self, min_state: HealthState = HealthState.HEALTHY) -> List[str]:
        """Return model IDs whose health meets or exceeds ``min_state``.

        Ordering is deterministic (sorted by model ID) to make selection
        reproducible.
        """
        # Define ordering of enum values for comparison.
        order = {
            HealthState.UNVERIFIED: 0,
            HealthState.HEALTHY: 1,
            HealthState.DEGRADED: 2,
            HealthState.QUARANTINED: -1,
            HealthState.UNKNOWN: -2,
            HealthState.UNAVAILABLE: -3,
        }
        threshold = order.get(min_state, 0)
        eligible = [mid for mid, rec in self.records.items() if order.get(rec.health_state, -10) >= threshold]
        return sorted(eligible)

# Global singleton for easy import by other modules.
global_health_registry = ModelHealthRegistry()
