"""GNW user-scoped Windows DPAPI secret store. No secret values are logged."""
from __future__ import annotations
import ctypes
import hashlib
import json
import os
import sys
from ctypes import wintypes
from pathlib import Path

PREFIX = b"GNW-DPAPI-SECRET-V1\n"
SEAL_DOMAIN = b"GNW-FILE-SEAL-V1\n"
SEAL_NAME = "seal.json"
SEALED_SECRETS = ("perplexity-session.dpapi", "bridge-api-key.txt")
CRYPTPROTECT_UI_FORBIDDEN = 0x1

class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]

def secret_dir() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "GNW" / "Secrets"

def secret_path(name: str) -> Path:
    if name not in {*SEALED_SECRETS, SEAL_NAME}:
        raise ValueError("Secret name is not allowlisted")
    return secret_dir() / name

def _seal_digest(name: str, data: bytes) -> str:
    digest = hashlib.sha256()
    digest.update(SEAL_DOMAIN)
    digest.update(name.encode("utf-8"))
    digest.update(b"\0")
    digest.update(data)
    return digest.hexdigest()

def write_seal() -> dict:
    """Record domain-separated SHA-256 digests for every sealed file that exists."""
    folder = secret_dir()
    folder.mkdir(parents=True, exist_ok=True)
    entries = {}
    for name in SEALED_SECRETS:
        path = secret_path(name)
        if path.is_file():
            entries[name] = _seal_digest(name, path.read_bytes())
    manifest = {"domain": "GNW-FILE-SEAL-V1", "files": entries}
    target = secret_path(SEAL_NAME)
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, target)
    return entries

def verify_seal() -> dict:
    """Return PASS / MISMATCH / MISSING / UNSEALED per sealed file; reveals no contents."""
    expected = {}
    manifest_path = secret_path(SEAL_NAME)
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("domain") == "GNW-FILE-SEAL-V1":
            expected = manifest.get("files", {})
    results = {}
    for name in SEALED_SECRETS:
        path = secret_path(name)
        if not path.is_file():
            results[name] = "MISSING"
        elif name not in expected:
            results[name] = "UNSEALED"
        elif _seal_digest(name, path.read_bytes()) == expected[name]:
            results[name] = "PASS"
        else:
            results[name] = "MISMATCH"
    return results

def _blob(data: bytes):
    buf = ctypes.create_string_buffer(data)
    b = DATA_BLOB(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_byte)))
    return b, buf

def _protect(data: bytes) -> bytes:
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    in_blob, keepalive = _blob(data)
    out_blob = DATA_BLOB()
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(DATA_BLOB), wintypes.LPCWSTR, ctypes.POINTER(DATA_BLOB),
        wintypes.LPVOID, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(DATA_BLOB)
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    if not crypt32.CryptProtectData(ctypes.byref(in_blob), "GNW scoped secret", None, None, None,
                                    CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out_blob)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree(out_blob.pbData)

def _unprotect(data: bytes) -> bytes:
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    in_blob, keepalive = _blob(data)
    out_blob = DATA_BLOB()
    desc = wintypes.LPWSTR()
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(DATA_BLOB), ctypes.POINTER(wintypes.LPWSTR), ctypes.POINTER(DATA_BLOB),
        wintypes.LPVOID, wintypes.LPVOID, wintypes.DWORD, ctypes.POINTER(DATA_BLOB)
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    if not crypt32.CryptUnprotectData(ctypes.byref(in_blob), ctypes.byref(desc), None, None, None,
                                      CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(out_blob)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(out_blob.pbData, out_blob.cbData)
    finally:
        kernel32.LocalFree.argtypes = [ctypes.c_void_p]
        kernel32.LocalFree(out_blob.pbData)
        if desc:
            kernel32.LocalFree(desc)

def set_session_token(token: str) -> None:
    if not token or "\n" in token or "\r" in token:
        raise ValueError("Refusing an empty or malformed session token")
    folder = secret_dir()
    folder.mkdir(parents=True, exist_ok=True)
    target = secret_path("perplexity-session.dpapi")
    tmp = target.with_suffix(".tmp")
    tmp.write_bytes(PREFIX + _protect(token.encode("utf-8")))
    os.replace(tmp, target)
    write_seal()

def get_session_token() -> str:
    raw = secret_path("perplexity-session.dpapi").read_bytes()
    if not raw.startswith(PREFIX):
        raise ValueError("Secret-store format marker mismatch")
    value = _unprotect(raw[len(PREFIX):]).decode("utf-8")
    if not value:
        raise ValueError("Stored session token is empty")
    return value

def get_bridge_key() -> str:
    key = secret_path("bridge-api-key.txt").read_text(encoding="utf-8").strip()
    if len(key) < 40 or "\n" in key or "\r" in key:
        raise ValueError("Bridge access key is absent or malformed")
    return key

def _main(argv: list) -> int:
    if len(argv) != 2 or argv[1] not in {"seal", "verify"}:
        print("usage: gnw_secrets.py seal|verify")
        return 2
    if argv[1] == "seal":
        entries = write_seal()
        print(f"SEAL_WRITTEN; files={len(entries)}")
        return 0
    statuses = verify_seal()
    for name in sorted(statuses):
        print(f"SEAL_STATUS {name}={statuses[name]}")
    return 0 if all(v == "PASS" for v in statuses.values()) else 1

if __name__ == "__main__":
    raise SystemExit(_main(sys.argv))
