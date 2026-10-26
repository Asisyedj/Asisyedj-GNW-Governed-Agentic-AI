"""Personal agent package marker.

Automatic bootstrap for bridge supervision.

This ensures the BridgeSupervisor singleton starts its monitoring thread as
soon as the ``personal_agent`` package is imported, allowing the supervisor to
detect an already‑running bridge process, perform health/auth checks, and
manage restarts.
"""

import logging
from .bridge.supervisor import global_bridge_supervisor

_logger = logging.getLogger(__name__)

def _bootstrap_supervisor():
    try:
        global_bridge_supervisor.start()
        _logger.info("BridgeSupervisor started via package autoload")
    except Exception as exc:  # pragma: no cover – defensive
        _logger.error("Failed to start BridgeSupervisor: %s", exc)

# Initialise exactly once per interpreter session.
_bootstrap_supervisor()

