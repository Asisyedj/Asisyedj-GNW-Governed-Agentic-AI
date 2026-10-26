# tests/test_config.py
import types
import json
import pathlib
from src.config import load_config

def test_load_config(tmp_path):
    # Create a dummy cookies JSON file
    cookies_file = tmp_path / "cookies.json"
    cookies_file.write_text(json.dumps({"session": "abc123"}), encoding="utf-8")

    args = types.SimpleNamespace(
        target="https://www.perplexity.com",
        cookies=str(cookies_file),
        password="1234",
        model="perplexity-gpt-4o-mini",
    )
    cfg = load_config(args)
    assert cfg.target == "https://www.perplexity.com"
    assert cfg.password == "1234"
    assert cfg.model == "perplexity-gpt-4o-mini"
    assert cfg.cookies["session"] == "abc123"
    # Ensure the default attack set includes XSS
    assert "XSS" in cfg.attack_set
