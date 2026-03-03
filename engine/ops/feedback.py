"""Performance feedback loop for source/template scoring."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass
class Score:
    wins: int = 0
    losses: int = 0

    @property
    def value(self) -> float:
        total = self.wins + self.losses
        if total == 0:
            return 0.0
        return (self.wins - self.losses) / total


class PerformanceFeedback:
    def __init__(self, db_path: str = "data/clip_empire.db"):
        self.db_path = db_path
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS source_scores (
                source_key TEXT PRIMARY KEY,
                wins INTEGER NOT NULL DEFAULT 0,
                losses INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS template_scores (
                template_key TEXT PRIMARY KEY,
                wins INTEGER NOT NULL DEFAULT 0,
                losses INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        conn.close()

    def get_source_score(self, source_key: str) -> float:
        conn = sqlite3.connect(self.db_path)
        row = conn.execute("SELECT wins, losses FROM source_scores WHERE source_key = ?", (source_key,)).fetchone()
        conn.close()
        if not row:
            return 0.0
        return Score(wins=row[0], losses=row[1]).value

    def record_source_outcome(self, source_key: str, success: bool) -> None:
        field = "wins" if success else "losses"
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            f"""
            INSERT INTO source_scores (source_key, {field}) VALUES (?, 1)
            ON CONFLICT(source_key) DO UPDATE SET
                {field} = {field} + 1,
                updated_at = CURRENT_TIMESTAMP
            """,
            (source_key,),
        )
        conn.commit()
        conn.close()

    def record_template_outcome(self, template_key: str, success: bool) -> None:
        field = "wins" if success else "losses"
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            f"""
            INSERT INTO template_scores (template_key, {field}) VALUES (?, 1)
            ON CONFLICT(template_key) DO UPDATE SET
                {field} = {field} + 1,
                updated_at = CURRENT_TIMESTAMP
            """,
            (template_key,),
        )
        conn.commit()
        conn.close()
