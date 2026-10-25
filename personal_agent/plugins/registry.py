"""Plugin registry for personal_agent.

Scans the ``personal_agent/plugins`` package for subclasses of ``BaseTool`` and builds a dictionary ``registry`` mapping ``tool.name`` to the class.

The registry is imported by the planner so that the LLM can request a tool by name.
"""

from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Dict, Type

from .base import BaseTool


def _load_plugins() -> Dict[str, Type[BaseTool]]:
    """Import all modules in the ``plugins`` package and collect ``BaseTool`` subclasses.

    Returns:
        dict mapping ``tool.name`` to the concrete class.
    """
    registry: Dict[str, Type[BaseTool]] = {}
    package_dir = Path(__file__).parent
    for _, module_name, is_pkg in pkgutil.iter_modules([str(package_dir)]):
        if is_pkg:
            continue  # No nested packages expected
        module = importlib.import_module(f"personal_agent.plugins.{module_name}")
        for attr in dir(module):
            obj = getattr(module, attr)
            if isinstance(obj, type) and issubclass(obj, BaseTool) and obj is not BaseTool:
                instance = obj  # class, not instantiated yet
                name = getattr(instance, "name", None)
                if name:
                    registry[name] = instance
    return registry

# Export a ready‑to‑use registry at import time.
registry: Dict[str, Type[BaseTool]] = _load_plugins()
