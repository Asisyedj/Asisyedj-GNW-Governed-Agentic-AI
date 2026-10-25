"""SQLite‑backed personal memory for the agent.

The schema stores arbitrary key/value pairs per user, with a Unix timestamp.
"""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any, List, Tuple

DB_PATH = Path(__file__).parent.parent / "data" / "memory.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS facts (
            user_id TEXT NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            ts INTEGER NOT NULL,
            PRIMARY KEY (user_id, key)
        )
        """
    )
    return conn


def add_fact(user_id: str, key: str, value: Any, ts: int | None = None) -> None:
    """Insert or replace a fact for a user.

    ``value`` is stored as JSON‑compatible text via ``repr``; callers should ensure
    it is serialisable.
    """
    if ts is None:
        ts = int(time.time())
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO facts (user_id, key, value, ts) VALUES (?, ?, ?, ?)",
        (user_id, key, repr(value), ts),
    )
    conn.commit()
    conn.close()


def get_fact(user_id: str, key: str) -> Tuple[Any, int] | None:
    """Return ``(value, ts)`` for the given ``key`` or ``None`` if absent."""
    conn = _get_conn()
    cur = conn.execute(
        "SELECT value, ts FROM facts WHERE user_id = ? AND key = ?", (user_id, key)
    )
    row = cur.fetchone()
    conn.close()
    if row:
        value_str, ts = row
        try:
            value = eval(value_str)  # simple eval for primitive types; safe because we control writes
        except Exception:
            value = value_str
        return value, ts
    return None


def search_facts(user_id: str, pattern: str) -> List[Tuple[str, Any, int]]:
    """Return a list of ``(key, value, ts)`` where ``key`` LIKE ``%pattern%``.
    """
    conn = _get_conn()
    cur = conn.execute(
        "SELECT key, value, ts FROM facts WHERE user_id = ? AND key LIKE ?",
        (user_id, f"%{pattern}%"),
    )
    rows = [(k, eval(v) if v else v, t) for k, v, t in cur.fetchall()]
    conn.close()
    return rows
