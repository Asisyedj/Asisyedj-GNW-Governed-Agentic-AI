from unittest import mock

from personal_agent.agent import llm
from personal_agent.agent.planner import plan
from personal_agent.plugins.powershell_tool import PowerShellTool


def test_plan_uses_default_model_route_when_model_name_is_omitted(monkeypatch):
    default_calls = []

    def fake_default_llm(messages):
        default_calls.append(messages)
        return "default route response"

    def unexpected_explicit_model_call(_messages, model_name=None):
        raise AssertionError("Explicit model helper should not be used without model_name")

    monkeypatch.setattr(llm, "call_llm", fake_default_llm)
    monkeypatch.setattr(llm, "call_llm_with_model", unexpected_explicit_model_call)

    result = plan("Summarize today.")

    assert result["type"] == "plain"
    assert result["result"] == "default route response"
    assert len(default_calls) == 1


def test_plan_routes_explicit_model_and_preserves_approval_gate(monkeypatch):
    explicit_calls = []
    proposal = '{"tool": "powershell", "args": {"script": "Write-Output test"}}'

    def unexpected_default_llm(_messages):
        raise AssertionError("Default LLM route should not be used with model_name")

    def fake_explicit_model_call(messages, model_name=None):
        explicit_calls.append((messages, model_name))
        return proposal

    monkeypatch.setattr(llm, "call_llm", unexpected_default_llm)
    monkeypatch.setattr(llm, "call_llm_with_model", fake_explicit_model_call)

    with mock.patch.object(PowerShellTool, "run") as mock_run:
        result = plan("Run a test script", model_name="perplexity/sonar-2")

    assert result["type"] == "approval_required"
    assert result["tool"] == "powershell"
    assert result["args"] == {"script": "Write-Output test"}
    assert len(explicit_calls) == 1
    assert explicit_calls[0][1] == "perplexity/sonar-2"
    mock_run.assert_not_called()
