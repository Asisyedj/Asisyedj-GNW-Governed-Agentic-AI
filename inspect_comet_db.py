import os
import sys
import json
import base64
import sqlite3
import ctypes
from ctypes import wintypes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

class DATA_BLOB(ctypes.Structure):
    _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_byte))]

def decrypt_dpapi(encrypted_bytes: bytes) -> bytes:
    pDataIn = DATA_BLOB(len(encrypted_bytes), ctypes.cast(ctypes.create_string_buffer(encrypted_bytes), ctypes.POINTER(ctypes.c_byte)))
    pDataOut = DATA_BLOB()
    if ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(pDataIn), None, None, None, None, 1, ctypes.byref(pDataOut)):
        result = ctypes.string_at(pDataOut.pbData, pDataOut.cbData)
        ctypes.windll.kernel32.LocalFree(pDataOut.pbData)
        return result
    raise RuntimeError('DPAPI failed')

def get_master_key(local_state_path: str) -> bytes:
    with open(local_state_path, 'r', encoding='utf-8') as f:
        local_state = json.load(f)
    encrypted_key = base64.b64decode(local_state['os_crypt']['encrypted_key'])
    return decrypt_dpapi(encrypted_key[5:])

def decrypt_raw(encrypted_val: bytes, master_key: bytes) -> bytes:
    if not encrypted_val:
        return b''
    if encrypted_val.startswith(b'v10') or encrypted_val.startswith(b'v11'):
        nonce = encrypted_val[3:15]
        ciphertext = encrypted_val[15:]
        aesgcm = AESGCM(master_key)
        return aesgcm.decrypt(nonce, ciphertext, None)
    return decrypt_dpapi(encrypted_val)

ls_path = os.path.expandvars(r'%LOCALAPPDATA%\Perplexity\Comet\User Data\Local State')
master_key = get_master_key(ls_path)

db_path = r'D:\GNW\perplexity-browser-api\Comet_Cookies.sqlite'
conn = sqlite3.connect(db_path)
c = conn.cursor()
c.execute("SELECT host_key, name, encrypted_value FROM cookies WHERE host_key LIKE '%perplexity%'")
rows = c.fetchall()

all_cookies = {}
for host_key, name, enc in rows:
    try:
        raw_val = decrypt_raw(enc, master_key)
        # In recent Chromium (v127+ / v130+), cookie values can have a 32-byte hash or binary prefix or be plain text
        all_cookies.setdefault(name, []).append((host_key, raw_val))
    except Exception as e:
        print(f"Error {name}: {e}")

conn.close()

# Look at session token
tokens = all_cookies.get('__Secure-next-auth.session-token', [])
for host, raw_val in tokens:
    print(f"\nHost: {host}, length: {len(raw_val)}")
    print(f"First 40 bytes: {list(raw_val[:40])}")
    # Check if text
    try:
        txt = raw_val.decode('utf-8')
        print(f"Decoded UTF8 length: {len(txt)}")
        print(f"Start: {repr(txt[:30])}")
    except Exception as e:
        print(f"Decode error: {e}")
        # In Chromium 130+, does it have a 32-byte SHA256 header?
        try:
            txt = raw_val[32:].decode('utf-8')
            print(f"Decoded UTF8 [32:] length: {len(txt)}")
            print(f"Start [32:]: {repr(txt[:30])}")
        except Exception as e2:
            print(f"Decode [32:] error: {e2}")
