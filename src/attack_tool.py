"""Entry point for the Perplexity‑powered attack framework.

Usage::
    python -m src.attack_tool --target https://staging.example.com \
        --cookies path/to/cookies.json [--password 1234]
"""

import argparse
from .config import load_config
from .bridge_client import BridgeClient
from .payloads import generate_payloads
from .reporter import save_report

def main():
    parser = argparse.ArgumentParser(description="Perplexity attack framework")
    parser.add_argument("--target", required=True, help="Base URL of the site to test (staging only)")
    parser.add_argument("--cookies", required=True, help="Path to cookies JSON file")
    parser.add_argument("--password", help="Optional password for basic auth")
    parser.add_argument("--model", default="perplexity-gpt-4o-mini", help="Perplexity model identifier")
    args = parser.parse_args()

    cfg = load_config(args)

    bridge = BridgeClient()
    bridge.start()

    payloads = generate_payloads(cfg.target, cfg.model, cfg.attack_set)

    results = []
    for p in payloads:
        res = bridge.run_payload(p, cfg)
        results.append(res)

    save_report(cfg.target, results)
    bridge.stop()

if __name__ == "__main__":
    main()