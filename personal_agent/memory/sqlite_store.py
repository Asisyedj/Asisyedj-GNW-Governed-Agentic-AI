"""SQLite‑backed personal memory for the agent.

The schema stores arbitrary key/value pairs per user, with a Unix timestamp.
Values are serialized safely with JSON to avoid arbitrary code execution.
"""

from __future__ import annotations

import json
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


def _serialize_value(value: Any) -> str:
    """Serialize value safely to JSON string."""
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return json.dumps(str(value), ensure_ascii=False)


def _deserialize_value(value_str: str) -> Any:
    """Safely deserialize JSON string without using eval."""
    try:
        return json.loads(value_str)
    except (json.JSONDecodeError, TypeError):
        return value_str


def add_fact(user_id: str, key: str, value: Any, ts: int | None = None) -> None:
    """Insert or replace a fact for a user.

    ``value`` is stored as JSON text safely.
    """
    if ts is None:
        ts = int(time.time())
    serialized = _serialize_value(value)
    conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO facts (user_id, key, value, ts) VALUES (?, ?, ?, ?)",
        (user_id, key, serialized, ts),
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
        return _deserialize_value(value_str), ts
    return None


def search_facts(user_id: str, pattern: str) -> List[Tuple[str, Any, int]]:
    """Return a list of ``(key, value, ts)`` where ``key`` LIKE ``%pattern%``."""
    conn = _get_conn()
    cur = conn.execute(
        "SELECT key, value, ts FROM facts WHERE user_id = ? AND key LIKE ?",
        (user_id, f"%{pattern}%"),
    )
    rows = [(k, _deserialize_value(v), t) for k, v, t in cur.fetchall()]
    conn.close()
    return rows
