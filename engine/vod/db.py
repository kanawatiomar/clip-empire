"""DB helpers for VOD segments table.

Schema:
    vod_segments — one row per extracted highlight clip from a Twitch VOD.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

_DB_PATH = Path(__file__).parents[2] / "data" / "clip_empire.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS vod_segments (
            segment_id    TEXT PRIMARY KEY,
            vod_id        TEXT NOT NULL,
            vod_url       TEXT NOT NULL,
            creator       TEXT NOT NULL,
            channel_name  TEXT NOT NULL,
            start_ts      REAL NOT NULL,
            end_ts        REAL NOT NULL,
            duration_s    REAL NOT NULL,
            energy_score  REAL DEFAULT 0.0,
            clip_path     TEXT,
            status        TEXT NOT NULL DEFAULT 'ready'
                              CHECK(status IN ('ready','used_short','used_montage','exhausted')),
            created_at    TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_vod_seg_creator
            ON vod_segments(creator, status);
        CREATE INDEX IF NOT EXISTS idx_vod_seg_channel
            ON vod_segments(channel_name, status);
        CREATE INDEX IF NOT EXISTS idx_vod_seg_vod
            ON vod_segments(vod_id);
    """)
    conn.commit()


# ── Write ──────────────────────────────────────────────────────────────────

def insert_segment(
    vod_id: str,
    vod_url: str,
    creator: str,
    channel_name: str,
    start_ts: float,
    end_ts: float,
    energy_score: float = 0.0,
    clip_path: str = "",
) -> str:
    """Insert a new VOD segment and return its segment_id."""
    segment_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    duration_s = end_ts - start_ts
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO vod_segments
                (segment_id, vod_id, vod_url, creator, channel_name,
                 start_ts, end_ts, duration_s, energy_score, clip_path, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (segment_id, vod_id, vod_url, creator, channel_name,
             start_ts, end_ts, duration_s, energy_score, clip_path, now),
        )
        conn.commit()
    return segment_id


def update_clip_path(segment_id: str, clip_path: str) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE vod_segments SET clip_path = ? WHERE segment_id = ?",
            (clip_path, segment_id),
        )
        conn.commit()


def mark_used(segment_id: str, usage_type: str = "used_short") -> None:
    """Mark a segment as consumed. usage_type: 'used_short' | 'used_montage'."""
    with _connect() as conn:
        conn.execute(
            "UPDATE vod_segments SET status = ? WHERE segment_id = ?",
            (usage_type, segment_id),
        )
        conn.commit()


# ── Read ───────────────────────────────────────────────────────────────────

def vod_already_processed(vod_id: str) -> bool:
    """True if we already extracted highlights from this VOD."""
    with _connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM vod_segments WHERE vod_id = ? LIMIT 1",
            (vod_id,),
        ).fetchone()
    return row is not None


def get_ready_segments(
    creator: str,
    channel_name: str,
    limit: int = 10,
    min_energy: float = 0.0,
) -> list[dict]:
    """Return ready (unused) segments for a creator, sorted by energy desc."""
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM vod_segments
            WHERE creator = ?
              AND channel_name = ?
              AND status = 'ready'
              AND energy_score >= ?
              AND clip_path IS NOT NULL
              AND clip_path != ''
            ORDER BY energy_score DESC, created_at DESC
            LIMIT ?
            """,
            (creator, channel_name, min_energy, limit),
        ).fetchall()
    return [dict(r) for r in rows]


def segment_count(
    creator: str,
    channel_name: str,
    status: str = "ready",
) -> int:
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM vod_segments WHERE creator=? AND channel_name=? AND status=?",
            (creator, channel_name, status),
        ).fetchone()
    return row[0] if row else 0
