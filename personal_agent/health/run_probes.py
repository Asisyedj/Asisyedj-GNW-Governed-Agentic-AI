"""Run bounded health probes for available models and save a snapshot.

This script is intended to be executed manually or via a scheduled task.
It probes up to a configurable number of models (default 15) that are
currently catalog‑available but not yet marked as healthy.
The results are written to ``health_snapshot.json`` in the same directory.
"""

import json
import sys
sys.path.append(r'd:/GNW/perplexity-browser-api')
from pathlib import Path

# Import the global registry singleton
from personal_agent.health.model_health import global_health_registry, HealthState

# How many models to probe in this run – can be overridden via CLI arg
DEFAULT_LIMIT = 15


def main(limit: int = DEFAULT_LIMIT) -> None:
    # Select models that are catalog‑available (UNVERIFIED) – we treat UNVERIFIED as needing probing
    candidates = [
        mid
        for mid, rec in global_health_registry.records.items()
        if rec.catalog_status == "available" and rec.health_state == HealthState.UNVERIFIED
    ]
    if not candidates:
        print("No models require probing.")
        return
    # Limit the batch size
    to_probe = candidates[:limit]
    print(f"Probing {len(to_probe)} models (limit={limit})...")
    for model_id in to_probe:
        try:
            state = global_health_registry.probe_model(model_id, timeout=20.0)
            print(f" - {model_id}: {state}")
        except Exception as exc:
            print(f" - {model_id}: probe error {exc!r}")
    # Save a snapshot of the current registry state
    snapshot = {
        mid: {
            "catalog_status": rec.catalog_status,
            "health_state": rec.health_state.value,
            "last_probe_ts": rec.last_probe_ts,
            "latency_ms": rec.latency_ms,
            "last_error": str(rec.last_error) if rec.last_error else None,
        }
        for mid, rec in global_health_registry.records.items()
    }
    out_path = Path(__file__).with_name("health_snapshot.json")
    out_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True))
    print(f"Snapshot written to {out_path}")


if __name__ == "__main__":
    # Optional CLI arg to set limit
    if len(sys.argv) > 1:
        try:
            limit_arg = int(sys.argv[1])
        except ValueError:
            print(f"Invalid limit '{sys.argv[1]}', using default {DEFAULT_LIMIT}")
            limit_arg = DEFAULT_LIMIT
    else:
        limit_arg = DEFAULT_LIMIT
    main(limit_arg)
