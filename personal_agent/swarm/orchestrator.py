"""Swarm orchestrator for GNW.

The SwarmCoordinator loads the set of *eligible* (healthy) models from the
global health registry and provides a convenience method to run a single prompt
across all of them.  Each model is invoked via the existing ``global_router``
with the standard fallback logic, so the coordinator inherits the circuit‑breaker
behaviour and retry semantics already present in the router.
"""

import logging
from typing import Dict, List

from personal_agent.agent.router import (
    global_router,
    TaskCategory,
)
from personal_agent.health.model_health import global_health_registry, HealthState

logger = logging.getLogger(__name__)


class SwarmCoordinator:
    """Execute a prompt on a fleet of healthy models.

    Attributes
    ----------
    models: List[str]
        Model IDs selected from the health registry (default: ``HEALTHY``).
    """

    def __init__(self, min_state: HealthState = HealthState.HEALTHY):
        # Resolve the set of models that satisfy the requested health threshold.
        self.models: List[str] = global_health_registry.eligible_models(min_state)
        logger.info("SwarmCoordinator initialised with %d models", len(self.models))

    def run_task(
        self,
        prompt: str,
        timeout: float = 15.0,
        task_category: TaskCategory = TaskCategory.DEFAULT,
    ) -> Dict[str, Dict]:
        """Run *prompt* on every model in ``self.models``.

        Parameters
        ----------
        prompt: str
            The user‑visible instruction that will be sent as the sole message
            to each model.
        timeout: float, optional
            Per‑model HTTP timeout passed to the router (default 15 s).
        task_category: TaskCategory, optional
            Allows callers to influence the routing table; defaults to ``DEFAULT``.

        Returns
        -------
        Dict[str, Dict]
            Mapping ``model_id → router result dict`` as returned by
            ``global_router.execute_with_fallback``.  The result contains keys
            ``ok``, ``model``, ``content``, ``latency_ms`` and ``attempted_models``.
        """
        results: Dict[str, Dict] = {}
        messages = [{"role": "user", "content": prompt}]
        for model_id in self.models:
            try:
                logger.debug("Swarm invoking model %s", model_id)
                res = global_router.execute_with_fallback(
                    messages=messages,
                    requested_model=model_id,
                    task_category=task_category,
                    timeout=timeout,
                )
                results[model_id] = res
            except Exception as exc:  # pragma: no cover – unexpected failures are logged
                logger.error("Swarm model %s failed: %s", model_id, exc)
                results[model_id] = {"ok": False, "error": str(exc)}
        logger.info("Swarm completed %d models", len(results))
        return results
