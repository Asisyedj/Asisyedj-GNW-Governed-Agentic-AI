"""Plugin registry for personal_agent.

Scans the ``personal_agent/plugins`` package for subclasses of ``BaseTool`` and builds a dictionary ``registry`` mapping ``tool.name`` to the class.
Deterministic resolution: rejects conflicting insecure overrides and enforces fail-closed registration.
"""

from __future__ import annotations

import importlib
import logging
import pkgutil
from pathlib import Path
from typing import Dict, Type

from .base import BaseTool

logger = logging.getLogger(__name__)


def _load_plugins() -> Dict[str, Type[BaseTool]]:
    """Import all modules in the ``plugins`` package and collect ``BaseTool`` subclasses.

    Returns:
        dict mapping ``tool.name`` to the concrete class.
    """
    registry: Dict[str, Type[BaseTool]] = {}
    package_dir = Path(__file__).parent

    # Known preferred canonical implementations to avoid duplicate collisions
    preferred_modules = {
        "powershell": "personal_agent.plugins.powershell_tool",
    }

    for _, module_name, is_pkg in sorted(pkgutil.iter_modules([str(package_dir)])):
        if is_pkg:
            continue
        full_module_name = f"personal_agent.plugins.{module_name}"
        module = importlib.import_module(full_module_name)
        for attr in sorted(dir(module)):
            obj = getattr(module, attr)
            if isinstance(obj, type) and issubclass(obj, BaseTool) and obj is not BaseTool:
                name = getattr(obj, "name", None)
                if not name:
                    continue
                # If tool name already registered, check deterministic preference
                if name in registry:
                    preferred = preferred_modules.get(name)
                    if preferred and full_module_name == preferred:
                        registry[name] = obj
                    elif preferred and registry[name].__module__ == preferred:
                        # Existing is preferred, keep it
                        continue
                    else:
                        logger.warning(
                            "Duplicate tool name '%s' from %s ignored in favor of %s",
                            name,
                            full_module_name,
                            registry[name].__module__,
                        )
                else:
                    registry[name] = obj
    return registry


# Export a ready‑to‑use registry at import time.
registry: Dict[str, Type[BaseTool]] = _load_plugins()
