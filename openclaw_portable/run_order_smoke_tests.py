#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TESTS = sorted(ROOT.glob('skills/**/test_order_smoke.py'))
EXPECTED = 7

print(f'Discovered {len(TESTS)} package test files; expected {EXPECTED}.')
if len(TESTS) != EXPECTED:
    print('FAIL: package test inventory is incomplete.', file=sys.stderr)
    for test in TESTS:
        print(f'  found: {test.relative_to(ROOT)}', file=sys.stderr)
    raise SystemExit(2)

failed: list[tuple[Path, int]] = []
for test in TESTS:
    relative = test.relative_to(ROOT)
    print(f'=== {relative} ===', flush=True)
    completed = subprocess.run([sys.executable, str(test)], cwd=str(test.parent), check=False)
    if completed.returncode != 0:
        failed.append((relative, completed.returncode))

if failed:
    print('FAILED PACKAGE TEST FILES:', file=sys.stderr)
    for path, code in failed:
        print(f'  {path}: exit {code}', file=sys.stderr)
    raise SystemExit(2)

print(f'PASS: all {EXPECTED} package test files completed successfully.')
