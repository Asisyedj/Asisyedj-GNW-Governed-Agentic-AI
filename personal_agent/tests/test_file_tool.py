"""Tests for FileTool.

We use a temporary directory as the workspace.
"""

import os
import tempfile
from pathlib import Path

from personal_agent.plugins.file_tool import FileTool


def test_file_tool_read_write(tmp_path: Path):
    # tmp_path is a pytest fixture providing a temporary directory
    root = tmp_path / "workspace"
    root.mkdir()
    tool = FileTool(root=root, allow_write=True, max_bytes=1024)
    # Write a file
    write_res = tool.run(action="write", path="test.txt", content="Hello World")
    assert write_res["ok"] is True
    assert write_res["bytes_written"] == len("Hello World")
    # Read the file
    read_res = tool.run(action="read", path="test.txt")
    assert read_res["ok"] is True
    assert read_res["content"] == "Hello World"

def test_file_tool_path_escape(tmp_path: Path):
    root = tmp_path / "ws"
    root.mkdir()
    tool = FileTool(root=root, allow_write=False)
    # Attempt to escape the workspace
    try:
        tool.run(action="read", path="../outside.txt")
        assert False, "Expected PermissionError"
    except PermissionError:
        pass
