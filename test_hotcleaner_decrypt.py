import json
import base64
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

uploaded_json = r"C:\Users\asisy\.gemini\antigravity\brain\83b326c1-5060-42ff-a761-07b92c7707c4\.user_uploaded\media_1792580470653_ef60ef11.json"

with open(uploaded_json, "r", encoding="utf-8") as f:
    payload = json.load(f)

b64_data = payload["data"]
raw_bytes = base64.b64decode(b64_data)
iv = raw_bytes[:12]
ciphertext = raw_bytes[12:]

def try_decrypt(password: str):
    pw_bytes = password.encode("utf-8")
    salt_bytes = (password + password).encode("utf-8")
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt_bytes,
        iterations=1024,
    )
    key = kdf.derive(pw_bytes)
    aesgcm = AESGCM(key)
    try:
        decrypted = aesgcm.decrypt(iv, ciphertext, None)
        return decrypted.decode("utf-8")
    except Exception:
        return None

candidates = [
    "", " ", "1", "123", "1234", "12345", "123456", "12345678", "123456789",
    "password", "admin", "comet", "perplexity", "gnw", "opencode", "asisy",
    "cookie", "cookies", "test", "root", "112233", "user", "Asisy", "Asis", "0000"
]

found = None
for p in candidates:
    res = try_decrypt(p)
    if res:
        found = (p, res)
        print(f"MATCH FOUND! Password is: {repr(p)}")
        break

if not found:
    print("None of the common candidate passwords matched.")
else:
    print(f"Decrypted length: {len(found[1])}")
    print(f"Preview: {found[1][:200]}")
    # Save decrypted
    with open(r"D:\GNW\perplexity-browser-api\decrypted_cookies.json", "w", encoding="utf-8") as f_out:
        f_out.write(found[1])
    print("Saved decrypted cookies to D:\\GNW\\perplexity-browser-api\\decrypted_cookies.json")
