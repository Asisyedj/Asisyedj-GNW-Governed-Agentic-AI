"""Test router persistence integration."""
import pytest
import uuid

from personal_agent.agent.router import ModelRouter, CircuitState
from personal_agent.state.persistence import get_state_store


class TestRouterPersistenceIntegration:
    """Integration tests for router persistence."""

    @pytest.fixture
    def router(self) -> ModelRouter:
        """Create a router with test state store."""
        tenant_id = uuid.uuid4()
        store = get_state_store(tenant_id=tenant_id)
        router = ModelRouter(state_store=store, tenant_id=tenant_id)
        return router

    def test_router_circuit_breaker_persisted(self, router: ModelRouter) -> None:
        """Test that router circuit breaker changes are persisted."""
        model_id = "test/persist-model"
        
        # Trip the breaker
        for _ in range(router.failure_threshold):
            router.record_failure(model_id, Exception("Test failure"))
        
        # Verify in-memory state
        metrics = router._get_or_create_metrics(model_id)
        assert metrics.circuit_state == CircuitState.OPEN
        
        # Verify persisted state
        store = router._state_store
        execution_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"circuit-breaker:{model_id}")
        history = store.get_execution_history(execution_id)
        
        # Should have transition to OPEN
        open_transitions = [t for t in history if t.to_state == "OPEN"]
        assert len(open_transitions) >= 1

    def test_router_recovery_persisted(self, router: ModelRouter) -> None:
        """Test that router recovery is persisted."""
        model_id = "test/recovery-model"
        
        # Trip the breaker
        for _ in range(router.failure_threshold):
            router.record_failure(model_id, Exception("Test failure"))
        
        # Force recovery via success
        router.record_success(model_id, 100.0)
        
        # Verify in-memory state
        metrics = router._get_or_create_metrics(model_id)
        assert metrics.circuit_state == CircuitState.CLOSED
        
        # Verify persisted recovery transition
        store = router._state_store
        execution_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"circuit-breaker:{model_id}")
        history = store.get_execution_history(execution_id)
        
        # Should have transition from OPEN/HALF_OPEN to CLOSED
        recovery_transitions = [t for t in history if t.to_state == "CLOSED" and t.from_state in ("OPEN", "HALF_OPEN")]
        assert len(recovery_transitions) >= 1

    def test_router_half_open_persisted(self, router: ModelRouter) -> None:
        """Test that HALF_OPEN transition is persisted."""
        model_id = "test/half-open-model"
        
        # Trip the breaker
        for _ in range(router.failure_threshold):
            router.record_failure(model_id, Exception("Test failure"))
        
        metrics = router._get_or_create_metrics(model_id)
        metrics.last_failure_time = 0  # Force expiration
        
        # Check availability triggers HALF_OPEN
        is_avail = router.is_available(model_id)
        assert is_avail is True
        
        metrics = router._get_or_create_metrics(model_id)
        assert metrics.circuit_state == CircuitState.HALF_OPEN
        
        # Verify persisted
        store = router._state_store
        execution_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"circuit-breaker:{model_id}")
        history = store.get_execution_history(execution_id)
        
        half_open_transitions = [t for t in history if t.to_state == "HALF_OPEN"]
        assert len(half_open_transitions) >= 1

    def test_router_periodic_metrics_persist(self, router: ModelRouter) -> None:
        """Test that periodic metrics persistence works."""
        model_id = "test/metrics-model"
        
        # Generate some metrics
        router.record_success(model_id, 50.0)
        router.record_failure(model_id, Exception("Test failure"))
        
        # Trigger persistence
        router.persist_metrics()
        
        # Verify metrics were recorded
        store = router._state_store
        execution_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"metrics:{model_id}")
        history = store.get_execution_history(execution_id)
        
        metrics_transitions = [t for t in history if t.trigger == "periodic_metrics"]
        assert len(metrics_transitions) >= 1
        
        # Verify metadata contains expected fields
        metadata = metrics_transitions[-1].metadata
        assert metadata.get("model_id") == model_id
        assert "total_calls" in metadata
        assert "circuit_state" in metadata


if __name__ == "__main__":
    pytest.main([__file__, "-v"])