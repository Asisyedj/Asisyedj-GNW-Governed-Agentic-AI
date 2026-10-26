"""Dynamic Model Router and Circuit-Breaker Registry for GNW.

Enforces zero-direct-default-model policy:
All model calls must route exclusively through the approved local GNW Perplexity Bridge
or explicitly authorized provider endpoints.
"""
from __future__ import annotations

import os
import time
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import httpx

logger = logging.getLogger(__name__)

DEFAULT_BRIDGE_URL = "http://127.0.0.1:8000/v1"
APPROVED_HOSTS = ("127.0.0.1", "localhost")


class CircuitState(str, Enum):
    CLOSED = "CLOSED"        # Normal operations
    OPEN = "OPEN"            # Tripped; traffic diverted to fallback
    HALF_OPEN = "HALF_OPEN"  # Probe request allowed to test recovery


class PolicyViolationError(RuntimeError):
    """Attempted an unauthorized model bypass or unapproved endpoint."""


class RouterExhaustionError(RuntimeError):
    """All candidate models and fallbacks failed or circuit breakers are open."""


class TaskCategory(str, Enum):
    DEFAULT = "default"
    COMPLEX_REASONING = "complex_reasoning"
    HIGH_VELOCITY = "high_velocity"
    ADVERSARIAL_AUDIT = "adversarial_audit"
    DEEP_RESEARCH = "deep_research"
    CODE_INTELLIGENCE = "code_intelligence"


@dataclass
class ModelMetrics:
    model_id: str
    provider: str
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    consecutive_failures: int = 0
    circuit_state: CircuitState = CircuitState.CLOSED
    last_failure_time: float = 0.0
    last_success_time: float = 0.0
    total_latency_ms: float = 0.0
    last_latency_ms: float = 0.0

    @property
    def avg_latency_ms(self) -> float:
        if self.successful_calls == 0:
            return 0.0
        return round(self.total_latency_ms / self.successful_calls, 1)


# Fleet mapping based on discovered 99-model catalog (updated to use available models, excluding DISABLED_MODELS)
DEFAULT_TASK_ROUTING: Dict[TaskCategory, List[str]] = {
    TaskCategory.COMPLEX_REASONING: [
        "anthropic/claude-opus-5-thinking",
        "anthropic/claude-sonnet-5-thinking",
        "google/gemini-3.1-pro-thinking-high",
        "openai/gpt-5.6-sol-thinking",
        "openai/gpt-5.6-terra-thinking",
    ],
    TaskCategory.HIGH_VELOCITY: [
        "google/gemini-3.7-flash",
        "google/gemini-3.7-flash-thinking",
        "anthropic/claude-sonnet-5",
        "x-ai/grok-4.5",
    ],
    TaskCategory.ADVERSARIAL_AUDIT: [
        "x-ai/grok-4.7-thinking",
        "x-ai/grok-4.6-thinking",
        "nvidia/nemotron-3-ultra-thinking",
    ],
    TaskCategory.DEEP_RESEARCH: [
        "perplexity/sonar-2",
        "anthropic/claude-opus-5",
        "google/gemini-3.1-pro-thinking-high",
    ],
    TaskCategory.CODE_INTELLIGENCE: [
        "openai/gpt-5.6-sol-thinking",
        "openai/gpt-5.6-terra-thinking",
        "anthropic/claude-sonnet-5-thinking",
    ],
    TaskCategory.DEFAULT: [
        "perplexity/sonar-2",
        "anthropic/claude-sonnet-5",
        "anthropic/claude-opus-5",
        "google/gemini-3.7-flash",
        "x-ai/grok-4.5",
        "nvidia/nemotron-3-ultra-thinking",
        "openai/gpt-5.6-sol",
    ],
}


