"""Clip usage tracker — prevents the same clip appearing in too many videos.

Tracks every time a clip (Twitch slug or URL hash) is used in any video
(montage, short, long-form) so we can avoid recycling content too aggressively.

Usage rules enforced:
  - montage:  clip blocked if used in another montage within MONTAGE_COOLDOWN days
  - short:    clip blocked if used in another short (existing dedup handles this,
              but we also log here for cross-format visibility)
  - cross:    clip used in a short is ALLOWED in a montage (different format),
              but deprioritized in scoring

DB table: clip_usage (in data/clip_empire.db)
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional
import re

_DB_PATH = Path(__file__).parents[2] / "data" / "clip_empire.db"

# How long before a clip can appear in another montage
MONTAGE_COOLDOWN_DAYS = 90

# How long before a clip can appear in another short (cross-format awareness)
SHORT_COOLDOWN_DAYS = 30


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS clip_usage (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            clip_slug    TEXT NOT NULL,
            clip_url     TEXT,
            creator      TEXT,
            channel_name TEXT NOT NULL,
            video_id     TEXT NOT NULL,
            video_type   TEXT NOT NULL CHECK(video_type IN ('montage','short','long')),
            used_at      TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_clip_usage_slug
            ON clip_usage(clip_slug);
        CREATE INDEX IF NOT EXISTS idx_clip_usage_video
            ON clip_usage(video_id);
        CREATE INDEX IF NOT EXISTS idx_clip_usage_type_at
            ON clip_usage(video_type, used_at);
    """)
    conn.commit()


# ── Slug extraction ────────────────────────────────────────────────────────

def extract_slug(url: str) -> str:
    """Extract Twitch clip slug from a clip URL.

    Handles both formats:
      https://www.twitch.tv/{creator}/clip/{slug}
      https://clips.twitch.tv/{slug}

    Falls back to the URL itself (stripped) if no match.
    """
    m = re.search(r'/clip/([^/?&#]+)', url)
    if m:
        return m.group(1)
    m = re.search(r'clips\.twitch\.tv/([^/?&#]+)', url)
    if m:
        return m.group(1)
    return url.strip()


# ── Write ──────────────────────────────────────────────────────────────────

def log_usage(
    clip_slug: str,
    video_id: str,
    video_type: str,
    channel_name: str,
    creator: str = "",
    clip_url: str = "",
) -> None:
    """Record that a clip was used in a video."""
    now = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO clip_usage
                (clip_slug, clip_url, creator, channel_name, video_id, video_type, used_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (clip_slug, clip_url, creator, channel_name, video_id, video_type, now),
        )
        conn.commit()


def log_montage_clips(
    clips: list[dict],
    video_id: str,
    channel_name: str,
) -> None:
    """Bulk-log all clips selected for a montage.

    Each clip dict should have at minimum: 'url' or 'source_url', 'creator'.
    """
    for clip in clips:
        if clip.get("is_title_card"):
            continue
        url = clip.get("url") or clip.get("source_url", "")
        slug = extract_slug(url) if url else clip.get("clip_id", "")
        if not slug:
            continue
        log_usage(
            clip_slug=slug,
            video_id=video_id,
            video_type="montage",
            channel_name=channel_name,
            creator=clip.get("creator", ""),
            clip_url=url,
        )


# ── Read / Query ───────────────────────────────────────────────────────────

def get_usage(clip_slug: str) -> list[dict]:
    """Return all usage records for a clip slug."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT * FROM clip_usage WHERE clip_slug = ? ORDER BY used_at DESC",
            (clip_slug,),
        ).fetchall()
    return [dict(r) for r in rows]


def used_in_montage_recently(clip_slug: str, days: int = MONTAGE_COOLDOWN_DAYS) -> bool:
    """True if this clip appeared in any montage within the last `days` days."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM clip_usage
            WHERE clip_slug = ?
              AND video_type = 'montage'
              AND used_at >= ?
            LIMIT 1
            """,
            (clip_slug, cutoff),
        ).fetchone()
    return row is not None


def used_in_short_recently(clip_slug: str, days: int = SHORT_COOLDOWN_DAYS) -> bool:
    """True if this clip appeared in any short within the last `days` days."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT 1 FROM clip_usage
            WHERE clip_slug = ?
              AND video_type = 'short'
              AND used_at >= ?
            LIMIT 1
            """,
            (clip_slug, cutoff),
        ).fetchone()
    return row is not None


def get_usage_count(
    clip_slug: str,
    video_type: Optional[str] = None,
) -> int:
    """Return total number of times this clip has been used (optionally filtered by type)."""
    with _connect() as conn:
        if video_type:
            row = conn.execute(
                "SELECT COUNT(*) FROM clip_usage WHERE clip_slug = ? AND video_type = ?",
                (clip_slug, video_type),
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT COUNT(*) FROM clip_usage WHERE clip_slug = ?",
                (clip_slug,),
            ).fetchone()
    return row[0] if row else 0


def filter_montage_clips(clips: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split clips into (allowed, blocked) for montage use.

    Blocked = used in another montage within MONTAGE_COOLDOWN_DAYS.
    Allowed clips are also annotated with 'short_reuse' flag if recently
    used in a Short (for downstream deprioritization).
    """
    allowed, blocked = [], []
    for clip in clips:
        if clip.get("is_title_card"):
            allowed.append(clip)
            continue
        url = clip.get("url") or clip.get("source_url", "")
        slug = extract_slug(url) if url else clip.get("clip_id", "")
        if not slug:
            allowed.append(clip)
            continue
        if used_in_montage_recently(slug):
            print(f"[dedup] Blocking {slug[:40]} — used in montage recently")
            blocked.append(clip)
        else:
            if used_in_short_recently(slug):
                clip = dict(clip, short_reuse=True)
            allowed.append(clip)
    return allowed, blocked


# ── Stats / reporting ──────────────────────────────────────────────────────

def usage_report(channel_name: Optional[str] = None, limit: int = 20) -> None:
    """Print a usage summary — most-reused clips."""
    with _connect() as conn:
        if channel_name:
            rows = conn.execute(
                """
                SELECT clip_slug, creator, COUNT(*) AS uses,
                       GROUP_CONCAT(DISTINCT video_type) AS types,
                       MAX(used_at) AS last_used
                FROM clip_usage
                WHERE channel_name = ?
                GROUP BY clip_slug
                ORDER BY uses DESC
                LIMIT ?
                """,
                (channel_name, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT clip_slug, creator, COUNT(*) AS uses,
                       GROUP_CONCAT(DISTINCT video_type) AS types,
                       MAX(used_at) AS last_used
                FROM clip_usage
                GROUP BY clip_slug
                ORDER BY uses DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
    if not rows:
        print("[dedup] No usage records yet.")
        return
    print(f"\n{'Clip Slug':<45} {'Creator':<12} {'Uses':>4}  {'Types':<20} Last Used")
    print("-" * 100)
    for r in rows:
        slug = r["clip_slug"][:44]
        print(f"{slug:<45} {(r['creator'] or ''):<12} {r['uses']:>4}  {r['types']:<20} {r['last_used'][:19]}")
