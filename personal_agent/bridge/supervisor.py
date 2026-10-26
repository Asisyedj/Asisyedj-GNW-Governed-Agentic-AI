"""Bridge supervisor – self‑healing wrapper for the local Perplexity bridge.

The bridge daemon lives in *bridge_daemon.py* and is a FastAPI app that
expects two pieces of secret material:

* ``bridge-api-key.txt`` – the local access key that clients present via a
  ``Bearer <key>`` header.
* ``perplexity-session.dpapi`` – the upstream Perplexity session token that
  the bridge forwards after validating the local key.

Both values are stored in the DPAPI‑protected secret store implemented in
:mod:`gnw_secrets`.  The supervisor is responsible for:

* Starting the bridge process if it is not running.
* Periodically checking ``/health`` (local‑only, no auth required).
* Detecting HTTP 401/403 from the bridge and attempting a refresh of the
  session token via the project's ``refresh_token.py`` script if it exists.
* Restarting the bridge when the health check fails, when the process exits
  unexpectedly, or when the authentication contract is broken.
* Exposing a deterministic state machine for observability.

The implementation deliberately avoids external dependencies – only the
standard library and ``httpx`` (already used elsewhere) are required.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import subprocess
import sys
from pathlib import Path
from typing import Optional

import httpx

from gnw_secrets import get_bridge_key, get_session_token

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration – can be overridden by environment variables for flexibility.
# ---------------------------------------------------------------------------
CHECK_INTERVAL = float(os.getenv("BRIDGE_CHECK_INTERVAL", "30"))  # seconds
FAILURE_THRESHOLD = int(os.getenv("BRIDGE_FAILURE_THRESHOLD", "3"))
RECOVERY_COOLDOWN = float(os.getenv("BRIDGE_RECOVERY_COOLDOWN", "60"))
MAX_RESTARTS = int(os.getenv("BRIDGE_MAX_RESTARTS", "5"))
PORT_RELEASE_WAIT = float(os.getenv("BRIDGE_PORT_RELEASE_WAIT", "5"))  # seconds to wait for port release
BRIDGE_HOST = os.getenv("BRIDGE_HOST", "127.0.0.1")
BRIDGE_PORT = int(os.getenv("BRIDGE_PORT", "8000"))
BRIDGE_URL = f"http://{BRIDGE_HOST}:{BRIDGE_PORT}"
LOCK_PATH = Path(os.getenv("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))) / "GNW" / "bridge_supervisor.lock"

# ---------------------------------------------------------------------------
# Simple state machine – used for structured logs and external visibility.
# ---------------------------------------------------------------------------
class BridgeState(str):
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    RECOVERING = "RECOVERING"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    FAILED = "FAILED"

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------
def _write_lock(pid: int) -> None:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOCK_PATH.write_text(str(pid), encoding="utf-8")

def _read_lock() -> Optional[int]:
    if LOCK_PATH.is_file():
        try:
            return int(LOCK_PATH.read_text(encoding="utf-8"))
        except Exception:
            return None
    return None

def _clear_lock() -> None:
    try:
        LOCK_PATH.unlink(missing_ok=True)
    except Exception:
        pass

def _is_process_alive(pid: int) -> bool:
    try:
        # ``os.kill(pid, 0)`` works on Windows as a liveness check.
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def _start_bridge_process() -> subprocess.Popen:
    """Launch ``bridge_daemon.py`` as a detached subprocess.

    The bridge reads its secrets at import time, so we must ensure the
    environment contains the required DPAPI‑derived values before spawning.
    ``get_bridge_key`` and ``get_session_token`` raise if the secret store is
    incomplete – the caller should handle those exceptions.
    """
    # Prevent duplicate bridge instances: if a lock exists and the PID is alive, reuse it.
    existing_pid = _read_lock()
    if existing_pid and _is_process_alive(existing_pid):
        logger.debug("BridgeSupervisor: existing bridge PID %s detected, not spawning a new process", existing_pid)
        from types import SimpleNamespace
        return SimpleNamespace(pid=existing_pid)


    # Ensure the secrets are readable – this will raise a clear exception if
    # something is missing, preventing a stray bridge from starting.
    _ = get_bridge_key()
    _ = get_session_token()

    bridge_path = Path(__file__).parents[2] / "bridge_daemon.py"
    env = os.environ.copy()
    # Pass secrets via environment to bridge daemon (overrides if set).
    env["GNW_SESSION_TOKEN"] = get_session_token()
    env["GNW_BRIDGE_KEY"] = get_bridge_key()
    proc = subprocess.Popen([sys.executable, str(bridge_path)], env=env)
    logger.info("BridgeSupervisor: started bridge process PID %s", proc.pid)
    _write_lock(proc.pid)
    return proc

def _health_check() -> bool:
    """Return ``True`` if ``/health`` responds with 200 within the timeout.
    """
    try:
        resp = httpx.get(f"{BRIDGE_URL}/health", timeout=5.0)
        return resp.status_code == 200
    except Exception as exc:
        logger.debug("Bridge health check failed: %s", exc)
        return False

def _auth_check() -> bool:
    """Perform a minimal authenticated request to verify the bridge key.

    The request is a cheap ``GNW_HEALTH_CHECK`` chat call – it goes through the
    router's authentication flow, so a 401/403 indicates a broken key or session.
    Upstream 503 errors are treated as transient and do not fail the auth check.
    """
    try:
        # Import lazily to avoid circular imports at module load time.
        from personal_agent.agent.router import global_router, TaskCategory

        result = global_router.execute_with_fallback(
            messages=[{"role": "user", "content": "GNW_HEALTH_CHECK"}],
            requested_model="perplexity/sonar-2",
            task_category=TaskCategory.DEFAULT,
            timeout=10,
        )
        # Successful inference should contain the probe token.
        return isinstance(result.get("content"), str) and "GNW_HEALTH_CHECK" in result["content"]
    except Exception as exc:
        # Check if this is an auth failure (401/403) vs upstream failure (503, etc.)
        exc_str = str(exc).lower()
        if "401" in exc_str or "403" in exc_str or "unauthorized" in exc_str:
            logger.warning("Bridge auth check failed - authentication error: %s", exc)
            return False
        # Upstream service unavailable (503) or other transient errors don't indicate auth failure
        logger.debug("Bridge auth check - upstream transient error (not auth failure): %s", exc)
        return True

def _run_refresh_token() -> bool:
    """Execute the project's ``refresh_token.py`` script if present.

    Returns ``True`` when the script exits with code 0, otherwise ``False``.
    """
    script = Path(__file__).parents[2] / "refresh_token.py"
    if not script.is_file():
        logger.info("BridgeSupervisor: no refresh_token.py – cannot refresh session")
        return False
    proc = subprocess.run([sys.executable, str(script)], capture_output=True, text=True)
    if proc.returncode == 0:
        logger.info("BridgeSupervisor: session token refreshed successfully")
        return True
    else:
        logger.warning(
            "BridgeSupervisor: refresh_token.py failed (code %s): %s",
            proc.returncode,
            proc.stderr.strip(),
        )
        return False

# ---------------------------------------------------------------------------
# Supervisor implementation
# ---------------------------------------------------------------------------
class BridgeSupervisor:
    """Self‑healing manager for the local Perplexity bridge.

    The supervisor runs a background thread that periodically checks the bridge
    health and authentication state.  State transitions are logged and exposed
    via :meth:`status` for UI panels or external monitoring.
    """

    def __init__(self) -> None:
        self._state: BridgeState = BridgeState.FAILED
        self._failures: int = 0
        self._restart_count: int = 0
        self._process: Optional[subprocess.Popen] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    # -------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------
    def start(self) -> None:
        """Start the background monitor thread (idempotent)."""
        if self._thread and self._thread.is_alive():
            logger.debug("BridgeSupervisor: already running")
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="BridgeSupervisor")
        self._thread.start()
        logger.info("BridgeSupervisor: monitoring thread started")

    def stop(self) -> None:
        """Signal the thread to stop and terminate the bridge process."""
        self._stop_event.set()
        if self._process and _is_process_alive(self._process.pid):
            self._process.terminate()
            self._process.wait(timeout=5)
        _clear_lock()
        logger.info("BridgeSupervisor: stopped")

    def status(self) -> dict:
        """Return a JSON‑serialisable snapshot of the current supervisor state."""
        return {
            "state": self._state,
            "failures": self._failures,
            "restarts": self._restart_count,
            "pid": self._process.pid if self._process else None,
        }

    # -------------------------------------------------------------------
    # Internal loop
    # -------------------------------------------------------------------
    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._evaluate()
            except Exception as exc:  # pragma: no cover – defensive
                logger.exception("BridgeSupervisor unexpected error: %s", exc)
            time.sleep(CHECK_INTERVAL)

    def _evaluate(self) -> None:
        """Core evaluation step – health, auth, restart logic."""
        # 1️⃣ Ensure a process exists.
        if not self._process or not _is_process_alive(self._process.pid):
            logger.debug("BridgeSupervisor: bridge process not running – attempting start")
            self._start_or_fail()
            return

        # 2️⃣ Health check – fast local endpoint.
        if not _health_check():
            logger.warning("BridgeSupervisor: health endpoint unreachable – marking degraded")
            self._transition(BridgeState.DEGRADED)
            self._failures += 1
            if self._failures >= FAILURE_THRESHOLD:
                self._restart_or_fail()
            return

        # 3️⃣ Auth check – ensure the bridge key and session token are valid.
        if not _auth_check():
            logger.warning("BridgeSupervisor: authenticated call failed – auth required")
            self._transition(BridgeState.AUTH_REQUIRED)
            # Attempt a session refresh before giving up.
            if _run_refresh_token():
                # Refresh succeeded – give the bridge a chance to recover.
                self._transition(BridgeState.RECOVERING)
                time.sleep(RECOVERY_COOLDOWN)
                self._restart_or_fail()
            else:
                self._failures += 1
                if self._failures >= FAILURE_THRESHOLD:
                    self._restart_or_fail()
            return

        # 4️⃣ All good – reset counters and mark healthy.
        self._failures = 0
        self._transition(BridgeState.HEALTHY)

    # -------------------------------------------------------------------
    # State helpers
    # -------------------------------------------------------------------
    def _transition(self, new_state: BridgeState) -> None:
        if self._state != new_state:
            logger.info("BridgeSupervisor: state %s → %s", self._state, new_state)
            self._state = new_state

    def _start_or_fail(self) -> None:
        try:
            self._process = _start_bridge_process()
            self._restart_count += 1
            self._transition(BridgeState.RECOVERING)
        except Exception as exc:
            logger.error("BridgeSupervisor: failed to start bridge – %s", exc)
            self._transition(BridgeState.FAILED)
            self._failures += 1
            if self._restart_count >= MAX_RESTARTS:
                logger.critical("BridgeSupervisor: max restarts exceeded – giving up")
                self._stop_event.set()

    def _restart_or_fail(self) -> None:
        if self._process and _is_process_alive(self._process.pid):
            logger.info("BridgeSupervisor: terminating unhealthy bridge PID %s", self._process.pid)
            self._process.terminate()
            self._process.wait(timeout=5)
        # Wait for TCP port release (TIME_WAIT on Windows can take several seconds)
        logger.debug("BridgeSupervisor: waiting %ss for port release", PORT_RELEASE_WAIT)
        time.sleep(PORT_RELEASE_WAIT)
        self._process = None
        self._start_or_fail()

# ---------------------------------------------------------------------------
# Convenience singleton – importable by the rest of the codebase.
# ---------------------------------------------------------------------------
global_bridge_supervisor = BridgeSupervisor()
"""A module‑level singleton that can be imported wherever bridge health is
required.  Users should call ``global_bridge_supervisor.start()`` early in the
application lifecycle (e.g., from ``personal_agent.__init__``).
"""
