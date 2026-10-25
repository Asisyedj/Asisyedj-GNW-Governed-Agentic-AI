"""Tests for WebTool.

We mock ``httpx.Client`` to avoid real network calls.
"""

from unittest import mock

import httpx

from personal_agent.plugins.web_tool import WebTool


def test_web_tool_allowed_host_success():
    # Mock response object
    mock_response = mock.Mock()
    mock_response.status_code = 200
    mock_response.headers = {"content-type": "text/plain"}
    mock_response.encoding = "utf-8"
    mock_response.url = httpx.URL("https://example.com")
    mock_response.iter_bytes.return_value = [b"Hello World"]
    mock_response.raise_for_status = mock.Mock()

    mock_client = mock.Mock()
    mock_client.__enter__ = mock.Mock(return_value=mock_client)
    mock_client.__exit__ = mock.Mock(return_value=False)
    mock_client.stream.return_value.__enter__ = mock.Mock(return_value=mock_response)
    mock_client.stream.return_value.__exit__ = mock.Mock(return_value=False)

    with mock.patch("httpx.Client", return_value=mock_client):
        tool = WebTool(allowed_hosts={"example.com"})
        result = tool.run(url="https://example.com")
        assert result["ok"] is True
        assert result["status_code"] == 200
        assert result["text"] == "Hello World"


def test_web_tool_disallowed_host_raises():
    tool = WebTool(allowed_hosts={"example.com"})
    try:
        tool.run(url="https://evil.com")
        assert False, "Expected PermissionError"
    except PermissionError:
        pass
