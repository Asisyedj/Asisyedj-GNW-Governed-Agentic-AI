"""Focused regression test for the GNW filesystem MCP tools; uses a disposable workspace file."""
import sys
from pathlib import Path

ROOT = Path(r"D:\GNW\perplexity-browser-api")
sys.path.insert(0, str(ROOT))
import mcp_server

def check(condition, label):
    if not condition:
        raise AssertionError(label)
    print("PASS:", label)

tools = {name for name in dir(mcp_server) if name in {"perplexity_ask", "perplexity_list_models", "perplexity_bridge_health", "gnw_list_files", "gnw_read_file", "gnw_write_file"}}
check({"perplexity_ask", "perplexity_list_models", "perplexity_bridge_health",
       "gnw_list_files", "gnw_read_file", "gnw_write_file"}.issubset(tools),
      "six expected MCP tools registered")

listing = mcp_server.gnw_list_files(str(ROOT), recursive=False, limit=20)
check("mcp_server.py" in listing, "allowed directory listing")

readback = mcp_server.gnw_read_file(str(ROOT / "README_SETUP.md"), max_chars=5000)
check("GNW" in readback and not readback.startswith("Error:"), "read allowed UTF-8 file")

try:
    blocked = mcp_server.gnw_read_file(r"D:\GNW\.env.production")
    check(blocked.startswith("Error:") and "Access denied" in blocked, "blocked environment secrets")
except Exception as exc:
    raise AssertionError("blocked-path check raised unexpectedly") from exc

outside = mcp_server.gnw_read_file(r"C:\Windows\win.ini")
check(outside.startswith("Error:") and "Access denied" in outside, "blocked path outside configured root")

workspace = ROOT / "workspace"
workspace.mkdir(exist_ok=True)
probe = workspace / "mcp_fs_probe.txt"
if probe.exists():
    probe.unlink()
try:
    wrote = mcp_server.gnw_write_file(str(probe), "GNW_FILESYSTEM_WRITE_READ_OK", overwrite=False)
    check(wrote.startswith("OK:"), "write new file")
    check(mcp_server.gnw_read_file(str(probe)) == "GNW_FILESYSTEM_WRITE_READ_OK", "read back written file")
    check(mcp_server.gnw_write_file(str(probe), "no-overwrite") .startswith("Error: file already exists"),
          "refuse overwrite by default")
finally:
    if probe.exists():
        probe.unlink()
print("FILESYSTEM_MCP_TEST=PASS")
