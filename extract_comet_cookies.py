import os
import sys
import json
import base64
import sqlite3
import shutil
import tempfile
import ctypes
from ctypes import wintypes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# Windows DPAPI structures
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
    # Strip DPAPI prefix (5 bytes: 'DPAPI')
    if not encrypted_key.startswith(b"DPAPI"):
        raise ValueError("Invalid DPAPI prefix in encrypted_key")
    encrypted_key = encrypted_key[5:]
    return decrypt_dpapi(encrypted_key)

def decrypt_cookie_value(encrypted_val: bytes, master_key: bytes) -> str:
    if not encrypted_val:
        return ""
    # Chromium v10/v11 prefix
    if encrypted_val.startswith(b"v10") or encrypted_val.startswith(b"v11"):
        nonce = encrypted_val[3:15]
        ciphertext = encrypted_val[15:]
        aesgcm = AESGCM(master_key)
        decrypted = aesgcm.decrypt(nonce, ciphertext, None)
        return decrypted.decode("utf-8", errors="replace")
    else:
        # Fallback to direct DPAPI for older or non-v10 entries
        try:
            return decrypt_dpapi(encrypted_val).decode("utf-8", errors="replace")
        except Exception:
            return encrypted_val.decode("utf-8", errors="replace")

def copy_locked_file(src: str, dst: str):
    # Try direct copy first
    try:
        shutil.copyfile(src, dst)
        return
    except Exception:
        pass
    
    # Read with full sharing permissions if locked by running browser
    GENERIC_READ = 0x80000000
    FILE_SHARE_READ = 0x00000001
    FILE_SHARE_WRITE = 0x00000002
    FILE_SHARE_DELETE = 0x00000004
    OPEN_EXISTING = 3
    FILE_ATTRIBUTE_NORMAL = 0x80

    handle = ctypes.windll.kernel32.CreateFileW(
        src,
        GENERIC_READ,
        FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
        None,
        OPEN_EXISTING,
        FILE_ATTRIBUTE_NORMAL,
        None
    )
    if handle == -1 or handle == 0xFFFFFFFF:
        raise RuntimeError(f"Unable to open {src} with sharing: error {ctypes.windll.kernel32.GetLastError()}")
    
    try:
        # Get file size
        file_size = ctypes.wintypes.LARGE_INTEGER()
        ctypes.windll.kernel32.GetFileSizeEx(handle, ctypes.byref(file_size))
        size = file_size.value
        
        buffer = ctypes.create_string_buffer(size)
        bytes_read = wintypes.DWORD()
        if not ctypes.windll.kernel32.ReadFile(handle, buffer, size, ctypes.byref(bytes_read), None):
            raise RuntimeError("ReadFile failed")
        
        with open(dst, "wb") as f_out:
            f_out.write(buffer.raw[:bytes_read.value])
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)

def extract_perplexity_cookies():
    comet_user_data = os.path.expandvars(r"%LOCALAPPDATA%\Perplexity\Comet\User Data")
    local_state_path = os.path.join(comet_user_data, "Local State")
    
    if not os.path.exists(local_state_path):
        print(f"Error: Comet Local State not found at {local_state_path}")
        return None
    
    print("Extracting Comet master encryption key...")
    master_key = get_master_key(local_state_path)
    print("Master key successfully extracted and decrypted!")
    
    # Potential cookie file locations in profiles
    candidate_profiles = ["Default"]
    for item in os.listdir(comet_user_data):
        if item.startswith("Profile ") and os.path.isdir(os.path.join(comet_user_data, item)):
            candidate_profiles.append(item)
            
    found_cookies = {}
    
    for profile in candidate_profiles:
        profile_dir = os.path.join(comet_user_data, profile)
        cookie_paths = [
            os.path.join(profile_dir, "Network", "Cookies"),
            os.path.join(profile_dir, "Cookies")
        ]
        
        for cookie_file in cookie_paths:
            if not os.path.exists(cookie_file):
                continue
            
            print(f"Checking cookies in {cookie_file}...")
            with tempfile.NamedTemporaryFile(delete=False) as temp_db:
                temp_db_path = temp_db.name
            
            try:
                copy_locked_file(cookie_file, temp_db_path)
                conn = sqlite3.connect(temp_db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT host_key, name, encrypted_value FROM cookies WHERE host_key LIKE '%perplexity.ai%'")
                rows = cursor.fetchall()
                print(f"  Found {len(rows)} cookies for perplexity.ai in {profile}")
                
                for host_key, name, encrypted_val in rows:
                    try:
                        val = decrypt_cookie_value(encrypted_val, master_key)
                        found_cookies[name] = val
                        print(f"    - Cookie: {name} (length: {len(val)})")
                    except Exception as e:
                        print(f"    - Error decrypting {name}: {e}")
                
                conn.close()
            finally:
                if os.path.exists(temp_db_path):
                    try:
                        os.remove(temp_db_path)
                    except Exception:
                        pass

    return found_cookies

def main():
    cookies = extract_perplexity_cookies()
    if not cookies:
        print("No Perplexity cookies found in Comet browser!")
        sys.exit(1)
        
    session_token = cookies.get("__Secure-next-auth.session-token")
    if not session_token:
        # Check if there are other session tokens
        for k, v in cookies.items():
            if "session-token" in k or "next-auth" in k:
                session_token = v
                break
                
    if session_token:
        print("\nSUCCESS: Extracted Perplexity session token from Comet browser!")
        print(f"Token preview: {session_token[:15]}...{session_token[-10:]}")
        
        # Write to .env
        env_path = r"D:\GNW\perplexity-browser-api\.env"
        with open(env_path, "w", encoding="utf-8") as f:
            f.write(f"PERPLEXITY_SESSION_TOKEN={session_token}\n")
            f.write("PERPLEXITY_API_KEY=local-session\n")
            f.write("PPLX_API_PORT=8000\n")
            f.write("PPLX_API_HOST=127.0.0.1\n")
        print(f"Saved session token to {env_path}")
        
        # Also save full cookie json for debugging or cookie-based requests
        cookie_export_path = r"D:\GNW\perplexity-browser-api\comet_cookies.json"
        with open(cookie_export_path, "w", encoding="utf-8") as f:
            json.dump(cookies, f, indent=2)
        print(f"Saved all perplexity cookies to {cookie_export_path}")
    else:
        print("\nSession token not found among Perplexity cookies.")
        print("Available cookies:", list(cookies.keys()))
        sys.exit(1)

if __name__ == "__main__":
    main()
