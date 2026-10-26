"""Extract only the current Perplexity session cookie and seal it with Windows DPAPI."""
import os
import json
import base64
import sqlite3
import ctypes
import tempfile
import shutil
from pathlib import Path
from ctypes import wintypes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from gnw_secrets import set_session_token, secret_dir

class DATA_BLOB(ctypes.Structure):
    _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_byte))]

def decrypt_dpapi(encrypted_bytes: bytes) -> bytes:
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    source = ctypes.create_string_buffer(encrypted_bytes)
    data_in = DATA_BLOB(len(encrypted_bytes), ctypes.cast(source, ctypes.POINTER(ctypes.c_byte)))
    data_out = DATA_BLOB()
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p,
        ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(DATA_BLOB)
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    if not crypt32.CryptUnprotectData(ctypes.byref(data_in), None, None, None, None, 1, ctypes.byref(data_out)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(data_out.pbData, data_out.cbData)
    finally:
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree(data_out.pbData)

def get_master_key(local_state_path: str) -> bytes:
    with open(local_state_path, "r", encoding="utf-8") as f:
        local_state = json.load(f)
    encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
    if not encrypted_key.startswith(b"DPAPI"):
        raise RuntimeError("Unsupported browser key format")
    return decrypt_dpapi(encrypted_key[5:])

def decrypt_val(encrypted_val: bytes, master_key: bytes) -> str:
    if not encrypted_val:
        return ""
    if encrypted_val.startswith((b"v10", b"v11", b"v20")):
        nonce = encrypted_val[3:15]
        raw = AESGCM(master_key).decrypt(nonce, encrypted_val[15:], None)
    else:
        raw = decrypt_dpapi(encrypted_val)
    try:
        decoded = raw.decode("utf-8")
        if decoded.startswith("eyJ"):
            return decoded
    except UnicodeDecodeError:
        pass
    # Chromium versioned values may contain a 32-byte host-hash prefix.
    if len(raw) > 32:
        candidate = raw[32:].decode("utf-8", errors="ignore")
        if candidate.startswith("eyJ"):
            return candidate
    return raw.decode("utf-8", errors="ignore")

def extract_session_token() -> int:
    local = os.environ.get("LOCALAPPDATA")
    if not local:
        raise RuntimeError("LOCALAPPDATA is unavailable")
    root = Path(local) / "Perplexity" / "Comet" / "User Data"
    state_path = root / "Local State"
    cookie_path = root / "Default" / "Network" / "Cookies"
    if not state_path.is_file() or not cookie_path.is_file():
        raise FileNotFoundError("Comet cookie source was not found")
    master_key = get_master_key(str(state_path))
    # Open the original browser DB read-only; no persistent cookie copy/export is produced.
    uri = cookie_path.resolve().as_uri() + "?mode=ro"
    with sqlite3.connect(uri, uri=True, timeout=5) as conn:
        rows = conn.execute(
            "SELECT host_key, encrypted_value FROM cookies "
            "WHERE name='__Secure-next-auth.session-token' AND host_key LIKE '%perplexity.ai%'"
        ).fetchall()
    token = None
    for host, enc in rows:
        candidate = decrypt_val(enc, master_key)
        if candidate.startswith("eyJ") and (host == "www.perplexity.ai" or token is None):
            token = candidate
            if host == "www.perplexity.ai":
                break
    if not token:
        raise RuntimeError("Perplexity session cookie was not available")
    set_session_token(token)
    return len(token)

def main():
    size = extract_session_token()
    print(f"Session stored with Windows DPAPI; token_length={size}; no plaintext export created.")

if __name__ == "__main__":
    main()
