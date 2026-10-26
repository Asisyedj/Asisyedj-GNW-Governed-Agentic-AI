import os
import sys
import json
import base64
import sqlite3
import tempfile
from pathlib import Path

try:
    import win32crypt
    import win32file
    import win32con
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
except ImportError as e:
    print(f"Error importing modules: {e}")
    sys.exit(1)

def copy_locked_file(src_path, dest_path):
    handle = win32file.CreateFile(
        str(src_path),
        win32con.GENERIC_READ,
        win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE | win32con.FILE_SHARE_DELETE,
        None,
        win32con.OPEN_EXISTING,
        win32con.FILE_ATTRIBUTE_NORMAL,
        None
    )
    # Read up to 200MB
    _, data = win32file.ReadFile(handle, 200 * 1024 * 1024)
    win32file.CloseHandle(handle)
    with open(dest_path, "wb") as f:
        f.write(data)

def get_perplexity_session_token():
    pkg_dir = Path(r"C:\Users\asisy\AppData\Local\Packages\PerplexityAI.PerplexityApp_3jh4kjrg4dzr2\LocalCache\Roaming\Perplexity")
    local_state_path = pkg_dir / "Local State"
    cookies_path = pkg_dir / "Network" / "Cookies"

    if not local_state_path.exists() or not cookies_path.exists():
        print("Perplexity app Local State or Cookies file not found.")
        return None

    # 1. Read encrypted master key from Local State
    with open(local_state_path, "r", encoding="utf-8") as f:
        local_state = json.load(f)
    
    b64_key = local_state["os_crypt"]["encrypted_key"]
    raw_key = base64.b64decode(b64_key)
    dpapi_key = raw_key[5:]
    master_key = win32crypt.CryptUnprotectData(dpapi_key, None, None, None, 0)[1]

    # 2. Copy Cookies SQLite database using win32file (bypassing app lock)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        tmp_cookies = tmp.name
    
    try:
        copy_locked_file(cookies_path, tmp_cookies)
        conn = sqlite3.connect(tmp_cookies)
        cursor = conn.cursor()

        # Query cookies for perplexity.ai
        cursor.execute("""
            SELECT name, encrypted_value 
            FROM cookies 
            WHERE host_key LIKE '%perplexity.ai%'
        """)
        rows = cursor.fetchall()
        print(f"Found {len(rows)} cookies for perplexity.ai")

        token = None
        for name, enc_val in rows:
            if "session-token" in name.lower() or name == "__Secure-next-auth.session-token":
                if enc_val.startswith(b"v10") or enc_val.startswith(b"v11"):
                    nonce = enc_val[3:15]
                    ciphertext = enc_val[15:]
                    aesgcm = AESGCM(master_key)
                    decrypted_bytes = aesgcm.decrypt(nonce, ciphertext, None)
                    token = decrypted_bytes.decode("utf-8")
                    print(f"Successfully decrypted session token for cookie: {name} (Length: {len(token)})")
                    break

        conn.close()
        return token
    finally:
        if os.path.exists(tmp_cookies):
            os.remove(tmp_cookies)

def main():
    token = get_perplexity_session_token()
    if not token:
        print("Failed to find session token in Perplexity App storage.")
        sys.exit(1)

    env_path = Path(r"D:\GNW\perplexity-browser-api\.env")
    env_content = f"""# Auto-synced from Perplexity Windows Desktop App
PERPLEXITY_SESSION_TOKEN={token}
PERPLEXITY_API_KEY=local-session
PPLX_API_PORT=8000
"""
    with open(env_path, "w", encoding="utf-8") as f:
        f.write(env_content)
    
    print(f"Wrote session token to {env_path}")
    print("TOKEN_EXTRACT_SUCCESS")

if __name__ == "__main__":
    main()
