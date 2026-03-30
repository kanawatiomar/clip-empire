"""Montage runner: fetch → score → assemble → queue for upload.

Builds a long-form 16:9 YouTube compilation from fresh top Twitch clips,
grouped by creator with title cards between sections.
"""

from __future__ import annotations

import uuid
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from engine.montage.fetcher import fetch_top_clips
from engine.montage.scorer import score_clips
from engine.montage.assembler import build_montage
from engine.dedup.tracker import filter_montage_clips, log_montage_clips, extract_slug
from publisher.db_queue import add_publish_job, get_db_connection

DATABASE_PATH = "data/clip_empire.db"

# Creator config for arc_highlightz
_CREATOR_CONFIG = [
    {"name": "tfue",    "display": "Tfue",    "fetch": 20, "top_n": 5, "range_days": 30},
    {"name": "cloakzy", "display": "Cloakzy", "fetch": 20, "top_n": 5, "range_days": 30},
    {"name": "ninja",   "display": "Ninja",   "fetch": 15, "top_n": 4, "range_days": 30},
    {"name": "taxi2g",  "display": "Taxi2g",  "fetch": 15, "top_n": 4, "range_days": 30},
]

CHANNEL_CONFIGS: dict[str, list[dict]] = {
    "arc_highlightz": _CREATOR_CONFIG,
}


def _generate_title(creators: list[str], month_str: Optional[str] = None) -> str:
    if not month_str:
        month_str = datetime.now().strftime("%B %Y")
    if len(creators) == 1:
        return f"{creators[0]} Best Clips - {month_str}"
    if len(creators) == 2:
        return f"{creators[0]} & {creators[1]} Best Moments - {month_str}"
    return f"Best Gaming Moments - {month_str}"


def _generate_description(creators: list[str], month_str: str) -> str:
    creator_line = ", ".join(creators)
    return (
        f"The best {creator_line} moments from {month_str}.\n"
        f"Subscribe for daily gaming highlights!\n\n"
        f"#Gaming #{' #'.join(creators)} #FortNite #Highlights #TwitchClips"
    )


def _generate_hashtags(creators: list[str]) -> list[str]:
    tags = ["Gaming", "Highlights", "FortNite", "TwitchClips", "GamingMoments"]
    tags.extend(creators)
    return tags


def _queue_montage_upload(
    channel: str,
    video_path: str,
    title: str,
    description: str,
    hashtags: list[str],
    schedule_delay_s: int = 3600,
) -> str:
    """Insert a long-form upload job into the publish queue."""
    # Create a stub platform_variant so the FK constraint is satisfied
    conn = get_db_connection()
    variant_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO platform_variants
           (variant_id, clip_id, platform, render_path, caption_text, hashtags, first_frame_hook, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (variant_id, "montage_" + variant_id[:8], "youtube",
         video_path, description, str(hashtags), None, now_iso),
    )
    conn.commit()
    conn.close()

    schedule_at = datetime.fromtimestamp(time.time() + schedule_delay_s, tz=timezone.utc)

    job_id = add_publish_job(
        variant_id=variant_id,
        platform="youtube",
        channel_name=channel,
        publisher_account=channel,
        schedule_at=schedule_at,
        caption_text=title + "\n\n" + description,
        hashtags=hashtags,
        render_path=video_path,
    )
    print(f"[runner] Queued upload job {job_id} scheduled for {schedule_at.isoformat()}")
    return job_id


