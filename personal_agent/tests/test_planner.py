from unittest import mock

from personal_agent.agent import llm
from personal_agent.agent.planner import plan
from personal_agent.plugins.powershell_tool import PowerShellTool


def fake_tool_response(_messages):
    return '{"tool": "powershell", "args": {"script": "Write-Output test"}}'


def test_planner_requires_approval_by_default(monkeypatch):
    monkeypatch.setattr(llm, "call_llm", fake_tool_response)
    with mock.patch.object(PowerShellTool, "run") as mock_run:
        result = plan("run a test script")
    assert result["type"] == "approval_required"
    assert result["tool"] == "powershell"
    assert result["args"] == {"script": "Write-Output test"}
    mock_run.assert_not_called()


def test_planner_executes_only_after_approval(monkeypatch):
    monkeypatch.setattr(llm, "call_llm", fake_tool_response)
    with mock.patch.object(PowerShellTool, "run", return_value={"ok": True, "stdout": "test", "stderr": ""}) as mock_run:
        result = plan("run a test script", approve_tool=lambda name, args: name == "powershell" and args["script"] == "Write-Output test")
    assert result["type"] == "tool"
    assert result["tool"] == "powershell"
    assert result["result"]["ok"] is True
    mock_run.assert_called_once_with(script="Write-Output test")


def test_planner_denies_tool_when_approval_callback_returns_false(monkeypatch):
    monkeypatch.setattr(llm, "call_llm", fake_tool_response)
    with mock.patch.object(PowerShellTool, "run") as mock_run:
        result = plan("run a test script", approve_tool=lambda _name, _args: False)
    assert result["type"] == "approval_denied"
    mock_run.assert_not_called()


def test_planner_returns_plain_text_when_no_tool(monkeypatch):
    monkeypatch.setattr(llm, "call_llm", lambda _messages: "Just a normal reply")
    result = plan("What is 2+2?")
    assert result["type"] == "plain"
    assert result["result"] == "Just a normal reply"


def test_planner_unknown_tool_is_not_executed(monkeypatch):
    monkeypatch.setattr(llm, "call_llm", lambda _messages: '{"tool":"unknown","args":{}}')
    result = plan("do something")
    assert result["type"] == "plain"
    assert "warning" in result
