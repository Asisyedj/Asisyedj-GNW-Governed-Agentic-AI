"""Comprehensive tests for GNW Dynamic Model Router, Circuit Breaker, Anti-Bypass, and State Recovery."""
import json
import time
from unittest import mock
import httpx
import pytest

from personal_agent.agent.router import (
    CircuitState,
    ModelMetrics,
    ModelRouter,
    PolicyViolationError,
    RouterExhaustionError,
    TaskCategory,
)
from personal_agent.agent.planner import plan
from personal_agent.plugins.powershell_tool import PowerShellTool
from personal_agent.memory import sqlite_store


def test_anti_bypass_rejects_unapproved_endpoint():
    """Policy violation: router must reject non-localhost non-HTTPS endpoints."""
    with pytest.raises(PolicyViolationError):
        ModelRouter(base_url="http://unauthorized-external-api.com/v1")


def test_candidate_models_ordered_by_task_category():
    """Candidates must prioritize requested model, followed by task category fleet."""
    router = ModelRouter()
    candidates = router.get_candidate_models(
        requested_model="anthropic/claude-opus-5-thinking",
        task_category=TaskCategory.COMPLEX_REASONING,
    )
    assert candidates[0] == "anthropic/claude-opus-5-thinking"
    assert "openai/gpt-5.6-sol-thinking" in candidates
    assert len(candidates) >= 3


def test_router_fallback_on_model_timeout_or_failure():
    """When primary model times out or fails with 500, router automatically falls back to secondary."""
    router = ModelRouter(failure_threshold=3)

    call_log = []

    def fake_post(url, json=None, headers=None, **kwargs):
        model = json.get("model")
        call_log.append(model)
        if model == "primary-model":
            # Simulate timeout or 500
            request = httpx.Request("POST", url)
            response = httpx.Response(500, request=request)
            raise httpx.HTTPStatusError("Internal Server Error", request=request, response=response)
        # Fallback model succeeds
        request = httpx.Request("POST", url)
        resp_data = {"choices": [{"message": {"content": "Fallback success response"}}]}
        return httpx.Response(200, json=resp_data, request=request)

    mock_client = mock.MagicMock(spec=httpx.Client)
    mock_client.post.side_effect = fake_post

    # Configure candidates
    router.task_routes[TaskCategory.DEFAULT] = ["primary-model", "secondary-fallback-model"]

    res = router.execute_with_fallback(
        messages=[{"role": "user", "content": "Hello"}],
        requested_model="primary-model",
        http_client=mock_client,
    )

    assert res["ok"] is True
    assert res["model"] == "secondary-fallback-model"
    assert res["content"] == "Fallback success response"
    assert call_log == ["primary-model", "secondary-fallback-model"]

    # Check metrics
    primary_metrics = router.metrics["primary-model"]
    assert primary_metrics.failed_calls == 1
    assert primary_metrics.consecutive_failures == 1

    secondary_metrics = router.metrics["secondary-fallback-model"]
    assert secondary_metrics.successful_calls == 1
    assert secondary_metrics.consecutive_failures == 0

@pytest.mark.parametrize("status_code", [429, 503])
def test_transient_http_status_does_not_trip_circuit_breaker(status_code):
    router = ModelRouter(failure_threshold=2)
    request = httpx.Request("POST", "http://127.0.0.1/v1/chat/completions")
    response = httpx.Response(status_code, request=request)
    error = httpx.HTTPStatusError("transient upstream failure", request=request, response=response)

    for _ in range(4):
        router.record_failure("transient-model", error)

    metrics = router.metrics["transient-model"]
    assert metrics.failed_calls == 4
    assert metrics.consecutive_failures == 0
    assert metrics.circuit_state == CircuitState.CLOSED
    assert router.is_available("transient-model") is True


def test_transport_timeout_does_not_trip_circuit_breaker():
    router = ModelRouter(failure_threshold=1)
    request = httpx.Request("POST", "http://127.0.0.1/v1/chat/completions")
    error = httpx.ReadTimeout("upstream timed out", request=request)

    router.record_failure("timeout-model", error)

    metrics = router.metrics["timeout-model"]
    assert metrics.failed_calls == 1
    assert metrics.consecutive_failures == 0
    assert metrics.circuit_state == CircuitState.CLOSED


def test_transient_half_open_probe_reopens_with_cooldown():
    router = ModelRouter(failure_threshold=1, recovery_timeout_sec=10.0)
    router.record_failure("half-open-model", RuntimeError("persistent failure"))
    metrics = router.metrics["half-open-model"]
    metrics.last_failure_time -= 11.0
    assert router.is_available("half-open-model") is True
    assert metrics.circuit_state == CircuitState.HALF_OPEN

    request = httpx.Request("POST", "http://127.0.0.1/v1/chat/completions")
    response = httpx.Response(503, request=request)
    router.record_failure(
        "half-open-model",
        httpx.HTTPStatusError("upstream unavailable", request=request, response=response),
    )

    assert metrics.circuit_state == CircuitState.OPEN
    assert metrics.consecutive_failures == 1
    assert router.is_available("half-open-model") is False


