"""Workspace-scoped UTF-8 file operations.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Literal

from .base import BaseTool


class FileTool(BaseTool):
    """Read and write files inside a workspace.

    Containment checks assume no hostile concurrent filesystem changes.
    """

    name = "file"
    description = "Read or write a UTF-8 file inside the workspace."

    def __init__(self, root: str | Path, *, allow_write: bool = False, max_bytes: int = 1_000_000) -> None:
        if max_bytes <= 0:
            raise ValueError("max_bytes must be positive")
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise NotADirectoryError(self.root)
        self.allow_write = allow_write
        self.max_bytes = max_bytes

    def _resolve(self, path: str) -> Path:
        """Resolve a workspace‑relative path and reject escapes."""
        relative = Path(path)
        if relative.is_absolute():
            raise ValueError("Use a workspace‑relative path")
        target = (self.root / relative).resolve()
        if not target.is_relative_to(self.root):
            raise PermissionError("Path escapes the workspace")
        return target

    def run(self, *, action: Literal["read", "write"], path: str, content: str | None = None) -> dict[str, Any]:
        """Read text or atomically replace a file; parents must exist."""
        if action not in {"read", "write"}:
            raise ValueError("action must be 'read' or 'write'")
        target = self._resolve(path)

        if action == "read":
            with target.open("rb") as handle:
                data = handle.read(self.max_bytes + 1)
            if len(data) > self.max_bytes:
                raise ValueError("File exceeds max_bytes")
            return {
                "ok": True,
                "path": str(target.relative_to(self.root)),
                "content": data.decode("utf-8"),
            }

        # write path
        if not self.allow_write:
            raise PermissionError("File writes are disabled")
        if content is None:
            raise ValueError("content is required for writes")
        data = content.encode("utf-8")
        if len(data) > self.max_bytes:
            raise ValueError("Content exceeds max_bytes")

        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
                temporary = Path(handle.name)
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

        return {
            "ok": True,
            "path": str(target.relative_to(self.root)),
            "bytes_written": len(data),
        }
