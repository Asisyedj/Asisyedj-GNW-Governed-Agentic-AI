"""Isolated loopback GNW bridge with a local access key and DPAPI-backed upstream token."""
from __future__ import annotations
import hmac
import json
import os
import uvicorn
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from starlette.types import ASGIApp, Receive, Scope, Send
from gnw_secrets import get_bridge_key, get_session_token

# These 15 IDs were individually probed on 2026-10-26 and returned upstream HTTP 503.
# Keep the rest of the catalog untouched until it has equivalent live evidence.
DISABLED_MODELS = frozenset({
    "anthropic/claude-fable-5.1",
    "anthropic/claude-fable-5.1-thinking",
    "anthropic/claude-opus-5.5",
    "anthropic/claude-opus-5.5-thinking",
    "anthropic/claude-sonnet-5.5",
    "anthropic/claude-sonnet-5.5-thinking",
    "google/gemini-3.8-flash",
    "google/gemini-3.8-flash-thinking",
    "moonshot/kimi-k3-thinking",
    "openai/gpt-6-astra",
    "openai/gpt-6-astra-thinking",
    "openai/gpt-6.1-sol",
    "openai/gpt-6.1-sol-thinking",
    "perplexity/best",
    "perplexity/deep-research",
})

# Load the upstream token and bridge key, preferring environment overrides.
_SESSION_TOKEN = os.getenv("GNW_SESSION_TOKEN") or get_session_token()
_ACCESS_KEY = os.getenv("GNW_BRIDGE_KEY") or get_bridge_key()
os.environ["PERPLEXITY_SESSION_TOKEN"] = _SESSION_TOKEN

from perplexity_webui_scraper.api.app import create_app  # noqa: E402

class BridgeAuthGate:
    def __init__(self, app: ASGIApp, access_key: str, session_token: str):
        self.app = app
        self.access_key = access_key.encode("utf-8")
        self.session_token = session_token.encode("utf-8")

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        path = scope.get("path", "")
        # Health is local-only because the entire listener is loopback-bound.
        if path in {"/health", "/v1/health"}:
            # Handle health check directly - return ok status
            response = JSONResponse(content={"status": "ok"})
            await response(scope, receive, send)
            return
        if path.startswith("/v1/"):
            headers = list(scope.get("headers", []))
            auth = next((v for k, v in headers if k.lower() == b"authorization"), b"")
            supplied = auth[7:] if auth.lower().startswith(b"bearer ") else b""
            if not supplied or not hmac.compare_digest(supplied, self.access_key):
                response = JSONResponse(status_code=401, content={"error": "unauthorized"})
                await response(scope, receive, send)
                return
            # Replace the local bridge credential with the upstream session token only in-process.
            headers = [(k, v) for k, v in headers if k.lower() != b"authorization"]
            headers.append((b"authorization", b"Bearer " + self.session_token))
            scoped = dict(scope)
            scoped["headers"] = headers
            if path == "/v1/chat/completions" and scope.get("method") == "POST":
                await self._filter_chat_model(scoped, receive, send)
                return
            if path == "/v1/models" and scope.get("method") == "GET":
                await self._filter_model_catalog(scoped, receive, send)
                return
            await self.app(scoped, receive, send)
            return
        await self.app(scope, receive, send)

    async def _filter_chat_model(self, scope: Scope, receive: Receive, send: Send) -> None:
        request_messages = []
        body = bytearray()
        while True:
            message = await receive()
            request_messages.append(message)
            if message.get("type") != "http.request":
                break
            body.extend(message.get("body", b""))
            if not message.get("more_body", False):
                break

        try:
            payload = json.loads(body.decode("utf-8"))
            model_id = payload.get("model") if isinstance(payload, dict) else None
        except (UnicodeDecodeError, json.JSONDecodeError):
            model_id = None

        if isinstance(model_id, str) and model_id in DISABLED_MODELS:
            response = JSONResponse(
                status_code=404,
                content={"error": {"type": "invalid_request_error", "message": "model not found"}},
            )
            await response(scope, receive, send)
            return

        async def replay_receive():
            if request_messages:
                return request_messages.pop(0)
            return await receive()

        await self.app(scope, replay_receive, send)

    async def _filter_model_catalog(self, scope: Scope, receive: Receive, send: Send) -> None:
        response_start = None
        body_parts = []

        async def filter_send(message):
            nonlocal response_start
            if message.get("type") == "http.response.start" and message.get("status") == 200:
                headers = {key.lower(): value.lower() for key, value in message.get("headers", [])}
                content_type = headers.get(b"content-type", b"")
                content_encoding = headers.get(b"content-encoding", b"identity")
                if b"application/json" in content_type and content_encoding in (b"identity", b""):
                    response_start = message
                    return
            if response_start is not None and message.get("type") == "http.response.body":
                body_parts.append(message.get("body", b""))
                if message.get("more_body", False):
                    return
                original_body = b"".join(body_parts)
                try:
                    payload = json.loads(original_body.decode("utf-8"))
                    entries = payload.get("data") if isinstance(payload, dict) else None
                    if not isinstance(entries, list):
                        raise ValueError("unexpected catalog shape")
                    filtered = [
                        entry
                        for entry in entries
                        if not isinstance(entry, dict)
                        or not isinstance(entry.get("id"), str)
                        or entry.get("id") not in DISABLED_MODELS
                    ]
                except (UnicodeDecodeError, json.JSONDecodeError, ValueError, AttributeError):
                    await send(response_start)
                    await send({"type": "http.response.body", "body": original_body, "more_body": False})
                    response_start = None
                    body_parts.clear()
                    return

                if len(filtered) == len(entries):
                    output_body = original_body
                    output_start = response_start
                else:
                    payload["data"] = filtered
                    if "total" in payload:
                        payload["total"] = len(filtered)
                    output_body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
                    output_headers = [
                        (key, value)
                        for key, value in response_start.get("headers", [])
                        if key.lower() not in (b"content-length", b"etag", b"content-md5")
                    ]
                    output_headers.append((b"content-length", str(len(output_body)).encode("ascii")))
                    output_start = dict(response_start, headers=output_headers)
                await send(output_start)
                await send({"type": "http.response.body", "body": output_body, "more_body": False})
                response_start = None
                body_parts.clear()
                return
            await send(message)

        await self.app(scope, receive, filter_send)

# Create the base app from perplexity_webui_scraper
base_app = create_app()

# Wrap with our auth gate
app = FastAPI()
app.add_middleware(BridgeAuthGate, access_key=_ACCESS_KEY, session_token=_SESSION_TOKEN)

# Mount the base app at root
app.mount("/", base_app)

if __name__ == "__main__":
    # Explicit loopback binding prevents LAN/WAN access to this session-backed bridge.
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning", access_log=False)
