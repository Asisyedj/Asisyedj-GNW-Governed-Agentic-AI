"""Test suite for the personal agent plugins.

Run with ``pytest -q``.
"""

# Ensure the repository root is on PYTHONPATH for imports
import sys, os
repo_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if repo_root not in sys.path:
    sys.path.append(repo_root)
