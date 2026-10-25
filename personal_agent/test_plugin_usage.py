"""Simple script to demo the three starter plugins.

Run with:
    python test_plugin_usage.py
"""

from pathlib import Path

import sys, os
# Ensure the repository root is on PYTHONPATH so that 'personal_agent' can be imported
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if repo_root not in sys.path:
    sys.path.append(repo_root)

# Import plugins (ensure the package root is on PYTHONPATH)
from personal_agent.plugins.powershell_tool import PowerShellTool
from personal_agent.plugins.file_tool import FileTool
from personal_agent.plugins.web_tool import WebTool

def demo_powershell():
    tool = PowerShellTool(enabled=True, timeout=5)
    result = tool.run(script="Get-Date -UFormat %Y-%m-%d")
    print("[PowerShell]")
    print(result["stdout"].strip())

def demo_file():
    workspace = Path("workspace")
    workspace.mkdir(exist_ok=True)
    tool = FileTool(root=workspace, allow_write=True)
    write_res = tool.run(action="write", path="demo.txt", content="Hello from the personal agent!")
    read_res = tool.run(action="read", path="demo.txt")
    print("[File]")
    print("Write:", write_res)
    print("Read content:", read_res["content"])

def demo_web():
    tool = WebTool(allowed_hosts={"example.com"})
    res = tool.run(url="https://example.com")
    print("[Web]")
    print("Status:", res["status_code"], "Snippet:", res["text"][:200].replace("\n", " "))

if __name__ == "__main__":
    demo_powershell()
    demo_file()
    demo_web()
