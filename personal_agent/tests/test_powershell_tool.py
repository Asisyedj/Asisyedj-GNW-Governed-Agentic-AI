"""Tests for PowerShellTool.

We mock ``subprocess.run`` to avoid executing real PowerShell commands.
"""

import subprocess
from unittest import mock

from personal_agent.plugins.powershell_tool import PowerShellTool


def test_powershell_tool_runs_script_success():
    mock_result = subprocess.CompletedProcess(args=["pwsh"], returncode=0, stdout="OK", stderr="")
    with mock.patch("subprocess.run", return_value=mock_result) as m_run:
        tool = PowerShellTool(enabled=True, timeout=5)
        res = tool.run(script="Write-Output 'Hello'")
        assert res["ok"] is True
        assert res["stdout"] == "OK"
        m_run.assert_called_once()

def test_powershell_tool_disabled_raises():
    tool = PowerShellTool(enabled=False)
    try:
        tool.run(script="Get-Date")
        assert False, "Expected PermissionError"
    except PermissionError:
        pass