@pytest.mark.parametrize("status_code", [401, 403])
def test_auth_failure_does_not_trip_breaker_or_try_fallback(status_code):
    router = ModelRouter(failure_threshold=1)
    router.task_routes[TaskCategory.DEFAULT] = ["primary-model", "fallback-model"]
    call_log = []

    def auth_failure(url, json=None, headers=None, **kwargs):
        call_log.append(json["model"])
        request = httpx.Request("POST", url)
        return httpx.Response(status_code, request=request)

    client = mock.MagicMock(spec=httpx.Client)
    client.post.side_effect = auth_failure

    with pytest.raises(httpx.HTTPStatusError):
        router.execute_with_fallback(
            messages=[{"role": "user", "content": "test"}],
            requested_model="primary-model",
            http_client=client,
        )

    metrics = router.metrics["primary-model"]
    assert call_log == ["primary-model"]
    assert metrics.failed_calls == 1
    assert metrics.consecutive_failures == 0
    assert metrics.circuit_state == CircuitState.CLOSED


def test_503_fallback_succeeds_without_opening_primary_circuit():
    router = ModelRouter(failure_threshold=1)
    router.task_routes[TaskCategory.DEFAULT] = ["primary-model", "secondary-model"]
    call_log = []

    def fake_post(url, json=None, headers=None, **kwargs):
        model = json["model"]
        call_log.append(model)
        request = httpx.Request("POST", url)
        if model == "primary-model":
            return httpx.Response(503, request=request)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": "fallback success"}}]},
            request=request,
        )

    client = mock.MagicMock(spec=httpx.Client)
    client.post.side_effect = fake_post
    result = router.execute_with_fallback(
        messages=[{"role": "user", "content": "test"}],
        requested_model="primary-model",
        http_client=client,
    )

    primary = router.metrics["primary-model"]
    assert result["ok"] is True
    assert result["model"] == "secondary-model"
    assert call_log == ["primary-model", "secondary-model"]
    assert primary.failed_calls == 1
    assert primary.consecutive_failures == 0
    assert primary.circuit_state == CircuitState.CLOSED


def test_circuit_breaker_trips_to_open_after_threshold():
    """Circuit breaker trips to OPEN after threshold failures and diverts traffic."""
    router = ModelRouter(failure_threshold=3, recovery_timeout_sec=10.0)

    for i in range(3):
        router.record_failure("flaky-model", RuntimeError("connection dropped"))

    metrics = router.metrics["flaky-model"]
    assert metrics.consecutive_failures == 3
    assert metrics.circuit_state == CircuitState.OPEN
    # Should not be available while OPEN and within recovery timeout
    assert router.is_available("flaky-model") is False


def test_circuit_breaker_half_open_recovery():
    """After recovery timeout, circuit enters HALF_OPEN probe and resets to CLOSED on success."""
    router = ModelRouter(failure_threshold=2, recovery_timeout_sec=0.05)

    router.record_failure("test-model", RuntimeError("fail 1"))
    router.record_failure("test-model", RuntimeError("fail 2"))
    assert router.metrics["test-model"].circuit_state == CircuitState.OPEN

    # Wait for recovery timeout
    time.sleep(0.06)

    # First probe check transitions to HALF_OPEN
    assert router.is_available("test-model") is True
    assert router.metrics["test-model"].circuit_state == CircuitState.HALF_OPEN

    # Record success -> resets to CLOSED
    router.record_success("test-model", latency_ms=120.0)
    assert router.metrics["test-model"].circuit_state == CircuitState.CLOSED
    assert router.metrics["test-model"].consecutive_failures == 0


def test_router_exhaustion_raises_error():
    """When all candidate models fail, router raises RouterExhaustionError fail-closed."""
    router = ModelRouter(failure_threshold=3)

    def failing_post(url, json=None, headers=None, **kwargs):
        request = httpx.Request("POST", url)
        raise httpx.ConnectError("Network unreachable", request=request)

    mock_client = mock.MagicMock(spec=httpx.Client)
    mock_client.post.side_effect = failing_post

    router.task_routes[TaskCategory.DEFAULT] = ["m1", "m2"]

    with pytest.raises(RouterExhaustionError) as exc_info:
        router.execute_with_fallback(
            messages=[{"role": "user", "content": "test"}],
            http_client=mock_client,
        )
    assert "All model candidates failed" in str(exc_info.value)


def test_unauthorized_tool_call_denied_fail_closed():
    """Tool proposal without explicit approval remains pending and never executes."""
    proposal = '{"tool": "powershell", "args": {"script": "Get-Process"}}'

    with mock.patch("personal_agent.agent.llm.call_llm", return_value=proposal):
        with mock.patch.object(PowerShellTool, "run") as mock_run:
            result = plan("List running processes")

    assert result["type"] == "approval_required"
    assert result["tool"] == "powershell"
    mock_run.assert_not_called()


def test_safe_sqlite_memory_without_eval(tmp_path, monkeypatch):
    """Memory fact storage and retrieval must safely serialize/deserialize complex types without eval."""
    test_db = tmp_path / "test_memory.db"
    monkeypatch.setattr(sqlite_store, "DB_PATH", test_db)

    user = "audit_user_01"
    sqlite_store.add_fact(user, "config", {"models": 99, "fleet": ["claude", "gpt"], "verified": True})
    sqlite_store.add_fact(user, "counter", 42)

    val_config, ts1 = sqlite_store.get_fact(user, "config")
    assert val_config == {"models": 99, "fleet": ["claude", "gpt"], "verified": True}
    assert isinstance(ts1, int)

    val_counter, ts2 = sqlite_store.get_fact(user, "counter")
    assert val_counter == 42

    search_res = sqlite_store.search_facts(user, "conf")
    assert len(search_res) == 1
    assert search_res[0][0] == "config"
    assert search_res[0][1]["models"] == 99