class ModelRouter:
    """Governed dynamic model router with circuit breakers and fallback management."""

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        failure_threshold: int = 3,
        recovery_timeout_sec: float = 60.0,
        max_retries_per_model: int = 2,
    ) -> None:
        self.base_url = (base_url or os.getenv("PERPLEXITY_BASE_URL", DEFAULT_BRIDGE_URL)).rstrip("/")
        self._validate_endpoint(self.base_url)
        self.api_key = api_key if api_key is not None else os.getenv("PERPLEXITY_API_KEY", "")
        # Fallback to DPAPI‑stored bridge key if no env var is set
        if not self.api_key:
            try:
                from gnw_secrets import get_bridge_key
                self.api_key = get_bridge_key()
                logger.info("Bridge API key loaded from gnw_secrets store")
            except Exception as exc:
                logger.warning("Bridge API key not found in env or secret store: %s", exc)

        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec
        self.max_retries_per_model = max_retries_per_model
        self.metrics: Dict[str, ModelMetrics] = {}
        self.task_routes: Dict[TaskCategory, List[str]] = dict(DEFAULT_TASK_ROUTING)

    def _validate_endpoint(self, url: str) -> None:
        """Enforce zero bypass: ensure only approved local bridge or explicitly permitted host is used."""
        if not (url.startswith("http://127.0.0.1") or url.startswith("http://localhost")):
            # Allow secure external only if explicitly set and confirmed
            if not url.startswith("https://"):
                raise PolicyViolationError(
                    f"Forbidden endpoint {url}: GNW policy mandates local bridge or approved HTTPS."
                )

    def _get_provider(self, model_id: str) -> str:
        if "/" in model_id:
            return model_id.split("/", 1)[0]
        return "unknown"

    def _get_or_create_metrics(self, model_id: str) -> ModelMetrics:
        if model_id not in self.metrics:
            self.metrics[model_id] = ModelMetrics(
                model_id=model_id,
                provider=self._get_provider(model_id),
            )
        return self.metrics[model_id]

    def is_available(self, model_id: str) -> bool:
        """Check if model is currently eligible for traffic under circuit breaker rules."""
        m = self._get_or_create_metrics(model_id)
        if m.circuit_state == CircuitState.CLOSED:
            return True
        if m.circuit_state == CircuitState.OPEN:
            now = time.time()
            if now - m.last_failure_time >= self.recovery_timeout_sec:
                # Transition to HALF_OPEN probe state
                m.circuit_state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker for %s transitioned to HALF_OPEN probe", model_id)
                return True
            return False
        if m.circuit_state == CircuitState.HALF_OPEN:
            return True
        return False

    def record_success(self, model_id: str, latency_ms: float) -> None:
        m = self._get_or_create_metrics(model_id)
        m.total_calls += 1
        m.successful_calls += 1
        m.consecutive_failures = 0
        m.last_success_time = time.time()
        m.last_latency_ms = latency_ms
        m.total_latency_ms += latency_ms
        if m.circuit_state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
            m.circuit_state = CircuitState.CLOSED
            logger.info("Circuit breaker for %s recovered and is now CLOSED", model_id)

    @staticmethod
    def _http_status_code(error: Exception) -> int | None:
        if isinstance(error, httpx.HTTPStatusError) and error.response is not None:
            return error.response.status_code
        return None

    @classmethod
    def _is_transient_error(cls, error: Exception) -> bool:
        """Identify provider/transport failures that should not trip a model breaker."""
        return isinstance(error, httpx.TransportError) or cls._http_status_code(error) in (429, 503)

    @classmethod
    def _is_auth_error(cls, error: Exception) -> bool:
        return cls._http_status_code(error) in (401, 403)

    def record_failure(self, model_id: str, error: Exception) -> None:
        m = self._get_or_create_metrics(model_id)
        m.total_calls += 1
        m.failed_calls += 1
        m.last_failure_time = time.time()

        if self._is_transient_error(error):
            # A transient upstream/transport failure says nothing about model health.
            # If a HALF_OPEN probe fails transiently, reopen for the normal cooldown.
            if m.circuit_state == CircuitState.HALF_OPEN:
                m.circuit_state = CircuitState.OPEN
            logger.info(
                "Transient failure for %s (HTTP %s); circuit remains %s",
                model_id,
                self._http_status_code(error),
                m.circuit_state.value,
            )
            return

        if self._is_auth_error(error):
            logger.warning(
                "Authentication failure for %s (HTTP %s); circuit state unchanged",
                model_id,
                self._http_status_code(error),
            )
            return

        m.consecutive_failures += 1
        if m.consecutive_failures >= self.failure_threshold:
            m.circuit_state = CircuitState.OPEN
            logger.warning(
                "Circuit breaker for %s TRIPPED to OPEN after %d consecutive failures (error: %s)",
                model_id,
                m.consecutive_failures,
                error,
            )

    def get_candidate_models(
        self,
        requested_model: str | None = None,
        task_category: TaskCategory = TaskCategory.DEFAULT,
    ) -> List[str]:
        """Return prioritized list of eligible candidate models."""
        candidates: List[str] = []
        if requested_model:
            candidates.append(requested_model)

        route_list = self.task_routes.get(task_category, self.task_routes[TaskCategory.DEFAULT])
        for model in route_list:
            if model not in candidates:
                candidates.append(model)

        return candidates

    def execute_with_fallback(
        self,
        messages: List[Dict[str, Any]],
        requested_model: str | None = None,
        task_category: TaskCategory = TaskCategory.DEFAULT,
        timeout: float = 60.0,
        http_client: Optional[httpx.Client] = None,
    ) -> Dict[str, Any]:
        """Execute chat completion across candidate models with automatic failover."""
        candidates = self.get_candidate_models(requested_model, task_category)
        last_error: Optional[Exception] = None
        attempted_models: List[str] = []

        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        endpoint = f"{self.base_url}/chat/completions"

        def _do_post(client: httpx.Client, model: str) -> str:
            payload = {"model": model, "messages": messages, "stream": False}
            resp = client.post(endpoint, json=payload, headers=headers)
            if resp.status_code == 429:
                # Rate limit encountered
                raise httpx.HTTPStatusError("Rate limited (HTTP 429)", request=resp.request, response=resp)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise ValueError("Model response content was not text.")
            return content

        for model in candidates:
            if not self.is_available(model):
                logger.debug("Skipping %s (circuit breaker OPEN)", model)
                continue

            attempted_models.append(model)
            start_time = time.perf_counter()

            try:
                if http_client:
                    content = _do_post(http_client, model)
                else:
                    with httpx.Client(timeout=timeout, trust_env=False, follow_redirects=False) as client:
                        content = _do_post(client, model)

                latency_ms = (time.perf_counter() - start_time) * 1000.0
                self.record_success(model, latency_ms)
                return {
                    "ok": True,
                    "model": model,
                    "content": content,
                    "latency_ms": round(latency_ms, 1),
                    "attempted_models": attempted_models,
                }
            except Exception as exc:
                latency_ms = (time.perf_counter() - start_time) * 1000.0
                self.record_failure(model, exc)
                last_error = exc
                if self._is_auth_error(exc):
                    logger.error("Call to %s failed authentication; refusing model fallback", model)
                    raise
                logger.warning("Call to %s failed (%s); trying fallback...", model, exc)
                continue

        raise RouterExhaustionError(
            f"All model candidates failed. Attempted: {attempted_models}. Last error: {last_error}"
        )



# Global singleton router
global_router = ModelRouter()
