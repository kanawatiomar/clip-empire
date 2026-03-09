"""Writes processed clips into the publish_jobs queue.

Creates the necessary platform_variants record (so foreign key is satisfied)
then calls add_publish_job() from publisher/queue.py.

Scheduling logic:
  - If channel has no jobs today yet: schedule for next available slot (spread
    across the day in equal intervals).
  - Subsequent jobs for the same day: space them ~2-3 hours apart.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, List

from publisher.queue import add_publish_job
from engine.config.templates import get_title, get_hashtags
from engine.transform.ab import choose_variant
from engine.config.series import build_series_title
from accounts.channel_definitions import CHANNELS


DATABASE_PATH = "data/clip_empire.db"

# Spread posts across these hours (Denver time → converted to UTC for storage)
POST_WINDOW_START_H = 8   # 8am local
POST_WINDOW_END_H = 22    # 10pm local
MAX_JOBS_PER_SLOT = 4


def _ensure_channel_in_db(channel_name: str, db_path: str = DATABASE_PATH) -> None:
    """Insert the channel row if it doesn't exist (for fresh DBs)."""
    ch = CHANNELS.get(channel_name, {})
    if not ch:
        return
    conn = sqlite3.connect(db_path)
    conn.execute("""
        INSERT OR IGNORE INTO channels
            (channel_name, category, status, daily_target, made_for_kids, created_at, updated_at)
        VALUES (?, ?, 'active', 5, ?, ?, ?)
    """, (
        channel_name,
        ch.get("niche", "Unknown"),
        1 if ch.get("made_for_kids") else 0,
        datetime.utcnow().isoformat(),
        datetime.utcnow().isoformat(),
    ))
    conn.commit()
    conn.close()


def _create_dummy_variant(
    channel_name: str,
    render_path: str,
    caption_text: str,
    hashtags: List[str],
    db_path: str = DATABASE_PATH,
) -> str:
    """Create a minimal platform_variants record for the foreign key requirement.

    In the full pipeline, platform_variants would point to a clip_asset → segment → source.
    For now, we create a standalone variant with a dummy clip_id.
    """
    conn = sqlite3.connect(db_path)
    variant_id = str(uuid.uuid4())
    import json
    conn.execute("""
        INSERT INTO platform_variants
            (variant_id, clip_id, platform, render_path, caption_text, hashtags, created_at)
        VALUES (?, ?, 'youtube', ?, ?, ?, ?)
    """, (
        variant_id,
        # clip_id FK is nullable in practice since there's no STRICT mode
        "engine_auto_" + str(uuid.uuid4())[:8],
        render_path,
        caption_text,
        json.dumps(hashtags),
        datetime.utcnow().isoformat(),
    ))
    conn.commit()
    conn.close()
    return variant_id


def _slot_load(slot_start_local: datetime, db_path: str = DATABASE_PATH) -> int:
    conn = sqlite3.connect(db_path)
    slot_end = slot_start_local + timedelta(minutes=30)
    cur = conn.execute(
        """
        SELECT COUNT(1) FROM publish_jobs
        WHERE status IN ('queued', 'running', 'succeeded')
          AND schedule_at >= ? AND schedule_at < ?
        """,
        (slot_start_local.isoformat(), slot_end.isoformat()),
    )
    count = int(cur.fetchone()[0] or 0)
    conn.close()
    return count


