# Perplexity Attack Framework

## Overview
This repository provides a **safe, non‑destructive testing framework** that uses **Perplexity AI models** via the **Chrome DevTools MCP bridge** to generate and execute a wide range of web‑application attack payloads (XSS, SQLi, CSRF, RCE, SSRF, etc.) against a **staging or test instance** of your site.

## Safety Guarantees
- **Read‑only enforcement** – only `GET` and `OPTIONS` requests are allowed; any other HTTP method is automatically skipped.
- **In‑memory secrets** – cookies and optional passwords are loaded into memory only and never written to disk.
- **Sandboxed Chromium** – the bridge runs a headless Chromium instance isolated from production networks. You can route traffic through a local proxy to further restrict outbound connections.
- **Target must be a staging/test URL** – never point the tool at a production domain.

## Quick Start
```bash
# Create a virtual environment (recommended)
python -m venv .venv
. .venv/Scripts/activate   # Windows PowerShell

# Install dependencies
pip install -r requirements.txt

# Run the framework against your staging site
python -m src.attack_tool \
    --target https://staging.example.com \
    --cookies path/to/cookies.json \
    [--password YOUR_PASSWORD] \
    [--model perplexity-gpt-4o-mini]
```
The command will:
1. Load the cookies JSON (in‑memory).
2. Start the MCP bridge daemon.
3. Ask Perplexity for payloads for each configured attack type.
4. Execute the payloads safely inside the sandbox.
5. Save a **JSON report** in `data/reports/` and a **Markdown summary** alongside it.

## Repository Layout
```
perplexity-browser-api/
├─ src/                     # Source code package
│   ├─ __init__.py
│   ├─ attack_tool.py       # CLI entry point
│   ├─ bridge_client.py    # MCP bridge wrapper (read‑only)
│   ├─ config.py           # Runtime configuration loader
│   ├─ payloads.py         # Ask Perplexity for payloads
│   ├─ mcp_tools.py        # Wrapper around `perplexity_ask`
│   └─ reporter.py         # JSON (and optional Markdown) report writer
├─ data/reports/            # Generated reports (git‑ignored)
├─ tests/                   # Minimal test suite
│   ├─ test_config.py
│   └─ test_reporter.py
├─ .gitignore               # Ignore secrets, reports, and build artefacts
├─ README.md                # This file
├─ requirements.txt         # Python dependencies
└─ setup.cfg                # Pytest configuration (optional)
```

## Extending the Framework
- **Add new attack types** – edit `config.load_config` to extend `attack_set`.
- **Change reporting** – modify `reporter.save_report` to also emit Markdown or create GitHub issues.
- **Custom MCP bridge commands** – extend `bridge_client.run_payload` to interact with the MCP protocol directly.

## License
MIT – feel free to fork and adapt.
