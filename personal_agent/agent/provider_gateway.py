"""Separate, loopback-only gateway for documented Perplexity APIs.

This module does not modify or replace the legacy browser-session scraper.
It exposes official Orchestrator, Agent, and Search routes plus a local custom
selector. Desktop-control at `/v1/computer` remains unavailable; `/v1/computer/plan`
is text-only and never acts on a device. No public Computer-control API is assumed.

Start locally with: python -m personal_agent.agent.provider_gateway
Required server-side secret: PERPLEXITY_API_KEY (never logged or returned).
"""
from __future__ import annotations

import json
import os
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

API_ROOT = "https://api.perplexity.ai"
REQUEST_TIMEOUT_SECONDS = 60.0
_ROUTE_PATHS = {
    "orchestrator": "/orchestrator/v1/chat/completions",
    "agent": "/v1/agent",
    "search": "/search",
}
_LOOPBACK_HOSTS = {"127.0.0.1", "::1", "localhost"}
_COMPUTER_PLAN_SYSTEM_PROMPT = (
    "You are a text-only task planner, not a computer-control agent. Propose a concise, "
    "human-reviewable plan for the user's task. You cannot see or operate the user's "
    "desktop, browser, or Perplexity Computer mode; never claim to have executed an action. "
    "Do not request credentials, cookies, session tokens, or hidden browser data. Do not "
    "recommend attacks, bypasses, private-protocol reverse engineering, or arbitrary scripts. "
    "Clearly label assumptions and unknowns, and flag external, destructive, financial, or "
    "security-sensitive steps for explicit human review."
)
_MAX_COMPUTER_TASK_LENGTH = 4000


def _validate_payload(route: str, payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="Request body must be a JSON object.")

    if route == "orchestrator":
        if not isinstance(payload.get("model"), str) or not payload["model"].strip():
            raise HTTPException(status_code=400, detail="Orchestrator requires a non-empty model.")
        if not isinstance(payload.get("messages"), list) or not payload["messages"]:
            raise HTTPException(status_code=400, detail="Orchestrator requires a non-empty messages array.")
        if payload.get("stream") is True:
            raise HTTPException(status_code=400, detail="Streaming is not enabled on this local gateway.")
    elif route == "agent":
        if not isinstance(payload.get("model"), str) or not payload["model"].strip():
            raise HTTPException(status_code=400, detail="Agent API requires a non-empty model.")
        if "input" not in payload or payload["input"] in (None, "", []):
            raise HTTPException(status_code=400, detail="Agent API requires non-empty input.")
        if payload.get("stream") is True:
            raise HTTPException(status_code=400, detail="Streaming is not enabled on this local gateway.")
    elif route == "search":
        if not isinstance(payload.get("query"), str) or not payload["query"].strip():
            raise HTTPException(status_code=400, detail="Search API requires a non-empty query.")
    else:
        raise HTTPException(status_code=400, detail="Unknown route selection.")

    # The upstream URL is fixed in code. Caller-provided URLs or auth headers are
    # never accepted, preventing this gateway from becoming an arbitrary proxy.
    return payload