def run_montage(
    channel: str = "arc_highlightz",
    range_days: int = 30,
    dry_run: bool = False,
    min_clips: int = 3,
    min_duration_s: float = 120.0,
    all_time: bool = False,
) -> Optional[str]:
    """Fetch, score, assemble and queue a long-form montage.

    Returns path to the output MP4, or None if not enough clips.
    """
    creator_cfg = CHANNEL_CONFIGS.get(channel)
    if not creator_cfg:
        print(f"[runner] No creator config for channel: {channel}")
        return None

    clips_by_creator: dict[str, list[dict]] = {}
    all_creators_display: list[str] = []

    # All-time mode: higher thresholds, more clips fetched
    min_views_override = 10000 if all_time else None

    for cfg in creator_cfg:
        creator = cfg["name"]
        display = cfg["display"]
        count = cfg["fetch"] if not all_time else 30
        top_n = cfg["top_n"] if not all_time else 6

        clips = fetch_top_clips(creator, count=count, range_days=range_days,
                                min_views=min_views_override)

        if not clips:
            print(f"[runner] No clips fetched for {display}, skipping")
            continue

        if not dry_run:
            clips = score_clips(clips)
        else:
            # In dry_run, just sort by view_count
            clips.sort(key=lambda c: c.get("view_count", 0), reverse=True)
            for c in clips:
                c["energy_score"] = 0.0

        # Dedup: filter out clips used in a montage recently
        allowed, blocked = filter_montage_clips(clips)
        if blocked:
            print(f"[runner] {display}: {len(blocked)} clip(s) blocked by dedup (used in montage recently)")
        # Deprioritize clips that appeared in a Short recently (sort to end)
        allowed.sort(key=lambda c: (c.get("short_reuse", False), -c.get("energy_score", 0), -c.get("view_count", 0)))

        selected = allowed[:top_n]
        if selected:
            clips_by_creator[display] = selected
            all_creators_display.append(display)
            total_dur = sum(c.get("duration", 0) for c in selected)
            print(f"[runner] {display}: {len(selected)} clips, ~{total_dur:.0f}s total")
            for c in selected:
                score = c.get("energy_score", 0)
                views = c.get("view_count", 0)
                print(f"  [{views:,}v | energy={score:.2f}] {c.get('title', c.get('clip_id', '?'))}")

    if not clips_by_creator:
        print("[runner] No clips found for any creator.")
        return None

    # Flatten and check totals
    all_clips = [c for clips in clips_by_creator.values() for c in clips]
    total_duration = sum(c.get("duration", 0) for c in all_clips)

    if len(all_clips) < min_clips:
        print(f"[runner] Only {len(all_clips)} clips — need at least {min_clips}. Aborting.")
        return None

    if total_duration < min_duration_s:
        print(f"[runner] Total duration {total_duration:.0f}s < {min_duration_s}s minimum. Aborting.")
        return None

    month_str = datetime.now().strftime("%B %Y")
    year_str = datetime.now().strftime("%Y")
    if all_time:
        creators_str = " & ".join(all_creators_display[:2]) if len(all_creators_display) > 1 else all_creators_display[0]
        title = f"{creators_str} Greatest Clips of All Time"
        description = _generate_description(all_creators_display, f"All Time • {year_str}")
    else:
        title = _generate_title(all_creators_display, month_str)
        description = _generate_description(all_creators_display, month_str)
    hashtags = _generate_hashtags(all_creators_display)

    print(f"\n[runner] Title: {title}")
    print(f"[runner] Clips: {len(all_clips)} | Duration: ~{total_duration:.0f}s ({total_duration/60:.1f} min)")

    if dry_run:
        print("[runner] DRY RUN — skipping encode and queue.")
        return None

    # Build output path
    date_str = datetime.now().strftime("%Y%m%d")
    out_dir = Path("rendered_clips") / channel
    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = "alltime" if all_time else "montage"
    output_path = str(out_dir / f"{prefix}_{date_str}.mp4")

    # Build montage (assembler handles creator sections with title cards)
    # Flatten into a single ordered list with title card markers
    ordered_clips: list[dict] = []
    for display, clips in clips_by_creator.items():
        ordered_clips.append({"is_title_card": True, "creator_display": display})
        ordered_clips.extend(clips)

    try:
        output_path = build_montage(
            channel=channel,
            clips=ordered_clips,
            output_path=output_path,
            title=title,
        )
    except Exception as e:
        print(f"[runner] Montage build failed: {e}")
        return None

    # Log clip usage for dedup tracking
    video_id = f"{prefix}_{datetime.now().strftime('%Y%m%d')}"
    log_montage_clips(ordered_clips, video_id=video_id, channel_name=channel)
    print(f"[runner] Logged {len(all_clips)} clip(s) to dedup tracker (video_id={video_id})")

    # Queue for upload
    _queue_montage_upload(channel, output_path, title, description, hashtags)

    print(f"\n[runner] Done! Montage at: {output_path}")
    return output_path
