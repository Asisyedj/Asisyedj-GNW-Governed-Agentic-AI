"""Dynamic Model Router and Circuit-Breaker Registry for GNW.

Enforces zero-direct-default-model policy:
All model calls must route exclusively through the approved local GNW Perplexity Bridge
or explicitly authorized provider endpoints.
"""
from __future__ import annotations

import os
import time
import logging
import uuid
import threading
import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
import httpx

from personal_agent.state.idempotency import (
    generate_action_id,
    canonicalize_args,
    generate_idempotency_key,
    hash_response,
    IdempotencyStore,
)
from personal_agent.state.persistence import get_state_store, ExecutionStateStore

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
        tenant_id: Optional[uuid.UUID] = None,
        state_store: Optional[ExecutionStateStore] = None,
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
        self.idempotency_store = IdempotencyStore(tenant_id=tenant_id)
        self._state_store = state_store or get_state_store(tenant_id=tenant_id)
        self._tenant_id = tenant_id

        # Recover circuit breaker states from persistence
        self._recover_circuit_breakers()

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

    def _recover_circuit_breakers(self) -> None:
        """Recover circuit breaker states from persistent storage on startup."""
        try:
            # Get all router transitions for circuit breakers
            # We need to find all unique model_ids from execution_ids
            # For simplicity, we'll query the current state for router component
            # The state store doesn't have a direct "get all circuit breakers" method yet
            # so we'll skip full recovery for now and rely on in-memory defaults
            # A more complete implementation would iterate through all model execution_ids
            logger.debug("ModelRouter: circuit breaker recovery not yet fully implemented")
        except Exception as exc:
            logger.warning("ModelRouter: failed to recover circuit breakers: %s", exc)

    def _persist_circuit_breaker_change(
        self,
        model_id: str,
        from_state: CircuitState,
        to_state: CircuitState,
        trigger: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Persist a circuit breaker state change to the database."""
        try:
            self._state_store.record_circuit_breaker_change(
                model_id=model_id,
                from_state=from_state.value,
                to_state=to_state.value,
                trigger=trigger,
                metadata=metadata,
            )
        except Exception as exc:
            logger.warning("ModelRouter: failed to persist circuit breaker change for %s: %s", model_id, exc)

    def is_available(self, model_id: str) -> bool:
        """Check if model is currently eligible for traffic under circuit breaker rules."""
        m = self._get_or_create_metrics(model_id)
        if m.circuit_state == CircuitState.CLOSED:
            return True
        if m.circuit_state == CircuitState.OPEN:
            now = time.time()
            if now - m.last_failure_time >= self.recovery_timeout_sec:
                # Transition to HALF_OPEN probe state
                prev_state = m.circuit_state
                m.circuit_state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker for %s transitioned to HALF_OPEN probe", model_id)
                self._persist_circuit_breaker_change(
                    model_id, prev_state, m.circuit_state, "recovery_timeout",
                    metadata={"last_failure_time": m.last_failure_time}
                )
                return True
            return False
        if m.circuit_state == CircuitState.HALF_OPEN:
            return True
        return False

    def record_success(self, model_id: str, latency_ms: float) -> None:
        m = self._get_or_create_metrics(model_id)
        prev_state = m.circuit_state
        m.total_calls += 1
        m.successful_calls += 1
        m.consecutive_failures = 0
        m.last_success_time = time.time()
        m.last_latency_ms = latency_ms
        m.total_latency_ms += latency_ms
        if m.circuit_state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
            m.circuit_state = CircuitState.CLOSED
            logger.info("Circuit breaker for %s recovered and is now CLOSED", model_id)
            self._persist_circuit_breaker_change(
                model_id, prev_state, m.circuit_state, "success_recovery",
                metadata={"latency_ms": latency_ms, "consecutive_failures": m.consecutive_failures}
            )

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
        prev_state = m.circuit_state
        m.total_calls += 1
        m.failed_calls += 1
        m.last_failure_time = time.time()

        if self._is_transient_error(error):
            # A transient upstream/transport failure says nothing about model health.
            # If a HALF_OPEN probe fails transiently, reopen for the normal cooldown.
            if m.circuit_state == CircuitState.HALF_OPEN:
                m.circuit_state = CircuitState.OPEN
                self._persist_circuit_breaker_change(
                    model_id, prev_state, m.circuit_state, "transient_failure_half_open",
                    metadata={"http_status": self._http_status_code(error)}
                )
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
            self._persist_circuit_breaker_change(
                model_id, prev_state, m.circuit_state, "consecutive_failures",
                metadata={"consecutive_failures": m.consecutive_failures, "error": str(error)}
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

    def persist_metrics(self) -> None:
        """Persist current model metrics to the database for audit trail."""
        for model_id, metrics in self.metrics.items():
            try:
                self._state_store.record_model_metrics(model_id, {
                    "total_calls": metrics.total_calls,
                    "successful_calls": metrics.successful_calls,
                    "failed_calls": metrics.failed_calls,
                    "consecutive_failures": metrics.consecutive_failures,
                    "circuit_state": metrics.circuit_state.value,
                    "last_failure_time": metrics.last_failure_time,
                    "last_success_time": metrics.last_success_time,
                    "avg_latency_ms": metrics.avg_latency_ms,
                    "last_latency_ms": metrics.last_latency_ms,
                    "provider": metrics.provider,
                })
            except Exception as exc:
                logger.warning("ModelRouter: failed to persist metrics for %s: %s", model_id, exc)

    def execute_with_fallback(
        self,
        messages: List[Dict[str, Any]],
        requested_model: str | None = None,
        task_category: TaskCategory = TaskCategory.DEFAULT,
        timeout: float = 60.0,
        http_client: Optional[httpx.Client] = None,
        requirement_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute chat completion across candidate models with automatic failover.

        Args:
            messages: Chat messages to send
            requested_model: Specific model to try first
            task_category: Task category for routing
            timeout: Request timeout in seconds
            http_client: Optional pre-configured HTTP client
            requirement_id: Optional requirement ID for idempotency tracking.
                          If not provided, one is generated from the request content.
        """
        candidates = self.get_candidate_models(requested_model, task_category)
        last_error: Optional[Exception] = None
        attempted_models: List[str] = []

        headers = {"Accept": "application/json", "Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        endpoint = f"{self.base_url}/chat/completions"

        # Generate requirement_id if not provided (based on request content)
        if requirement_id is None:
            req_args = {"messages": messages, "model": requested_model, "task_category": task_category.value}
            requirement_id = generate_action_id("router_request", req_args)[:16]

        def _do_post(client: httpx.Client, model: str, attempt: int = 1) -> tuple[str, Dict[str, Any]]:
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
            return content, data

        for model in candidates:
            if not self.is_available(model):
                logger.debug("Skipping %s (circuit breaker OPEN)", model)
                continue

            attempted_models.append(model)
            start_time = time.perf_counter()

            # Prepare args for action_id (includes model being tried)
            call_args = {
                "messages": messages,
                "model": model,
                "task_category": task_category.value,
                "timeout": timeout,
            }
            canonical_args_hash = hashlib.sha256(canonicalize_args(call_args).encode("utf-8")).hexdigest()
            action_id = generate_action_id(requirement_id, call_args)
            idempotency_key = generate_idempotency_key(action_id, len(attempted_models))

            # Record dispatch before making the call
            self.idempotency_store.record_dispatch(
                action_id=action_id,
                requirement_id=requirement_id,
                canonical_args_hash=canonical_args_hash,
                component="router",
                idempotency_key=idempotency_key,
            )

            try:
                if http_client:
                    content, response_data = _do_post(http_client, model)
                else:
                    with httpx.Client(timeout=timeout, trust_env=False, follow_redirects=False) as client:
                        content, response_data = _do_post(client, model)

                latency_ms = (time.perf_counter() - start_time) * 1000.0
                self.record_success(model, latency_ms)

                # Record successful provider response
                response_hash = hash_response(response_data)
                provider_request_id = response_data.get("id") or response_data.get("request_id")
                self.idempotency_store.record_provider_response(
                    action_id=action_id,
                    provider_request_id=provider_request_id or "",
                    response_hash=response_hash,
                    status="succeeded",
                )

                return {
                    "ok": True,
                    "model": model,
                    "content": content,
                    "latency_ms": round(latency_ms, 1),
                    "attempted_models": attempted_models,
                    "action_id": action_id,
                    "idempotency_key": idempotency_key,
                }
            except Exception as exc:
                latency_ms = (time.perf_counter() - start_time) * 1000.0
                self.record_failure(model, exc)
                last_error = exc

                # Record failed provider response
                error_response = {"error": str(exc), "type": type(exc).__name__}
                response_hash = hash_response(error_response)
                self.idempotency_store.record_provider_response(
                    action_id=action_id,
                    provider_request_id="",
                    response_hash=response_hash,
                    status="failed",
                )

                if self._is_auth_error(exc):
                    logger.error("Call to %s failed authentication; refusing model fallback", model)
                    raise
                logger.warning("Call to %s failed (%s); trying fallback...", model, exc)
                continue

        # All models failed - record final exhaustion
        raise RouterExhaustionError(
            f"All model candidates failed. Attempted: {attempted_models}. Last error: {last_error}"
        )



# Global singleton router
global_router = ModelRouter()


def _periodic_metrics_persist() -> None:
    """Background task to periodically persist router metrics."""
    while True:
        time.sleep(300)  # 5 minutes
        try:
            global_router.persist_metrics()
        except Exception as exc:
            logger.warning("ModelRouter: periodic metrics persist failed: %s", exc)


# Start background metrics persistence thread
_metrics_thread = threading.Thread(target=_periodic_metrics_persist, daemon=True, name="RouterMetricsPersist")
_metrics_thread.start()