def create_app(*, transport: httpx.AsyncBaseTransport | None = None) -> FastAPI:
    """Create the local API gateway; optional transport exists for offline tests."""
    app = FastAPI(title="GNW Official Perplexity API Gateway", version="0.1.0")

    @app.middleware("http")
    async def require_loopback(request: Request, call_next):
        client_host = request.client.host if request.client else ""
        if client_host not in _LOOPBACK_HOSTS:
            return JSONResponse(
                status_code=403,
                content={"error": {"code": "loopback_only", "message": "This gateway accepts local requests only."}},
            )
        return await call_next(request)

    async def forward(route: str, raw_payload: Any) -> JSONResponse:
        payload = _validate_payload(route, raw_payload)
        api_key = os.environ.get("PERPLEXITY_API_KEY", "").strip()
        if not api_key:
            return JSONResponse(
                status_code=503,
                content={"error": {"code": "api_key_not_configured", "message": "PERPLEXITY_API_KEY is not configured."}},
            )

        url = API_ROOT + _ROUTE_PATHS[route]
        try:
            async with httpx.AsyncClient(
                transport=transport,
                timeout=REQUEST_TIMEOUT_SECONDS,
                trust_env=False,
                follow_redirects=False,
            ) as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Accept": "application/json",
                        "Content-Type": "application/json",
                    },
                )
        except httpx.TimeoutException:
            return JSONResponse(
                status_code=504,
                content={"error": {"code": "upstream_timeout", "message": "Perplexity API request timed out."}},
            )
        except httpx.HTTPError:
            return JSONResponse(
                status_code=502,
                content={"error": {"code": "upstream_transport_error", "message": "Could not reach the Perplexity API."}},
            )

        try:
            body = response.json()
        except ValueError:
            body = {"error": {"code": "non_json_upstream_response", "message": "Perplexity returned a non-JSON response."}}

        headers: dict[str, str] = {}
        retry_after = response.headers.get("retry-after")
        if retry_after:
            headers["Retry-After"] = retry_after
        return JSONResponse(status_code=response.status_code, content=body, headers=headers)

    @app.post("/v1/orchestrator/chat/completions")
    async def orchestrator_chat(request: Request) -> JSONResponse:
        return await forward("orchestrator", await request.json())

    @app.post("/v1/agent")
    async def agent(request: Request) -> JSONResponse:
        return await forward("agent", await request.json())

    @app.post("/v1/search")
    async def search(request: Request) -> JSONResponse:
        return await forward("search", await request.json())

    @app.post("/v1/custom/dispatch")
    async def custom_dispatch(request: Request) -> JSONResponse:
        body = await request.json()
        if not isinstance(body, dict):
            raise HTTPException(status_code=400, detail="Request body must be a JSON object.")
        selected = body.get("route")
        payload = body.get("payload")
        if selected not in _ROUTE_PATHS:
            raise HTTPException(status_code=400, detail="route must be orchestrator, agent, or search.")
        return await forward(selected, payload)

    @app.post("/v1/computer/plan")
    async def computer_task_plan(request: Request) -> JSONResponse:
        try:
            body = await request.json()
        except ValueError:
            raise HTTPException(status_code=400, detail="Send a JSON object with model and task fields.")
        if not isinstance(body, dict) or set(body) != {"model", "task"}:
            raise HTTPException(status_code=400, detail="Only model and task fields are accepted.")
        model = body.get("model")
        task = body.get("task")
        if not isinstance(model, str) or not model.strip():
            raise HTTPException(status_code=400, detail="A non-empty Perplexity model is required.")
        if not isinstance(task, str) or not task.strip():
            raise HTTPException(status_code=400, detail="A non-empty task is required.")
        if len(task) > _MAX_COMPUTER_TASK_LENGTH:
            raise HTTPException(status_code=413, detail=f"Task must be at most {_MAX_COMPUTER_TASK_LENGTH} characters.")

        upstream = await forward(
            "orchestrator",
            {
                "model": model.strip(),
                "messages": [
                    {"role": "system", "content": _COMPUTER_PLAN_SYSTEM_PROMPT},
                    {"role": "user", "content": task.strip()},
                ],
                "stream": False,
            },
        )
        if upstream.status_code != 200:
            return upstream
        try:
            upstream_body = json.loads(upstream.body.decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return JSONResponse(
                status_code=502,
                content={"error": {"code": "invalid_plan_response", "message": "Perplexity returned an invalid plan response."}},
            )
        choices = upstream_body.get("choices") if isinstance(upstream_body, dict) else None
        first_choice = choices[0] if isinstance(choices, list) and choices else None
        message = first_choice.get("message") if isinstance(first_choice, dict) else None
        plan_text = message.get("content") if isinstance(message, dict) else None
        if not isinstance(plan_text, str) or not plan_text.strip():
            return JSONResponse(
                status_code=502,
                content={"error": {"code": "invalid_plan_response", "message": "Perplexity returned no text plan."}},
            )
        return JSONResponse(
            status_code=200,
            content={
                "mode": "computer_task_plan_only",
                "status": "pending_human_review",
                "executed": False,
                "approval_required": True,
                "untrusted_model_output": True,
                "model": model.strip(),
                "plan_text": plan_text,
            },
        )

    @app.post("/v1/computer")
    async def computer_control() -> JSONResponse:
        return JSONResponse(
            status_code=501,
            content={
                "error": {
                    "code": "computer_control_api_unavailable",
                    "message": "No documented Perplexity Computer-control API is configured. No private app protocol will be emulated.",
                }
            },
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "mode": "loopback-only", "upstream": "official-perplexity-api"}

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8010, log_level="warning")
