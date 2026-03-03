"""Auto-recovery watchdog scaffold."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta


def recover_stale_jobs(db_path: str = "data/clip_empire.db", stale_minutes: int = 45) -> int:
    conn = sqlite3.connect(db_path)
    cutoff = (datetime.utcnow() - timedelta(minutes=stale_minutes)).isoformat()
    cur = conn.execute(
        """
        UPDATE publish_jobs
        SET status = 'queued',
            last_error = COALESCE(last_error, '') || ' [watchdog recovered stale running job]',
            updated_at = ?
        WHERE status = 'running' AND updated_at < ?
        """,
        (datetime.utcnow().isoformat(), cutoff),
    )
    conn.commit()
    recovered = cur.rowcount if cur.rowcount is not None else 0
    conn.close()
    return recovered
