"""Cross-channel dedup tracker.

Tracks every source URL ever used by any channel in the empire.
Prevents the same clip from being posted by multiple channels or twice
on the same channel.

State stored in `source_clips` table (auto-migrated by data/migrate.py).
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import List, Optional

from engine.ingest.base import RawClip


DATABASE_PATH = "data/clip_empire.db"


class DedupTracker:
    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path
        self._ensure_table()

    def _ensure_table(self) -> None:
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS source_clips (
                clip_id TEXT PRIMARY KEY,
                source_url TEXT NOT NULL,
                url_hash TEXT NOT NULL,
                platform TEXT,
                creator TEXT,
                title TEXT,
                channel_name TEXT,
                download_path TEXT,
                duration_s REAL,
                view_count INTEGER,
                used_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'downloaded'
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_source_clips_url_hash ON source_clips(url_hash)")
        conn.commit()
        conn.close()

    @staticmethod
    def _url_hash(url: str) -> str:
        """Normalize a URL to a dedup key.

        Strips query params that don't affect identity (like ?si= tracking).
        """
        import hashlib
        # Strip common tracking params
        import urllib.parse as up
        try:
            parsed = up.urlparse(url)
            # Keep only path + video ID params
            qs = up.parse_qs(parsed.query)
            keep = {k: v for k, v in qs.items() if k in ("v", "list", "id")}
            clean = parsed._replace(query=up.urlencode(keep, doseq=True), fragment="")
            normalized = up.urlunparse(clean).rstrip("/")
        except Exception:
            normalized = url
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def is_used(self, clip: RawClip, channel_name: str = "") -> bool:
        """Return True if this source URL has been used by ANY channel."""
        url_hash = self._url_hash(clip.source_url)
        conn = sqlite3.connect(self.db_path)
        cur = conn.execute(
            "SELECT 1 FROM source_clips WHERE url_hash = ? LIMIT 1", (url_hash,)
        )
        result = cur.fetchone() is not None
        conn.close()
        return result

    def is_used_by_channel(self, clip: RawClip, channel_name: str) -> bool:
        """Return True only if used by this specific channel."""
        url_hash = self._url_hash(clip.source_url)
        conn = sqlite3.connect(self.db_path)
        cur = conn.execute(
            "SELECT 1 FROM source_clips WHERE url_hash = ? AND channel_name = ? LIMIT 1",
            (url_hash, channel_name),
        )
        result = cur.fetchone() is not None
        conn.close()
        return result

    def filter_unused(self, clips: List[RawClip], channel_name: str = "", global_dedup: bool = True) -> List[RawClip]:
        """Filter clips list to only those not previously used.

        global_dedup=True:  skip if used by ANY channel (strict, avoids cross-posting)
        global_dedup=False: skip only if used by this specific channel
        """
        result = []
        for clip in clips:
            if global_dedup and self.is_used(clip):
                print(f"[dedup] Skipping (global) used: {clip.source_url[:60]}")
                continue
            if not global_dedup and self.is_used_by_channel(clip, channel_name):
                print(f"[dedup] Skipping (channel) used: {clip.source_url[:60]}")
                continue
            result.append(clip)
        return result

    def mark_used(self, clip: RawClip, channel_name: str) -> None:
        """Record a clip as used by a channel."""
        url_hash = self._url_hash(clip.source_url)
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT OR IGNORE INTO source_clips
                    (clip_id, source_url, url_hash, platform, creator, title,
                     channel_name, download_path, duration_s, view_count, used_at, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                clip.clip_id,
                clip.source_url,
                url_hash,
                clip.platform,
                clip.creator,
                clip.title,
                channel_name,
                clip.download_path,
                clip.duration_s,
                clip.view_count,
                datetime.utcnow().isoformat(),
                "used",
            ))
            conn.commit()
        finally:
            conn.close()
