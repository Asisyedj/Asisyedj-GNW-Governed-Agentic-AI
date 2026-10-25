"""Base class for all tool plugins.

Subclasses must implement a ``run`` method that accepts keyword arguments and
returns a ``dict`` with string keys (e.g. ``{"ok": True, "result": ...}``).
The ``name`` and ``description`` attributes are optional class attributes used
by the plugin registry for discovery.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseTool(ABC):
    """Abstract base for a tool plugin.

    Concrete plugins should define class attributes ``name`` and ``description``
    (or provide ``@property`` equivalents) and implement the ``run`` method.
    """

    @abstractmethod
    def run(self, *args, **kwargs) -> Dict[str, Any]:
        """Execute the tool.

        Returns a dictionary containing the tool's output. The exact schema is
        up to the implementation but should be JSON‑serialisable.
        """
        ...