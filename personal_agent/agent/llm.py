"""Perplexity bridge client; deliberately does not import Antigravity/Gemini SDKs.

The bridge is expected to expose an OpenAI-compatible POST /chat/completions endpoint.
Defaults match the local development bridge; configure via environment variables.
"""
from __future__ import annotations

import os
from typing import Any, Optional

import httpx

from .router import (
    DEFAULT_BRIDGE_URL,
    ModelRouter,
    PolicyViolationError,
    RouterExhaustionError,
    TaskCategory,
    global_router,
)

DEFAULT_BASE_URL = DEFAULT_BRIDGE_URL
DEFAULT_MODEL = "perplexity/deep-research"


class LLMConfigurationError(RuntimeError):
    """The Perplexity bridge configuration is invalid."""


class LLMBridgeError(RuntimeError):
    """The Perplexity bridge could not provide a valid response."""


class LLMWrapper:
    def __init__(
        self,
        *,
        base_url: str | None = None,
        model_name: str | None = None,
        api_key: str | None = None,
        timeout: float | None = None,
        router: Optional[ModelRouter] = None,
    ) -> None:
        self.base_url = (base_url or os.getenv("PERPLEXITY_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        self.model_name = model_name or os.getenv("PERPLEXITY_MODEL", DEFAULT_MODEL)
        self.api_key = api_key if api_key is not None else os.getenv("PERPLEXITY_API_KEY", "")
        self.timeout = timeout or float(os.getenv("PERPLEXITY_TIMEOUT_SECONDS", "90"))
        self.router = router or global_router

        if not self.base_url.startswith(("http://127.0.0.1", "http://localhost", "https://")):
            raise LLMConfigurationError("PERPLEXITY_BASE_URL must use localhost HTTP or HTTPS.")
        if not self.model_name.strip():
            raise LLMConfigurationError("PERPLEXITY_MODEL must not be empty.")
        if self.timeout <= 0:
            raise LLMConfigurationError("PERPLEXITY_TIMEOUT_SECONDS must be positive.")

    def call(self, messages: list[dict[str, Any]], stream: bool = False) -> str:
        if stream:
            raise NotImplementedError("Streaming is not implemented in this bridge wrapper.")
        if not isinstance(messages, list) or not messages:
            raise ValueError("messages must be a non-empty list.")
        payload = {"model": self.model_name, "messages": messages, "stream": False}
        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        endpoint = f"{self.base_url}/chat/completions"
        try:
            with httpx.Client(timeout=self.timeout, trust_env=False, follow_redirects=False) as client:
                response = client.post(endpoint, json=payload, headers=headers)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise LLMBridgeError(f"Perplexity bridge request failed: {type(exc).__name__}") from exc

        # OpenAI-compatible response.
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMBridgeError("Bridge returned an unsupported response shape.") from exc
        if not isinstance(content, str):
            raise LLMBridgeError("Bridge response content was not text.")
        return content

    def call_routed(
        self,
        messages: list[dict[str, Any]],
        task_category: TaskCategory = TaskCategory.DEFAULT,
        model_name: str | None = None,
    ) -> dict[str, Any]:
        """Execute chat completion using dynamic routing with circuit-breaker and fallback."""
        if not isinstance(messages, list) or not messages:
            raise ValueError("messages must be a non-empty list.")
        target_model = model_name or self.model_name
        return self.router.execute_with_fallback(
            messages=messages,
            requested_model=target_model,
            task_category=task_category,
            timeout=self.timeout,
        )


_llm = LLMWrapper()


def call_llm(messages: list[dict[str, Any]]) -> str:
    return _llm.call(messages)


def call_llm_with_model(messages: list[dict[str, Any]], model_name: str | None = None) -> str:
    """Call the Perplexity bridge using an optional explicit model.

    If *model_name* is provided, a fresh LLMWrapper instance is created with that model;
    otherwise the global singleton ``_llm`` (configured via environment variables) is used.
    """
    if model_name:
        wrapper = LLMWrapper(model_name=model_name)
    else:
        wrapper = _llm
    return wrapper.call(messages)


def call_llm_routed(
    messages: list[dict[str, Any]],
    task_category: TaskCategory = TaskCategory.DEFAULT,
    model_name: str | None = None,
) -> dict[str, Any]:
    """Call the bridge using the dynamic model router with automated fallback."""
    return _llm.call_routed(messages, task_category=task_category, model_name=model_name)
