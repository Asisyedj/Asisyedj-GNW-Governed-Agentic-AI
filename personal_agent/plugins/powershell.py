"""PowerShell plugin for the personal agent.

Provides a `PowerShellTool` class that executes a PowerShell script and returns
stdout, stderr and an exit‑code flag. Execution is gated by an `enabled`
parameter – the user must have granted permission (as done earlier in the
project). The implementation uses the system's `pwsh` or `powershell`
executable and runs the command with a short timeout.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict

from .base import BaseTool


class PowerShellTool(BaseTool):
    """Execute a PowerShell script safely on Windows.

    The tool is *enabled* by default – the surrounding project already obtained
    user permission. The class accepts optional `timeout` (seconds) and a working
    directory `cwd`.
    """

    name = "powershell"
    description = "Execute an approved PowerShell script and capture its output."

    def __init__(self, *, enabled: bool = True, timeout: float = 30.0,
                 cwd: str | Path | None = None) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.enabled = enabled
        self.timeout = timeout
        self.cwd = Path(cwd).resolve(strict=True) if cwd else None

    def run(self, *, script: str) -> Dict[str, Any]:
        """Run ``script`` and return a dict with the execution result.

        Returns ``{"ok": bool, "returncode": int, "stdout": str, "stderr": str}``.
        """
        if not self.enabled:
            raise PermissionError("PowerShell execution is disabled")
        if not script.strip():
            raise ValueError("script must not be empty")

        executable = shutil.which("pwsh") or shutil.which("powershell")
        if executable is None:
            raise FileNotFoundError("PowerShell executable not found in PATH")

        # Wrap the script to enforce UTF‑8 output and stop on errors.
        wrapped = (
            "$ErrorActionPreference = 'Stop'; "
            "$OutputEncoding = [System.Text.UTF8Encoding]::new($false); "
            f"{script}"
        )

        proc = subprocess.run(
            [executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", wrapped],
            cwd=self.cwd,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=self.timeout,
            shell=False,
        )
        return {
            "ok": proc.returncode == 0,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