def _next_schedule_time(channel_name: str, db_path: str = DATABASE_PATH) -> datetime:
    """Calculate the next available upload slot for a channel today.

    Spreads posts evenly across POST_WINDOW_START_H → POST_WINDOW_END_H.
    """
    import pytz
    tz = pytz.timezone("America/Denver")
    now_local = datetime.now(tz)

    # Find last queued job time for today
    today = now_local.date().isoformat()
    conn = sqlite3.connect(db_path)
    cur = conn.execute(
        """SELECT schedule_at FROM publish_jobs
           WHERE channel_name = ?
             AND status IN ('queued', 'running', 'succeeded')
             AND date(created_at) = ?
           ORDER BY schedule_at DESC LIMIT 1""",
        (channel_name, today),
    )
    row = cur.fetchone()
    conn.close()

    if row and row[0]:
        try:
            last_dt = datetime.fromisoformat(row[0])
            if last_dt.tzinfo is None:
                last_dt = last_dt.replace(tzinfo=timezone.utc)
            last_local = last_dt.astimezone(tz)
            # Schedule 2.5 hours after last job
            next_time = last_local + timedelta(hours=2, minutes=30)
        except Exception:
            next_time = now_local + timedelta(minutes=5)
    else:
        # First job today — schedule at next 30-min boundary after now
        next_time = now_local.replace(second=0, microsecond=0)
        if next_time.minute >= 30:
            next_time = next_time.replace(minute=0) + timedelta(hours=1)
        else:
            next_time = next_time.replace(minute=30)

    # Clamp to window
    window_start = now_local.replace(hour=POST_WINDOW_START_H, minute=0, second=0, microsecond=0)
    window_end = now_local.replace(hour=POST_WINDOW_END_H, minute=0, second=0, microsecond=0)

    if next_time < window_start:
        next_time = window_start
    if next_time > window_end:
        # Push to tomorrow's window start
        next_time = (now_local + timedelta(days=1)).replace(
            hour=POST_WINDOW_START_H, minute=0, second=0, microsecond=0
        )

    # Load balancer: avoid overpacking a single half-hour slot globally.
    while _slot_load(next_time, db_path=db_path) >= MAX_JOBS_PER_SLOT:
        next_time = next_time + timedelta(minutes=30)
        if next_time.hour > POST_WINDOW_END_H:
            next_time = (next_time + timedelta(days=1)).replace(
                hour=POST_WINDOW_START_H, minute=0, second=0, microsecond=0
            )

    return next_time


class QueueWriter:
    """Write a processed clip into the publish_jobs queue."""

    def __init__(self, db_path: str = DATABASE_PATH):
        self.db_path = db_path

    def enqueue(
        self,
        channel_name: str,
        render_path: str,
        title: Optional[str] = None,
        hashtags: Optional[List[str]] = None,
        schedule_at: Optional[datetime] = None,
        creator: Optional[str] = None,
        clip_title: Optional[str] = None,
    ) -> str:
        """Add a clip to the publish queue.

        Args:
            channel_name: Target channel.
            render_path:  Path to the final MP4.
            title:        Caption/title for YouTube (auto-generated if None).
            hashtags:     Hashtag list (auto-generated if None).
            schedule_at:  When to post (auto-scheduled if None).
            creator:      Streamer/broadcaster name (used in series titles).
            clip_title:   Raw clip title (used for series theme classification).

        Returns:
            job_id of the created publish job.
        """
        _ensure_channel_in_db(channel_name, self.db_path)

        niche = CHANNELS.get(channel_name, {}).get("niche", "Gaming")

        # Build series title if we know the creator, otherwise fall back to A/B
        if creator and not title:
            caption = build_series_title(
                channel_name=channel_name,
                creator=creator,
                clip_title=clip_title or "",
                niche=niche,
                db_path=self.db_path,
            )
            # Derive hook from series title prefix
            auto_hook = caption.split("#")[0].strip()[:80]
            ab_label = "S"  # S = Series
        else:
            auto_title, auto_hook, ab_label = choose_variant(channel_name, creator=creator)
            caption = title or auto_title
        tags = hashtags or get_hashtags(channel_name)
        sched = schedule_at or _next_schedule_time(channel_name, self.db_path)

        variant_id = _create_dummy_variant(
            channel_name=channel_name,
            render_path=render_path,
            caption_text=caption,
            hashtags=tags,
            db_path=self.db_path,
        )

        job_id = add_publish_job(
            variant_id=variant_id,
            platform="youtube",
            channel_name=channel_name,
            publisher_account=f"youtube:{channel_name}",
            schedule_at=sched,
            caption_text=caption,
            hashtags=tags,
            render_path=render_path,
            first_frame_hook=f"{auto_hook} [{ab_label}]",
        )

        print(f"[queue] Enqueued {channel_name} → {job_id} (schedule: {sched.strftime('%Y-%m-%d %H:%M')}, A/B={ab_label})")
        return job_id
