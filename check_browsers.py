import os
import sys
import json
import base64
import sqlite3
import shutil
import tempfile
from pathlib import Path

import win32crypt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

def check_browser(browser_name, local_state_path, cookies_path):
    if not os.path.exists(local_state_path) or not os.path.exists(cookies_path):
        return None
    try:
        with open(local_state_path, "r", encoding="utf-8") as f:
            local_state = json.load(f)
        b64_key = local_state["os_crypt"]["encrypted_key"]
        raw_key = base64.b64decode(b64_key)[5:]
        master_key = win32crypt.CryptUnprotectData(raw_key, None, None, None, 0)[1]

        with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
            tmp_cookies = tmp.name
        
        try:
            shutil.copyfile(cookies_path, tmp_cookies)
            conn = sqlite3.connect(tmp_cookies)
            cursor = conn.cursor()
            cursor.execute("SELECT name, encrypted_value FROM cookies WHERE host_key LIKE '%perplexity.ai%'")
            rows = cursor.fetchall()
            for name, enc_val in rows:
                if "session-token" in name.lower():
                    nonce = enc_val[3:15]
                    ciphertext = enc_val[15:]
                    aesgcm = AESGCM(master_key)
                    decrypted = aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")
                    conn.close()
                    return decrypted
            conn.close()
        finally:
            if os.path.exists(tmp_cookies):
                os.remove(tmp_cookies)
    except Exception as e:
        print(f"Error checking {browser_name}: {e}")
    return None

# Check Chrome
chrome_ls = r"C:\Users\asisy\AppData\Local\Google\Chrome\User Data\Local State"
chrome_ck = r"C:\Users\asisy\AppData\Local\Google\Chrome\User Data\Default\Network\Cookies"
t_chrome = check_browser("Chrome", chrome_ls, chrome_ck)
if t_chrome:
    print(f"FOUND_IN_CHROME: len={len(t_chrome)}")

# Check Edge
edge_ls = r"C:\Users\asisy\AppData\Local\Microsoft\Edge\User Data\Local State"
edge_ck = r"C:\Users\asisy\AppData\Local\Microsoft\Edge\User Data\Default\Network\Cookies"
t_edge = check_browser("Edge", edge_ls, edge_ck)
if t_edge:
    print(f"FOUND_IN_EDGE: len={len(t_edge)}")

if not t_chrome and not t_edge:
    print("NOT_FOUND_IN_CHROME_OR_EDGE")
