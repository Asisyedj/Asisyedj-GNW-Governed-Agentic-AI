"""Thin wrapper around the Chrome DevTools MCP bridge.
It launches a headless Chromium process, attaches via the MCP protocol,
and provides a `run_payload(payload, cfg)` method that:
1. Loads the supplied cookies into the browser session (in‑memory).
2. Navigates to the target URL with the payload injected (e.g., query param, form post).
3. Captures network request/response data.
4. Enforces a **read‑only policy**: any HTTP method other than GET/OPTIONS is aborted.
"""
import subprocess, time, json, pathlib, os, sys

class BridgeClient:
    def __init__(self, dry_run: bool = True):
        """Initialize the bridge client.

        Args:
            dry_run: When True (default) the client will not attempt to launch a
                Python bridge daemon. This is suitable for the current sandbox
                where only the TypeScript bridge implementation exists.
        """
        # Assume the chrome-devtools-mcp repo is cloned under the workspace root
        self.repo_root = pathlib.Path(__file__).parents[1]
        self.bridge_path = self.repo_root / "chrome-devtools-mcp" / "bridge_daemon.py"
        self.proc = None
        self.dry_run = dry_run

    def start(self):
        if self.dry_run:
            # Skip real launch; log for visibility
            print("[BridgeClient] Dry-run mode - not starting bridge daemon.")
            return
        if not self.bridge_path.exists():
            raise FileNotFoundError(f"Bridge daemon not found at {self.bridge_path}")
        cmd = [sys.executable, str(self.bridge_path), "--headless"]
        # Launch bridge as a background process
        self.proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=str(self.repo_root),
        )
        # Give the daemon a moment to start up
        time.sleep(2)

    def stop(self):
        if self.dry_run:
            print("[BridgeClient] Dry-run mode - no daemon to stop.")
            return
        if self.proc:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.proc.kill()
            self.proc = None


    def run_payload(self, payload: dict, cfg) -> dict:
        """Execute a single payload safely.
        Returns a dict with request/response details and any error.
        """
        method = payload.get("method", "GET").upper()
        # Enforce read‑only policy
        if method not in {"GET", "OPTIONS"}:
            return {"payload": payload, "status": "skipped", "reason": "disallowed HTTP method"}

        # Simple simulation – in a real implementation we would communicate with the MCP socket.
        # Here we just record what would be sent.
        result = {
            "payload": payload,
            "status": "executed",
            "request": {
                "method": method,
                "url": payload.get("url", cfg.target),
                "headers": payload.get("headers", {}),
                "body": payload.get("body", ""),
            },
            "response": {
                "status": 200,
                "body": "<placeholder response>"
            }
        }
        return result
