# tests/test_reporter.py
import json
import pathlib
import os
from src.reporter import save_report

def test_save_report(tmp_path, monkeypatch):
    target = "https://www.perplexity.ai/"
    results = [{"payload": {"method": "GET", "url": target}, "status": "executed"}]
    # Temporarily change the repository root to the temporary directory
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    # Create a dummy src package inside repo_root so imports work
    (repo_root / "src").mkdir()
    (repo_root / "src" / "__init__.py").write_text("")
    # Copy reporter module into the temporary src (simplified for test)
    # Instead, adjust PYTHONPATH to include actual src directory
    monkeypatch.setenv("PYTHONPATH", str(pathlib.Path.cwd() / "src"))
    # Run save_report; it will create data/reports under actual repo root, but that's fine for test
    out_path = save_report(target, results)
    assert pathlib.Path(out_path).exists()
    data = json.loads(pathlib.Path(out_path).read_text())
    assert data["target"] == target
    assert data["results"] == results
