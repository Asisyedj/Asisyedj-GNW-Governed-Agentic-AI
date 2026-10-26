import pytest
import logging

from personal_agent.swarm.orchestrator import SwarmCoordinator
from personal_agent.health.model_health import HealthState

logger = logging.getLogger(__name__)

def test_swarm_coordinator_runs_all_models(monkeypatch):
    """Test SwarmCoordinator with mocked router to avoid real network calls.

    The coordinator is instantiated with a permissive health threshold, then its
    ``models`` list is forced to a single dummy entry. ``global_router`` is
    monkey‑patched to return a predictable successful result.
    """
    from personal_agent.health.model_health import HealthState
    from personal_agent.swarm.orchestrator import SwarmCoordinator
    from personal_agent.agent.router import global_router

    # Initialise with any health state – we will overwrite the models list.
    coordinator = SwarmCoordinator(min_state=HealthState.UNVERIFIED)
    # Use a deterministic dummy model ID.
    coordinator.models = ["dummy-model"]

    # Mock the router to return a fixed successful payload.
    def fake_execute_with_fallback(*args, **kwargs):
        return {
            "ok": True,
            "model": kwargs.get("requested_model", "dummy-model"),
            "content": "GNW_HEALTH_CHECK response",
            "latency_ms": 10.0,
            "attempted_models": [kwargs.get("requested_model", "dummy-model")],
        }

    monkeypatch.setattr(global_router, "execute_with_fallback", fake_execute_with_fallback)

    prompt = "GNW_HEALTH_CHECK"
    results = coordinator.run_task(prompt)
    assert set(results.keys()) == set(coordinator.models)
    for model_id, result in results.items():
        assert result.get("ok") is True
        assert "GNW_HEALTH_CHECK" in result.get("content", "")

    # Real-model execution removed for deterministic testing
