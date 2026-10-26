import os
from pathlib import Path

files_to_delete = [
    'test_supervisor.py',
    'test_simple.py',
    'test_router_integration.py',
    'test_persistence3.py',
    'test_persistence2.py',
    'test_persistence.py',
    'run_simple_test.py',
    'run_router_tests.py',
    'run_import_test2.py',
    'run_import_test.py',
    'run_existing_tests.py',
    'run_all_tests.py',
    'run_supervisor_test2.py',
    'run_supervisor_test.py',
    'run_single_test.py',
    'run_tests.py',
    'cleanup_db.py',
]

base = Path('D:/GNW/perplexity-browser-api')
for f in files_to_delete:
    p = base / f
    if p.exists():
        p.unlink()
        print(f"Deleted {f}")

print("Cleanup done")