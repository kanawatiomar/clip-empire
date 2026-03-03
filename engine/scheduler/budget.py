"""Daily upload budget enforcement per channel.

Checks publish_jobs table to count how many jobs were already queued or
succeeded today. Respects the channel's daily_target limit.
"""

from __future__ import annotations

import sqlite3
from datetime import date, datetime


DATABASE_PATH = "data/clip_empire.db"


class BudgetManager:
    """Track and enforce per-channel daily upload quota."""

    # Hard ceiling regardless of channel config (safety valve)
    ABSOLUTE_MAX_PER_DAY = 10

    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path

    def get_daily_target(self, channel_name: str) -> int:
        """Look up channel's configured daily_target from DB."""
        conn = sqlite3.connect(self.db_path)
        cur = conn.execute(
            "SELECT daily_target FROM channels WHERE channel_name = ?",
            (channel_name,),
        )
        row = cur.fetchone()
        conn.close()
        if row:
            return min(row[0], self.ABSOLUTE_MAX_PER_DAY)
        return 3  # safe default

    def get_queued_today(self, channel_name: str) -> int:
        """Count jobs queued or succeeded today (UTC date) for this channel."""
        today = date.today().isoformat()
        conn = sqlite3.connect(self.db_path)
        cur = conn.execute(
            """SELECT COUNT(*) FROM publish_jobs
               WHERE channel_name = ?
                 AND status IN ('queued', 'running', 'succeeded')
                 AND date(created_at) = ?""",
            (channel_name, today),
        )
        count = cur.fetchone()[0]
        conn.close()
        return count

    def slots_remaining(self, channel_name: str) -> int:
        """Return how many more uploads can be queued today for this channel."""
        target = self.get_daily_target(channel_name)
        used = self.get_queued_today(channel_name)
        return max(0, target - used)

    def has_budget(self, channel_name: str) -> bool:
        return self.slots_remaining(channel_name) > 0
