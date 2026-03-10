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
POST_WINDOW_START_H = 7   # earliest possible post (7am local)
POST_WINDOW_END_H = 23    # latest possible post (11pm local)
MAX_JOBS_PER_SLOT = 3     # max uploads across all channels per 30-min slot

# ── Peak posting windows by niche ─────────────────────────────────────────────
# Format: list of (hour_start, hour_end) tuples in local time (America/Denver)
# Based on YouTube Shorts peak engagement research:
#   Gaming:  teen/young adult audience — late morning, afternoon, evening
#   Finance: working professionals — commute times + lunch + evening
#   Business: entrepreneurs — morning focus, evening
#   Tech/AI: broad — throughout day, peaks evening
#   Fitness: morning workout crowd + evening
#   Food:    lunch + evening scroll
#   True Crime: evening/late night
NICHE_PEAK_WINDOWS: dict[str, list[tuple[int, int]]] = {
    "Gaming":    [(9, 11), (15, 17), (19, 22)],   # morning, after school, prime time
    "Finance":   [(7, 9),  (12, 13), (17, 19), (20, 22)],  # commute, lunch, commute home, evening
    "Business":  [(6, 9),  (11, 13), (18, 21)],   # morning hustle, lunch, evening
    "Tech/AI":   [(8, 10), (13, 15), (19, 22)],
    "Fitness":   [(5, 8),  (11, 13), (17, 20)],   # morning workout, lunch, after work
    "Food":      [(11, 13), (17, 20), (21, 23)],   # lunch, dinner, late night
    "True Crime":[(19, 23)],                        # evening/night scroll
    "Experimental": [(9, 11), (13, 15), (19, 22)],
}

# Niche → channel mapping (for scheduler)
CHANNEL_NICHE_MAP: dict[str, str] = {
    "arc_highlightz":   "Gaming",
    "fomo_highlights":  "Gaming",
    "viral_recaps":     "Gaming",
    "market_meltdowns": "Finance",
    "crypto_confessions": "Finance",
    "rich_or_ruined":   "Finance",
    "startup_graveyard": "Business",
    "self_made_clips":  "Business",
    "ai_did_what":      "Tech/AI",
    "gym_moments":      "Fitness",
    "kitchen_chaos":    "Food",
    "cases_unsolved":   "True Crime",
    "unfiltered_clips": "Experimental",
}


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


def _peak_slots_for_niche(niche: str, date_local) -> list[datetime]:
    """Return sorted list of candidate datetime slots for a niche on a given date.

    Candidates are on the hour and half-hour within each peak window.
    """
    import pytz
    tz = pytz.timezone("America/Denver")
    windows = NICHE_PEAK_WINDOWS.get(niche, NICHE_PEAK_WINDOWS["Experimental"])
    slots = []
    for (h_start, h_end) in windows:
        h = h_start
        while h < h_end:
            for minute in (0, 30):
                dt = date_local.replace(hour=h, minute=minute, second=0, microsecond=0)
                slots.append(dt)
            h += 1
    return sorted(set(slots))


