"""PowerShell execution tool.

Arbitrary scripts are dangerous. This tool is disabled by default and is only
enabled by the planner after the exact script/arguments are shown to the user
and the user explicitly approves them. This is not an OS sandbox.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

from .base import BaseTool


class PowerShellTool(BaseTool):
    name = "powershell"
    description = "Execute an explicitly approved PowerShell script."

    def __init__(self, *, enabled: bool = False, timeout: float = 15.0, cwd: str | Path | None = None) -> None:
        if timeout <= 0:
            raise ValueError("timeout must be positive")
        self.enabled = enabled
        self.timeout = timeout
        self.cwd = Path(cwd).resolve(strict=True) if cwd else None

    def run(self, *, script: str) -> dict[str, Any]:
        if not self.enabled:
            raise PermissionError("PowerShell execution is disabled; explicit approval is required")
        if not isinstance(script, str) or not script.strip():
            raise ValueError("script must be a non-empty string")
        executable = shutil.which("pwsh") or shutil.which("powershell")
        if executable is None:
            raise FileNotFoundError("Install PowerShell or add it to PATH")
        wrapped = (
            "$ErrorActionPreference = 'Stop'; "
            "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false);\n"
            + script
        )
        result = subprocess.run(
            [executable, "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", wrapped],
            shell=False,
            cwd=self.cwd,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            timeout=self.timeout,
            check=False,
        )
        return {
            "ok": result.returncode == 0,
            "returncode": result.returncode,
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
