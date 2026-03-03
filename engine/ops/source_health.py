"""Source health monitor for ingestion reliability."""

from __future__ import annotations

import sqlite3


class SourceHealthMonitor:
    def __init__(self, db_path: str = "data/clip_empire.db"):
        self.db_path = db_path
        self._ensure_table()

    def _ensure_table(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS source_health (
                source_key TEXT PRIMARY KEY,
                success_count INTEGER NOT NULL DEFAULT 0,
                failure_count INTEGER NOT NULL DEFAULT 0,
                last_error TEXT,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def is_healthy(self, source_key: str, max_fail_ratio: float = 0.8, min_events: int = 3) -> bool:
        conn = sqlite3.connect(self.db_path)
        row = conn.execute(
            "SELECT success_count, failure_count FROM source_health WHERE source_key = ?",
            (source_key,),
        ).fetchone()
        conn.close()
        if not row:
            return True
        success, failure = row
        total = success + failure
        if total < min_events:
            return True
        return (failure / max(total, 1)) < max_fail_ratio

    def record_success(self, source_key: str) -> None:
        self._upsert(source_key, success_inc=1)

    def record_failure(self, source_key: str, error: str = "") -> None:
        self._upsert(source_key, failure_inc=1, last_error=error)

    def _upsert(self, source_key: str, success_inc: int = 0, failure_inc: int = 0, last_error: str = "") -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """
            INSERT INTO source_health (source_key, success_count, failure_count, last_error)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(source_key) DO UPDATE SET
                success_count = success_count + ?,
                failure_count = failure_count + ?,
                last_error = CASE WHEN ? != '' THEN ? ELSE last_error END,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                source_key,
                success_inc,
                failure_inc,
                last_error,
                success_inc,
                failure_inc,
                last_error,
                last_error,
            ),
        )
        conn.commit()
        conn.close()
