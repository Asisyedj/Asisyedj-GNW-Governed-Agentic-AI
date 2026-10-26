"""Personal agent package marker.

Automatic bootstrap for bridge supervision and approval store.

This ensures the BridgeSupervisor singleton starts its monitoring thread as
soon as the ``personal_agent`` package is imported, allowing the supervisor to
detect an already‑running bridge process, perform health/auth checks, and
manage restarts. Also initializes the approval store for the default tenant.
"""

import logging
import os
import uuid
from .bridge.supervisor import global_bridge_supervisor
from .auth.approval_store import ApprovalStore, get_approval_store

_logger = logging.getLogger(__name__)

# Default tenant ID (can be overridden via GNW_TENANT_ID env var)
_DEFAULT_TENANT_ID = uuid.UUID(os.environ.get("GNW_TENANT_ID", "00000000-0000-0000-0000-000000000001"))

_approval_store: ApprovalStore | None = None
_approval_store_lock = __import__("threading").Lock()


def _bootstrap_supervisor():
    try:
        global_bridge_supervisor.start()
        _logger.info("BridgeSupervisor started via package autoload")
    except Exception as exc:  # pragma: no cover – defensive
        _logger.error("Failed to start BridgeSupervisor: %s", exc)


def _bootstrap_approval_store():
    """Initialize the default approval store for the tenant."""
    global _approval_store
    try:
        dsn = os.environ.get("GNW_PG_DSN")
        if dsn:
            _approval_store = ApprovalStore(_DEFAULT_TENANT_ID, dsn=dsn)
            _logger.info("ApprovalStore initialized for tenant %s", _DEFAULT_TENANT_ID)
        else:
            _logger.warning("GNW_PG_DSN not set; ApprovalStore not initialized (use get_approval_store() manually)")
    except Exception as exc:  # pragma: no cover – defensive
        _logger.error("Failed to initialize ApprovalStore: %s", exc)


def get_default_approval_store() -> ApprovalStore | None:
    """Get the default approval store (initialized on first import if DSN available)."""
    global _approval_store
    if _approval_store is None:
        with _approval_store_lock:
            if _approval_store is None:
                _bootstrap_approval_store()
    return _approval_store


def set_default_approval_store(store: ApprovalStore) -> None:
    """Set the default approval store (for testing)."""
    global _approval_store
    _approval_store = store


# Initialise exactly once per interpreter session.
_bootstrap_supervisor()
_bootstrap_approval_store()

__all__ = [
    "ApprovalStore",
    "get_approval_store",
    "get_default_approval_store",
    "set_default_approval_store",
]

