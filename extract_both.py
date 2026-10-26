import os
import sys
import time
import json
import base64
import sqlite3
import shutil
import subprocess
import ctypes
from ctypes import wintypes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte))
    ]

def decrypt_dpapi(encrypted_bytes: bytes) -> bytes:
    pDataIn = DATA_BLOB(len(encrypted_bytes), ctypes.cast(ctypes.create_string_buffer(encrypted_bytes), ctypes.POINTER(ctypes.c_byte)))
    pDataOut = DATA_BLOB()
    pPrompt = None
    pEntropy = None
    CRYPTPROTECT_UI_FORBIDDEN = 0x01
    
    if ctypes.windll.crypt32.CryptUnprotectData(
        ctypes.byref(pDataIn),
        None,
        pEntropy,
        None,
        pPrompt,
        CRYPTPROTECT_UI_FORBIDDEN,
        ctypes.byref(pDataOut)
    ):
        result = ctypes.string_at(pDataOut.pbData, pDataOut.cbData)
        ctypes.windll.kernel32.LocalFree(pDataOut.pbData)
        return result
    else:
        error = ctypes.windll.kernel32.GetLastError()
        raise RuntimeError(f"CryptUnprotectData failed with error code: {error}")

def get_master_key(local_state_path: str) -> bytes:
    with open(local_state_path, "r", encoding="utf-8") as f:
        local_state = json.load(f)
    encrypted_key_b64 = local_state["os_crypt"]["encrypted_key"]
    encrypted_key = base64.b64decode(encrypted_key_b64)
    if not encrypted_key.startswith(b"DPAPI"):
        raise ValueError("Invalid DPAPI prefix in encrypted_key")
    encrypted_key = encrypted_key[5:]
    return decrypt_dpapi(encrypted_key)

def decrypt_cookie_value(encrypted_val: bytes, master_key: bytes) -> str:
    if not encrypted_val:
        return ""
    if encrypted_val.startswith(b"v10") or encrypted_val.startswith(b"v11"):
        nonce = encrypted_val[3:15]
        ciphertext = encrypted_val[15:]
        aesgcm = AESGCM(master_key)
        decrypted = aesgcm.decrypt(nonce, ciphertext, None)
        return decrypted.decode("utf-8", errors="replace")
    else:
        try:
            return decrypt_dpapi(encrypted_val).decode("utf-8", errors="replace")
        except Exception:
            return encrypted_val.decode("utf-8", errors="replace")

def read_cookies_from_db(db_path: str, master_key: bytes):
    if not os.path.exists(db_path):
        return {}
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT host_key, name, encrypted_value FROM cookies WHERE host_key LIKE '%perplexity.ai%'")
    rows = cursor.fetchall()
    cookies = {}
    for host_key, name, enc_val in rows:
        try:
            val = decrypt_cookie_value(enc_val, master_key)
            cookies[name] = {
                "name": name,
                "domain": host_key,
                "value": val
            }
        except Exception as e:
            print(f"Error decrypting {name}: {e}")
    conn.close()
    return cookies

def main():
    print("1. Terminating Comet and Perplexity temporarily to release database locks...")
    os.system("taskkill /F /IM comet.exe >nul 2>&1")
    os.system("taskkill /F /IM Perplexity.exe >nul 2>&1")
    time.sleep(1.5)

    work_dir = r"D:\GNW\perplexity-browser-api"
    os.makedirs(work_dir, exist_ok=True)

    comet_db_src = os.path.expandvars(r"%LOCALAPPDATA%\Perplexity\Comet\User Data\Default\Network\Cookies")
    comet_ls_src = os.path.expandvars(r"%LOCALAPPDATA%\Perplexity\Comet\User Data\Local State")
    comet_db_dst = os.path.join(work_dir, "Comet_Cookies.sqlite")

    pplx_app_db_src = os.path.expandvars(r"%LOCALAPPDATA%\Packages\PerplexityAI.PerplexityApp_3jh4kjrg4dzr2\LocalCache\Roaming\Perplexity\Network\Cookies")
    pplx_app_ls_src = os.path.expandvars(r"%LOCALAPPDATA%\Packages\PerplexityAI.PerplexityApp_3jh4kjrg4dzr2\LocalCache\Roaming\Perplexity\Local State")
    pplx_app_db_dst = os.path.join(work_dir, "PerplexityApp_Cookies.sqlite")

    comet_copied = False
    if os.path.exists(comet_db_src):
        try:
            shutil.copyfile(comet_db_src, comet_db_dst)
            comet_copied = True
            print("Successfully copied Comet Cookies database!")
        except Exception as e:
            print(f"Failed to copy Comet Cookies: {e}")

    pplx_copied = False
    if os.path.exists(pplx_app_db_src):
        try:
            shutil.copyfile(pplx_app_db_src, pplx_app_db_dst)
            pplx_copied = True
            print("Successfully copied Perplexity App Cookies database!")
        except Exception as e:
            print(f"Failed to copy Perplexity App Cookies: {e}")

    # Immediately relaunch Comet browser so user isn't interrupted
    comet_exe = os.path.expandvars(r"%LOCALAPPDATA%\Perplexity\Comet\Application\comet.exe")
    if os.path.exists(comet_exe):
        print("2. Re-launching Comet browser...")
        subprocess.Popen([comet_exe])

    all_cookies = {}

    if comet_copied and os.path.exists(comet_ls_src):
        print("3. Decrypting Comet master key and cookies...")
        try:
            comet_key = get_master_key(comet_ls_src)
            comet_cookies = read_cookies_from_db(comet_db_dst, comet_key)
            print(f"   Found {len(comet_cookies)} cookies in Comet browser")
            all_cookies.update(comet_cookies)
        except Exception as e:
            print(f"   Error reading Comet: {e}")

    if pplx_copied and os.path.exists(pplx_app_ls_src):
        print("4. Decrypting Perplexity App master key and cookies...")
        try:
            pplx_key = get_master_key(pplx_app_ls_src)
            pplx_cookies = read_cookies_from_db(pplx_app_db_dst, pplx_key)
            print(f"   Found {len(pplx_cookies)} cookies in Perplexity App")
            all_cookies.update(pplx_cookies)
        except Exception as e:
            print(f"   Error reading Perplexity App: {e}")

    print("\nAll extracted Perplexity cookies:")
    for name, cinfo in all_cookies.items():
        print(f" - {name} ({cinfo['domain']}): {cinfo['value'][:30]}...")

    session_token = None
    if "__Secure-next-auth.session-token" in all_cookies:
        session_token = all_cookies["__Secure-next-auth.session-token"]["value"]
    else:
        for name, cinfo in all_cookies.items():
            if "session-token" in name.lower() or "next-auth" in name.lower():
                session_token = cinfo["value"]
                break

    if session_token:
        print("\n=======================================================")
        print("PERPLEXITY SESSION TOKEN EXTRACTED SUCCESSFULLY!")
        print(f"Token length: {len(session_token)}")
        print(f"Token preview: {session_token[:20]}...{session_token[-15:]}")
        print("=======================================================")

        env_path = os.path.join(work_dir, ".env")
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(f"PERPLEXITY_SESSION_TOKEN={session_token}\n")
            f.write("PERPLEXITY_API_KEY=local-session\n")
            f.write("PPLX_API_PORT=8000\n")
            f.write("PPLX_API_HOST=127.0.0.1\n")
        print(f"Saved configuration to {env_path}")
    else:
        print("\nWARNING: __Secure-next-auth.session-token not found.")
        sys.exit(1)

if __name__ == "__main__":
    main()
