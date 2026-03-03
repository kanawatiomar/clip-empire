"""Lightweight SQLite migrations.

Goal: make the repo plug-and-play on fresh installs *and* safe to pull updates on existing installs.

- Adds missing columns with ALTER TABLE.
- Idempotent.

Run manually:
  python data/migrate.py

Workers should call `ensure_schema()` before DB operations.
"""

from __future__ import annotations

import sqlite3
from typing import Iterable, Tuple

DATABASE_PATH = "data/clip_empire.db"


def _col_exists(conn: sqlite3.Connection, table: str, col: str) -> bool:
    cur = conn.execute(f"PRAGMA table_info({table})")
    return any(r[1] == col for r in cur.fetchall())


def _add_col(conn: sqlite3.Connection, table: str, col_def: str) -> None:
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_def}")


def ensure_schema(db_path: str = DATABASE_PATH) -> None:
    conn = sqlite3.connect(db_path)
    try:
        # channels
        if not _col_exists(conn, "channels", "made_for_kids"):
            _add_col(conn, "channels", "made_for_kids INTEGER NOT NULL DEFAULT 0")

        # publish_jobs
        if not _col_exists(conn, "publish_jobs", "schedule_at_ts"):
            _add_col(conn, "publish_jobs", "schedule_at_ts INTEGER")
        if not _col_exists(conn, "publish_jobs", "next_retry_at_ts"):
            _add_col(conn, "publish_jobs", "next_retry_at_ts INTEGER")

        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    ensure_schema()
    print("OK: migrations applied")
