from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from personal_agent.agent.provider_gateway import API_ROOT, create_app


@pytest.fixture

def fake_transport():
    calls: list[tuple[str, str, dict, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        calls.append((request.method, str(request.url), dict(request.headers), body))
        return httpx.Response(200, json={"ok": True, "echo_model": body.get("model")})

    return httpx.MockTransport(handler), calls


def local_client(app) -> TestClient:
    return TestClient(app, client=("127.0.0.1", 43123))


def test_orchestrator_route_uses_fixed_official_endpoint_and_server_key(monkeypatch, fake_transport):
    transport, calls = fake_transport
    monkeypatch.setenv("PERPLEXITY_API_KEY", "offline-test-key")
    client = local_client(create_app(transport=transport))

    response = client.post(
        "/v1/orchestrator/chat/completions",
        json={"model": "provider/model", "messages": [{"role": "user", "content": "hello"}]},
    )

    assert response.status_code == 200
    assert calls[0][0] == "POST"
    assert calls[0][1] == API_ROOT + "/orchestrator/v1/chat/completions"
    assert calls[0][2]["authorization"] == "Bearer offline-test-key"
    assert calls[0][3]["model"] == "provider/model"


def test_agent_route_uses_documented_agent_endpoint(monkeypatch, fake_transport):
    transport, calls = fake_transport
    monkeypatch.setenv("PERPLEXITY_API_KEY", "offline-test-key")
    client = local_client(create_app(transport=transport))

    response = client.post("/v1/agent", json={"model": "provider/model", "input": "hello"})

    assert response.status_code == 200
    assert calls[0][1] == API_ROOT + "/v1/agent"


def test_search_route_uses_documented_search_endpoint(monkeypatch, fake_transport):
    transport, calls = fake_transport
    monkeypatch.setenv("PERPLEXITY_API_KEY", "offline-test-key")
    client = local_client(create_app(transport=transport))

    response = client.post("/v1/search", json={"query": "hello", "max_results": 3})

    assert response.status_code == 200
    assert calls[0][1] == API_ROOT + "/search"


def test_custom_dispatch_selects_only_known_official_route(monkeypatch, fake_transport):
    transport, calls = fake_transport
    monkeypatch.setenv("PERPLEXITY_API_KEY", "offline-test-key")
    client = local_client(create_app(transport=transport))

    response = client.post(
        "/v1/custom/dispatch",
        json={"route": "agent", "payload": {"model": "provider/model", "input": "hello"}},
    )

    assert response.status_code == 200
    assert calls[0][1] == API_ROOT + "/v1/agent"


def test_unknown_custom_route_is_rejected_without_network(fake_transport):
    transport, calls = fake_transport
    client = local_client(create_app(transport=transport))

    response = client.post("/v1/custom/dispatch", json={"route": "https://example.com", "payload": {}})

    assert response.status_code == 400
    assert calls == []


def test_computer_route_is_explicitly_unavailable_and_never_calls_upstream(fake_transport):
    transport, calls = fake_transport
    client = local_client(create_app(transport=transport))

    response = client.post("/v1/computer", json={"input": "do something"})

    assert response.status_code == 501
    assert response.json()["error"]["code"] == "computer_control_api_unavailable"
    assert calls == []


def test_computer_plan_uses_official_text_route_and_marks_nonexecution(monkeypatch):
    calls: list[tuple[str, dict, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        calls.append((str(request.url), dict(request.headers), body))
        return httpx.Response(200, json={"choices": [{"message": {"content": "Review the screen manually; no action was taken."}}]})

    monkeypatch.setenv("PERPLEXITY_API_KEY", "offline-test-key")
    client = local_client(create_app(transport=httpx.MockTransport(handler)))
    response = client.post(
        "/v1/computer/plan",
        json={"model": "account-enabled-model", "task": "Help me review the visible Computer controls."},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["mode"] == "computer_task_plan_only"
    assert result["status"] == "pending_human_review"
    assert result["executed"] is False
    assert result["approval_required"] is True
    assert result["untrusted_model_output"] is True
    assert result["plan_text"] == "Review the screen manually; no action was taken."
    assert calls[0][0] == API_ROOT + "/orchestrator/v1/chat/completions"
    assert calls[0][1]["authorization"] == "Bearer offline-test-key"
    payload = calls[0][2]
    assert payload["model"] == "account-enabled-model"
    assert payload["stream"] is False
    assert "tools" not in payload
    assert [message["role"] for message in payload["messages"]] == ["system", "user"]
    assert "cannot see or operate" in payload["messages"][0]["content"]


def test_computer_plan_missing_api_key_fails_closed_without_network(monkeypatch):
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={})

    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    client = local_client(create_app(transport=httpx.MockTransport(handler)))
    response = client.post("/v1/computer/plan", json={"model": "model", "task": "Plan"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "api_key_not_configured"
    assert calls == []


def test_computer_plan_rejects_extra_fields_and_oversized_tasks_without_network(monkeypatch):
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={})

    monkeypatch.setenv("PERPLEXITY_API_KEY", "offline-test-key")
    client = local_client(create_app(transport=httpx.MockTransport(handler)))
    extra = client.post("/v1/computer/plan", json={"model": "model", "task": "Plan", "tools": []})
    oversized = client.post("/v1/computer/plan", json={"model": "model", "task": "x" * 4001})

    assert extra.status_code == 400
    assert oversized.status_code == 413
    assert calls == []


def test_computer_plan_preserves_upstream_503(monkeypatch):
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(503, json={"error": {"code": "upstream_unavailable"}})

    monkeypatch.setenv("PERPLEXITY_API_KEY", "offline-test-key")
    client = local_client(create_app(transport=httpx.MockTransport(handler)))
    response = client.post("/v1/computer/plan", json={"model": "model", "task": "Plan"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "upstream_unavailable"
    assert calls == [API_ROOT + "/orchestrator/v1/chat/completions"]


def test_missing_api_key_fails_closed_without_network(monkeypatch, fake_transport):
    transport, calls = fake_transport
    monkeypatch.delenv("PERPLEXITY_API_KEY", raising=False)
    client = local_client(create_app(transport=transport))

    response = client.post("/v1/search", json={"query": "hello"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "api_key_not_configured"
    assert calls == []


def test_non_loopback_call_is_rejected_before_upstream(monkeypatch, fake_transport):
    transport, calls = fake_transport
    monkeypatch.setenv("PERPLEXITY_API_KEY", "offline-test-key")
    app = create_app(transport=transport)
    client = TestClient(app, client=("203.0.113.10", 43123))

    response = client.post("/v1/search", json={"query": "hello"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "loopback_only"
    assert calls == []
