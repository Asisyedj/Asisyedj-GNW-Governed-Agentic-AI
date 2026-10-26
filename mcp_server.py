"""GNW-local MCP client. Uses only a scoped bridge key; upstream session remains in DPAPI."""
import json
import os
import tempfile
from pathlib import Path
import urllib.request
import urllib.error
from fastmcp import FastMCP
from gnw_secrets import get_bridge_key

BRIDGE_URL = "http://127.0.0.1:8000"
mcp = FastMCP("perplexity-models")

def _request(path: str, payload=None, timeout=120):
    headers = {}
    # Load optional Perplexity browse cookie from configuration (if present)
    try:
        config_path = Path(r"C:/Users/asisy/.gemini/config/mcp_config.json")
        cfg = json.load(open(config_path, "r", encoding="utf-8"))
        cookie_file = cfg.get("perplexity_cookie_path")
        if cookie_file and Path(cookie_file).exists():
            cookie_val = Path(cookie_file).read_text(encoding="utf-8").strip()
            if cookie_val:
                headers["Cookie"] = f"perplexity-browser={cookie_val}"
    except Exception:
        # Silently ignore errors – missing cookie is acceptable for non‑Perplexity calls
        pass
    # Add Authorization header if a valid bridge key is present
    try:
        key = get_bridge_key()
        if key:
            headers["Authorization"] = f"Bearer {key}"
    except Exception:
        # No valid bridge key; proceed without Authorization header
        pass
    # Load optional Perplexity browse cookie from configuration (if present)
    try:
        config_path = Path(r"C:/Users/asisy/.gemini/config/mcp_config.json")
        cfg = json.load(open(config_path, "r", encoding="utf-8"))
        cookie_file = cfg.get("perplexity_cookie_path")
        if cookie_file and Path(cookie_file).exists():
            cookie_val = Path(cookie_file).read_text(encoding="utf-8").strip()
            if cookie_val:
                headers["Cookie"] = f"perplexity-browser={cookie_val}"
    except Exception:
        # Silently ignore errors – missing cookie is acceptable for non‑Perplexity calls
        pass
    headers = {}
    try:
        key = get_bridge_key()
        if key:
            headers["Authorization"] = f"Bearer {key}"
    except Exception:
        # No valid bridge key; proceed without Authorization header
        pass
    data = None
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(BRIDGE_URL + path, data=data, headers=headers,
                                 method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # Avoid returning raw upstream error bodies that could contain sensitive details.
        raise RuntimeError(f"Bridge API returned HTTP {e.code}") from None
    except urllib.error.URLError:
        raise RuntimeError("Local GNW bridge is unreachable") from None

@mcp.tool()
def perplexity_ask(model: str = "openai/gpt5", prompt: str = "",
                   system_message: str = "You are a helpful expert assistant.") -> str:
    """Send a prompt through the GNW-local isolated bridge."""
    if not prompt or not prompt.strip():
        return "Error: Prompt cannot be empty."
    messages = []
    if system_message:
        messages.append({"role": "system", "content": system_message})
    messages.append({"role": "user", "content": prompt})
    try:
        data = _request("/v1/chat/completions",
                        {"model": model, "messages": messages, "stream": False})
        choices = data.get("choices", [])
        if choices:
            return choices[0].get("message", {}).get("content", "")
        return "Bridge returned no response choices."
    except Exception as exc:
        return f"Error: {exc}"

@mcp.tool()
def perplexity_list_models() -> str:
    """List models available through the local bridge."""
    try:
        data = _request("/v1/models", timeout=15)
        ids = sorted(m.get("id") for m in data.get("data", []) if m.get("id"))
        return f"Total Models: {len(ids)}\n" + "\n".join(ids)
    except Exception as exc:
        return f"Error: {exc}"

@mcp.tool()
def perplexity_bridge_health() -> str:
    """Check liveness of the localhost GNW bridge (does not prove upstream API health)."""
    req = urllib.request.Request(BRIDGE_URL + "/health", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.read().decode("utf-8")
    except Exception:
        return "Bridge offline or unreachable."

# Filesystem access is deliberately scoped to D:\\GNW. Secret-bearing paths and
# common credential artifacts are blocked even when they live under that root.
FILESYSTEM_ROOT = Path(r"D:\GNW").resolve()
_BLOCKED_DIRS = {".git", ".venv", "node_modules", "__pycache__", "secrets", ".cache"}
_BLOCKED_NAME_PARTS = ("secret", "credential", "token", "cookie", "password",
                       "recovery", "api_key", "api-key", "session")
_TEXT_SUFFIXES = {".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml",
                  ".ts", ".tsx", ".js", ".mjs", ".cjs", ".sh", ".ps1",
                  ".html", ".css", ".sql", ".csv", ".xml", ".ini", ".log"}

def _safe_path(user_path: str) -> Path:
    if not user_path or not user_path.strip():
        raise ValueError("A file path is required.")
    raw = Path(user_path)
    candidate = (FILESYSTEM_ROOT / raw).resolve() if not raw.is_absolute() else raw.resolve()
    try:
        candidate.relative_to(FILESYSTEM_ROOT)
    except ValueError:
        raise ValueError("Access denied: filesystem tools are restricted to D:\\GNW.") from None
    relative_parts = candidate.relative_to(FILESYSTEM_ROOT).parts
    if any(part.lower() in _BLOCKED_DIRS for part in relative_parts):
        raise ValueError("Access denied: this directory is excluded from model filesystem access.")
    name_lower = candidate.name.lower()
    if name_lower.startswith(".env") or any(part in name_lower for part in _BLOCKED_NAME_PARTS):
        raise ValueError("Access denied: secret or credential-like files are excluded.")
    if candidate.suffix.lower() in {".pem", ".key", ".pfx", ".p12", ".dpapi", ".sqlite", ".db"}:
        raise ValueError("Access denied: credential, database, or binary files are excluded.")
    return candidate

@mcp.tool()
def gnw_list_files(path: str = "D:\\GNW", recursive: bool = False, limit: int = 100) -> str:
    """List files and folders within D:\\GNW; secret and dependency directories are hidden."""
    try:
        base = _safe_path(path)
        if not base.exists() or not base.is_dir():
            return "Error: path is not an existing directory."
        limit = max(1, min(int(limit), 200))
        rows = []
        if recursive:
            for current, dirs, files in os.walk(base, followlinks=False):
                dirs[:] = [d for d in dirs if d.lower() not in _BLOCKED_DIRS
                           and not d.lower().startswith(".env")]
                for name in sorted(dirs + files):
                    candidate = Path(current) / name
                    try:
                        _safe_path(str(candidate))
                    except ValueError:
                        continue
                    rows.append(("DIR " if candidate.is_dir() else "FILE ") + str(candidate.relative_to(FILESYSTEM_ROOT)))
                    if len(rows) >= limit:
                        break
                if len(rows) >= limit:
                    break
        else:
            for candidate in sorted(base.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                try:
                    _safe_path(str(candidate))
                except ValueError:
                    continue
                rows.append(("DIR " if candidate.is_dir() else "FILE ") + candidate.name)
                if len(rows) >= limit:
                    break
        return "\n".join(rows) if rows else "No accessible files found."
    except Exception as exc:
        return f"Error: {type(exc).__name__}: {exc}"

@mcp.tool()
def gnw_read_file(path: str, max_chars: int = 20000) -> str:
    """Read a UTF-8 text file within D:\\GNW; secrets, databases, and binary files are blocked."""
    try:
        target = _safe_path(path)
        if not target.exists() or not target.is_file():
            return "Error: path is not an existing file."
        if target.suffix.lower() not in _TEXT_SUFFIXES:
            return "Error: only approved text-file extensions can be read."
        size = target.stat().st_size
        if size > 1_000_000:
            return "Error: file exceeds the 1 MB read limit."
        max_chars = max(1, min(int(max_chars), 50000))
        content = target.read_text(encoding="utf-8-sig")
        if len(content) > max_chars:
            return content[:max_chars] + f"\n\n[TRUNCATED: showing {max_chars} of {len(content)} characters]"
        return content
    except UnicodeDecodeError:
        return "Error: file is not valid UTF-8 text."
    except Exception as exc:
        return f"Error: {type(exc).__name__}: {exc}"

@mcp.tool()
def gnw_write_file(path: str, content: str, overwrite: bool = False) -> str:
    """Write UTF-8 text under D:\\GNW. Existing files require overwrite=true; protected paths are blocked."""
    try:
        target = _safe_path(path)
        if target.suffix.lower() not in _TEXT_SUFFIXES:
            return "Error: only approved text-file extensions can be written."
        if not isinstance(content, str) or len(content) > 100000:
            return "Error: content must be text no larger than 100,000 characters."
        if target.exists() and not overwrite:
            return "Error: file already exists; set overwrite=true only after reviewing its current contents."
        target.parent.mkdir(parents=True, exist_ok=True)
        # Revalidate after directory creation to guard against path changes.
        target = _safe_path(str(target))
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", delete=False,
                                         dir=str(target.parent), prefix=".gnw-write-", suffix=".tmp") as handle:
            temp_name = handle.name
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
        return f"OK: wrote {len(content)} characters to {target.relative_to(FILESYSTEM_ROOT)}"
    except Exception as exc:
        return f"Error: {type(exc).__name__}: {exc}"

if __name__ == "__main__":
    mcp.run()
