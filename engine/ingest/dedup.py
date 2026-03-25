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
from engine.ingest.fingerprint import url_fingerprint


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
        conn.execute("""
            CREATE TABLE IF NOT EXISTS clip_fingerprints (
                clip_id TEXT PRIMARY KEY,
                channel_name TEXT,
                url_fp TEXT,
                visual_fp TEXT,
                transcript_fp TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_clip_fp_url ON clip_fingerprints(url_fp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_clip_fp_visual ON clip_fingerprints(visual_fp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_clip_fp_transcript ON clip_fingerprints(transcript_fp)")
        conn.commit()
        conn.close()

    @staticmethod
    def _url_hash(url: str) -> str:
        """Normalize a URL to a stable dedup key.

        For Twitch clips: extracts the clip slug (stable across URL variants).
        Two URL formats refer to the same clip:
          https://www.twitch.tv/{channel}/clip/{slug}
          https://clips.twitch.tv/{slug}
        We hash the slug only so both formats dedup correctly.
        """
        import urllib.parse as up
        import re
        url = (url or "").strip()
        # Extract Twitch clip slug
        m = re.search(r'/clip/([A-Za-z0-9_-]+)', url)
        if not m:
            # Try clips.twitch.tv/{slug} format
            m = re.search(r'clips\.twitch\.tv/([A-Za-z0-9_-]+)', url)
        if m:
            slug = m.group(1)
            return url_fingerprint("twitch:clip:" + slug)[:16]
        # Fallback: normalize URL (strip query/fragment/trailing slash)
        try:
            parsed = up.urlparse(url)
            qs = up.parse_qs(parsed.query)
            keep = {k: v for k, v in qs.items() if k in ("v", "list", "id")}
            clean = parsed._replace(query=up.urlencode(keep, doseq=True), fragment="")
            normalized = up.urlunparse(clean).rstrip("/")
        except Exception:
            normalized = url
        return url_fingerprint(normalized)[:16]

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

    def is_near_duplicate(self, clip: RawClip) -> bool:
        """Scaffold for dedup v2.

        Current behavior: exact match on any non-empty fingerprint field.
        Future behavior can swap to distance-based visual/transcript matching.
        """
        fingerprints = [
            ("url_fp", clip.url_fingerprint),
            ("visual_fp", clip.visual_fingerprint),
            ("transcript_fp", clip.transcript_fingerprint),
        ]
        conn = sqlite3.connect(self.db_path)
        try:
            for col, fp in fingerprints:
                if not fp:
                    continue
                cur = conn.execute(f"SELECT 1 FROM clip_fingerprints WHERE {col} = ? LIMIT 1", (fp,))
                if cur.fetchone() is not None:
                    return True
            return False
        finally:
            conn.close()

    def register_fingerprint(self, clip: RawClip, channel_name: str) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO clip_fingerprints
                    (clip_id, channel_name, url_fp, visual_fp, transcript_fp, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    clip.clip_id,
                    channel_name,
                    clip.url_fingerprint,
                    clip.visual_fingerprint,
                    clip.transcript_fingerprint,
                    datetime.utcnow().isoformat(),
                ),
            )
            conn.commit()
        finally:
            conn.close()

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
        self.register_fingerprint(clip, channel_name)
