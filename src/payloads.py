"""Utilities to ask Perplexity for attack payloads.
We call the `perplexity_ask` MCP tool (lazy) with a prompt like:
"Generate XSS payloads for the endpoint /search?q=... targeting Chrome.
Return a JSON array of payload objects with fields: method, url, body."
"""
import json
from .mcp_tools import perplexity_ask

def generate_payloads(target: str, model: str, attack_set: list):
    payloads = []
    for atk in attack_set:
        prompt = f"Generate a {atk} payload against {target}. Return a JSON array of objects with keys: method, url, headers (optional), body (optional)."
        response = perplexity_ask(model=model, prompt=prompt)
        try:
            payloads.extend(json.loads(response))
        except Exception:
            # fallback: treat raw response as a single payload placeholder
            payloads.append({"raw": response, "attack": atk})
    return payloads