def _next_schedule_time(channel_name: str, db_path: str = DATABASE_PATH) -> datetime:
    """Smart scheduler: spread daily_target across peak engagement windows.

    Logic:
    1. Get daily_target for channel (default 5).
    2. Get already-scheduled slots for today on this channel.
    3. Divide peak windows into target evenly-spaced slots.
    4. Return the next unoccupied peak slot, with >90min gap from last post.
    5. Falls back to flat distribution if no peak windows defined.
    6. Global load balancer: max MAX_JOBS_PER_SLOT per 30-min slot across all channels.
    """
    import pytz
    tz = pytz.timezone("America/Denver")
    now_local = datetime.now(tz)
    today_str = now_local.date().isoformat()

    niche = CHANNEL_NICHE_MAP.get(channel_name, "Experimental")

    # Get daily target for this channel
    daily_target = 3  # conservative default — better distribution per video
    try:
        conn = sqlite3.connect(db_path)
        row = conn.execute(
            "SELECT daily_target FROM channels WHERE channel_name=?", (channel_name,)
        ).fetchone()
        if row and row[0]:
            daily_target = int(row[0])
        conn.close()
    except Exception:
        pass

    # Get already-queued slots for this channel today
    existing_slots: list[datetime] = []
    try:
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            """SELECT schedule_at FROM publish_jobs
               WHERE channel_name=? AND status IN ('queued','running','succeeded')
               AND date(schedule_at)=?
               ORDER BY schedule_at""",
            (channel_name, today_str),
        ).fetchall()
        for r in rows:
            try:
                dt = datetime.fromisoformat(r[0])
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                existing_slots.append(dt.astimezone(tz))
            except Exception:
                pass
        conn.close()
    except Exception:
        pass

    # Build candidate slots from peak windows for today
    today_midnight = now_local.replace(hour=0, minute=0, second=0, microsecond=0)
    peak_slots = _peak_slots_for_niche(niche, today_midnight)

    # Filter: must be in future (with 5-min buffer) and within allowed window
    window_start = today_midnight.replace(hour=POST_WINDOW_START_H)
    window_end   = today_midnight.replace(hour=POST_WINDOW_END_H)
    min_time = now_local + timedelta(minutes=5)

    peak_slots = [s for s in peak_slots if window_start <= s <= window_end]

    # If daily_target > number of peak slots, fill gaps between peaks evenly
    if daily_target > len(peak_slots):
        # Fall back to evenly distributed across full window
        window_minutes = (POST_WINDOW_END_H - POST_WINDOW_START_H) * 60
        interval_minutes = max(30, window_minutes // (daily_target + 1))
        peak_slots = []
        t = window_start
        while t <= window_end and len(peak_slots) < daily_target * 2:
            peak_slots.append(t)
            t = t + timedelta(minutes=interval_minutes)

    # Determine minimum gap between consecutive posts (evenly spread target across day)
    window_minutes = (POST_WINDOW_END_H - POST_WINDOW_START_H) * 60
    min_gap_minutes = max(60, window_minutes // max(daily_target, 1) - 15)

    # Last posted time (for gap enforcement)
    last_slot = existing_slots[-1] if existing_slots else None

    # Find next available peak slot
    for candidate in peak_slots:
        # Must be in the future
        if candidate < min_time:
            continue
        # Must not be already occupied by this channel
        occupied = any(
            abs((candidate - s).total_seconds()) < 1800  # 30-min collision window
            for s in existing_slots
        )
        if occupied:
            continue
        # Must respect minimum gap from last post
        if last_slot and (candidate - last_slot).total_seconds() < min_gap_minutes * 60:
            continue
        # Global slot load balancer
        if _slot_load(candidate, db_path=db_path) >= MAX_JOBS_PER_SLOT:
            continue
        return candidate

    # All peak slots taken — find next available slot after last existing
    if last_slot:
        next_time = last_slot + timedelta(minutes=min_gap_minutes)
    else:
        next_time = min_time.replace(second=0, microsecond=0)
        next_time = next_time.replace(minute=30 if next_time.minute < 30 else 0)
        if next_time.minute == 0:
            next_time += timedelta(hours=1)

    # Clamp to window; push to tomorrow if past end
    if next_time.hour > POST_WINDOW_END_H or next_time > window_end:
        tomorrow = (now_local + timedelta(days=1)).replace(
            hour=POST_WINDOW_START_H, minute=0, second=0, microsecond=0
        )
        peak_slots_tomorrow = _peak_slots_for_niche(niche, tomorrow.replace(hour=0, minute=0))
        peak_slots_tomorrow = [s for s in peak_slots_tomorrow if s >= tomorrow]
        if peak_slots_tomorrow:
            return peak_slots_tomorrow[0]
        return tomorrow

    # Load balancer on fallback
    while _slot_load(next_time, db_path=db_path) >= MAX_JOBS_PER_SLOT:
        next_time += timedelta(minutes=30)
        if next_time.hour > POST_WINDOW_END_H:
            next_time = (now_local + timedelta(days=1)).replace(
                hour=POST_WINDOW_START_H, minute=0, second=0, microsecond=0
            )
            break

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

        # Hard daily cap: refuse to queue if today's target is already met
        try:
            import pytz
            tz = pytz.timezone("America/Denver")
            today_str = datetime.now(tz).date().isoformat()
            conn = sqlite3.connect(self.db_path)
            row = conn.execute(
                "SELECT daily_target FROM channels WHERE channel_name=?", (channel_name,)
            ).fetchone()
            cap = int(row[0]) if (row and row[0]) else 3
            today_count = conn.execute(
                """SELECT COUNT(1) FROM publish_jobs
                   WHERE channel_name=? AND status IN ('queued','running','succeeded')
                   AND date(schedule_at)=?""",
                (channel_name, today_str),
            ).fetchone()[0]
            conn.close()
            if today_count >= cap:
                print(f"[queue] SKIP {channel_name}: daily cap {cap} already reached ({today_count} queued today)")
                return ""
        except Exception as e:
            print(f"[queue] daily cap check error: {e}")

        niche = CHANNELS.get(channel_name, {}).get("niche", "Gaming")

        # 1. Try LLM title generation (GPT-4o-mini curiosity-bait)
        llm_title = None
        if creator and not title:
            try:
                from engine.config.smart_title import generate_llm_title, clean_title
                raw_llm = generate_llm_title(
                    creator=creator,
                    clip_title=clip_title or "",
                    channel_name=channel_name,
                    niche=niche,
                )
                if raw_llm:
                    llm_title = clean_title(raw_llm)
            except Exception as e:
                print(f"[queue] LLM title skipped: {e}")

        # 2. Always build series entry (for hashtag + counter tracking)
        series_hashtag = None
        if creator and not title:
            from engine.config.series import classify_theme, next_episode
            theme = classify_theme(clip_title or "", niche)
            ep_num = next_episode(channel_name, creator, theme, self.db_path)
            # e.g. "#ShroudBestPlays4" — no space, YouTube hashtag format
            series_hashtag = f"#{creator.capitalize().replace(' ', '')}{theme.replace(' ', '')}{ep_num}"

        # 3. Title: LLM curiosity-bait, else series title, else A/B template
        if creator and not title:
            if llm_title:
                caption = llm_title
                auto_hook = caption.split(":")[0].strip()[:80]
                ab_label = "L"   # L = LLM
            else:
                # No LLM — use series title as primary
                series_name = f"{creator.capitalize()} {theme} #{ep_num}"
                caption = series_name
                auto_hook = caption.split("#")[0].strip()[:80]
                ab_label = "S"   # S = Series
        else:
            auto_title, auto_hook, ab_label = choose_variant(channel_name, creator=creator)
            caption = title or auto_title

        # 4. Apply profanity filter
        try:
            from engine.utils.censor import censor_text
            caption = censor_text(caption)
        except Exception:
            pass

        # 5. Build hashtag list: base niche tags + series hashtag
        tags = list(hashtags or get_hashtags(channel_name))
        if series_hashtag and series_hashtag not in tags:
            tags.append(series_hashtag)
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
