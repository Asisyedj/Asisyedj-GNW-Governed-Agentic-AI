from __future__ import annotations

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from personal_agent.agent.local_computer_planner import (
    OLLAMA_CHAT_URL,
    OLLAMA_TAGS_URL,
    PLAN_SCHEMA,
    create_app,
)

MODEL = "qwen3:8b"
PLAN = {
    "title": "Open the target app",
    "summary": "A short plan for a user-reviewed desktop task.",
    "steps": [
        {
            "action": "open_app",
            "description": "Open the named app and inspect its visible state.",
            "risk": "low",
            "reason": "Observation only; no prompt is submitted.",
        }
    ],
    "blockers": [],
}


@pytest.fixture
def fake_transport():
    calls: list[httpx.Request] = []
    plan_text = json.dumps(PLAN)

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if request.method == "GET" and str(request.url) == OLLAMA_TAGS_URL:
            return httpx.Response(200, json={"models": [{"name": MODEL, "model": MODEL}]})
        if request.method == "POST" and str(request.url) == OLLAMA_CHAT_URL:
            return httpx.Response(
                200,
                json={"model": MODEL, "message": {"role": "assistant", "content": plan_text}, "done": True},
            )
        return httpx.Response(404, json={"error": "unexpected mock request"})

    return httpx.MockTransport(handler), calls


def local_client(app) -> TestClient:
    return TestClient(app, client=("127.0.0.1", 43123))


def test_health_is_local_and_does_not_probe_ollama(monkeypatch, fake_transport):
    transport, calls = fake_transport
    monkeypatch.setenv("GNW_LOCAL_OLLAMA_MODEL", MODEL)
    response = local_client(create_app(transport=transport)).get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "mode": "loopback-plan-only",
        "model_configured": True,
        "execution": "disabled",
    }
    assert calls == []


def test_valid_local_plan_is_returned_pending_review_and_never_executed(monkeypatch, fake_transport):
    transport, calls = fake_transport
    monkeypatch.setenv("GNW_LOCAL_OLLAMA_MODEL", MODEL)
    response = local_client(create_app(transport=transport)).post("/v1/plan", json={"task": "Open the app and inspect the screen"})

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "pending_human_review"
    assert body["approval_required"] is True
    assert body["executed"] is False
    assert body["plan"]["steps"][0]["requires_user_approval"] is True
    assert [request.method for request in calls] == ["GET", "POST"]
    assert [str(request.url) for request in calls] == [OLLAMA_TAGS_URL, OLLAMA_CHAT_URL]
    payload = json.loads(calls[1].content.decode("utf-8"))
    assert payload["model"] == MODEL
    assert payload["stream"] is False
    assert payload["format"] == PLAN_SCHEMA
    assert "tools" not in payload
    assert [message["role"] for message in payload["messages"]] == ["system", "user"]


def test_missing_model_fails_closed_without_local_request(monkeypatch, fake_transport):
    transport, calls = fake_transport
    monkeypatch.delenv("GNW_LOCAL_OLLAMA_MODEL", raising=False)
    response = local_client(create_app(transport=transport)).post("/v1/plan", json={"task": "Plan a task"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "local_model_not_configured"
    assert calls == []


def test_cloud_model_name_is_blocked_before_request(monkeypatch, fake_transport):
    transport, calls = fake_transport
    monkeypatch.setenv("GNW_LOCAL_OLLAMA_MODEL", "gpt-oss:120b-cloud")
    response = local_client(create_app(transport=transport)).post("/v1/plan", json={"task": "Plan a task"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "remote_model_blocked"
    assert calls == []


def test_uninstalled_model_fails_before_chat(monkeypatch, fake_transport):
    transport, calls = fake_transport
    monkeypatch.setenv("GNW_LOCAL_OLLAMA_MODEL", "missing:local")
    response = local_client(create_app(transport=transport)).post("/v1/plan", json={"task": "Plan a task"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "local_model_not_installed"
    assert [str(request.url) for request in calls] == [OLLAMA_TAGS_URL]


def test_remote_model_metadata_is_blocked(monkeypatch):
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, json={"models": [{"name": MODEL, "model": MODEL, "remote_host": "https://remote.example"}]})

    monkeypatch.setenv("GNW_LOCAL_OLLAMA_MODEL", MODEL)
    response = local_client(create_app(transport=httpx.MockTransport(handler))).post("/v1/plan", json={"task": "Plan a task"})

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "remote_model_blocked"
    assert calls == [OLLAMA_TAGS_URL]


def test_invalid_model_output_is_rejected(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return httpx.Response(200, json={"models": [{"name": MODEL, "model": MODEL}]})
        return httpx.Response(200, json={"message": {"content": "not JSON"}})

    monkeypatch.setenv("GNW_LOCAL_OLLAMA_MODEL", MODEL)
    response = local_client(create_app(transport=httpx.MockTransport(handler))).post("/v1/plan", json={"task": "Plan a task"})

    assert response.status_code == 502
    assert response.json()["error"]["code"] == "local_plan_invalid"


def test_invalid_request_is_rejected_without_model_call(fake_transport):
    transport, calls = fake_transport
    client = local_client(create_app(transport=transport))

    empty = client.post("/v1/plan", json={"task": "   "})
    caller_model = client.post("/v1/plan", json={"task": "Plan", "model": MODEL})

    assert empty.status_code == 400
    assert caller_model.status_code == 400
    assert calls == []


def test_non_loopback_client_is_rejected(fake_transport):
    transport, calls = fake_transport
    app = create_app(transport=transport)
    client = TestClient(app, client=("203.0.113.10", 43123))

    response = client.post("/v1/plan", json={"task": "Plan a task"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "loopback_only"
    assert calls == []
