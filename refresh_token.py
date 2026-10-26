"""Securely refresh the browser session into DPAPI storage and restart the localhost bridge."""
import os
import time
import subprocess
from pathlib import Path
from sync_comet_token import extract_session_token

WORK_DIR = Path(r"D:\GNW\perplexity-browser-api")

def refresh() -> bool:
    try:
        length = extract_session_token()
    except Exception as exc:
        print(f"Token refresh failed ({type(exc).__name__}); existing stored credential was not overwritten.")
        return False
    print(f"Updated user-scoped DPAPI secret (length={length}); no plaintext token/config updates written.")
    # Stop only the current loopback listener on the bridge's reserved port.
    stop_script = (
        "$ids = @(Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue "
        "| Select-Object -ExpandProperty OwningProcess -Unique); "
        "foreach ($id in $ids) { if ($id -gt 0) { Stop-Process -Id $id -Force -ErrorAction SilentlyContinue } }"
    )
    subprocess.run(["powershell.exe", "-NoProfile", "-Command", stop_script],
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    time.sleep(1)
    launcher = WORK_DIR / "start_bridge_silent.vbs"
    if not launcher.is_file():
        print("Bridge launcher missing; secret was stored, but restart was skipped.")
        return False
    subprocess.Popen(["wscript.exe", str(launcher)], cwd=str(WORK_DIR),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    time.sleep(2)
    print("Bridge restart requested. Verify /health and a protected API call before relying on it.")
    return True

if __name__ == "__main__":
    raise SystemExit(0 if refresh() else 1)
