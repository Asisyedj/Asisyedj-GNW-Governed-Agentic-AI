"""Load runtime configuration; keep secrets in memory only."""
import json, pathlib

def load_config(args):
    # Load cookies file – do NOT write back to disk
    with open(args.cookies, "r", encoding="utf-8") as f:
        cookies = json.load(f)
    # Define the set of attacks (can be extended later)
    attack_set = [
        "XSS",
        "SQLi",
        "CSRF",
        "RCE",
        "SSRF",
        "Directory Traversal",
        "Open Redirect",
        "XXE",
        "Header Injection",
    ]
    return type("Cfg", (), {
        "target": args.target,
        "cookies": cookies,
        "password": args.password,
        "model": args.model,
        "attack_set": attack_set,
    })
