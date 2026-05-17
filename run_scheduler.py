"""Clip Empire — Upload Scheduler

Manages staggered uploads across all 10 accounts.
Rules:
  - Max 3 uploads per account per day
  - Min 2 hours between uploads on the same account
  - Processes channels in round-robin order

Usage:
    python run_scheduler.py              # Upload next batch
    python run_scheduler.py --dry-run    # Show what would happen
    python run_scheduler.py --channel market_meltdowns   # One channel only
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from engine.config.sources import CHANNEL_SOURCES
from publisher.queue import DATABASE_PATH


SCHEDULE_FILE = Path("data/schedule_state.json")

MAX_PER_DAY = 3
MIN_GAP_HOURS = 2


def _load_schedule() -> dict:
    if SCHEDULE_FILE.exists():
        try:
            return json.loads(SCHEDULE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_schedule(state: dict) -> None:
    SCHEDULE_FILE.parent.mkdir(parents=True, exist_ok=True)
    SCHEDULE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def _today_start_utc() -> datetime:
    n = _now_utc()
    return n.replace(hour=0, minute=0, second=0, microsecond=0)


def _count_pending_jobs(channel_name: str) -> int:
    """Count queued jobs waiting for this channel."""
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        cur = conn.execute(
            "SELECT COUNT(*) FROM publish_jobs WHERE channel_name = ? AND status = 'queued'",
            (channel_name,)
        )
        count = cur.fetchone()[0]
        conn.close()
        return count
    except Exception as e:
        print(f"[scheduler] DB error checking queue for {channel_name}: {e}")
        return 0


def _channel_eligible(channel_name: str, state: dict, now: datetime) -> tuple[bool, str]:
    """Check if a channel can upload now. Returns (eligible, reason)."""
    ch_state = state.get(channel_name, {})

    # Check daily cap
    uploads_today = 0
    today_start = _today_start_utc()
    for ts in ch_state.get("uploads_today_ts", []):
        if datetime.fromisoformat(ts) >= today_start:
            uploads_today += 1

    if uploads_today >= MAX_PER_DAY:
        return False, f"daily cap reached ({uploads_today}/{MAX_PER_DAY})"

    # Check minimum gap
    last_upload_str = ch_state.get("last_upload_at")
    if last_upload_str:
        last_upload = datetime.fromisoformat(last_upload_str)
        if last_upload.tzinfo is None:
            last_upload = last_upload.replace(tzinfo=timezone.utc)
        elapsed_h = (now - last_upload).total_seconds() / 3600
        if elapsed_h < MIN_GAP_HOURS:
            wait_min = int((MIN_GAP_HOURS - elapsed_h) * 60)
            return False, f"gap not met (need {wait_min}m more)"

    # Check pending jobs
    pending = _count_pending_jobs(channel_name)
    if pending == 0:
        return False, "no queued jobs"

    return True, f"{pending} jobs pending"


def _record_upload(channel_name: str, state: dict, now: datetime) -> None:
    ch = state.setdefault(channel_name, {"uploads_today_ts": []})
    ch["last_upload_at"] = now.isoformat()
    # Prune old timestamps (keep only today)
    today_start = _today_start_utc()
    ch["uploads_today_ts"] = [
        ts for ts in ch.get("uploads_today_ts", [])
        if datetime.fromisoformat(ts) >= today_start
    ]
    ch["uploads_today_ts"].append(now.isoformat())


def run_scheduler(
    channels: list[str],
    dry_run: bool = False,
    headless: bool = False,
) -> dict:
    """Run one scheduling pass across the given channels."""
    from publisher.youtube_worker import run_once, YouTubeWorkerConfig

    state = _load_schedule()
    now = _now_utc()

    summary = {"eligible": [], "skipped": [], "uploaded": 0, "errors": 0}

    print(f"\n{'='*60}")
    print(f"  SCHEDULER  {'(DRY RUN) ' if dry_run else ''}{now.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*60}")

    for channel_name in channels:
        eligible, reason = _channel_eligible(channel_name, state, now)

        if not eligible:
            print(f"  SKIP  {channel_name:<28} — {reason}")
            summary["skipped"].append(channel_name)
            continue

        print(f"  READY {channel_name:<28} — {reason}")
        summary["eligible"].append(channel_name)

        if dry_run:
            continue

        # Trigger upload
        print(f"  → Uploading {channel_name}...")
        try:
            cfg = YouTubeWorkerConfig(headless=headless)
            rc = run_once(cfg=cfg, channel_name=channel_name)
            if rc == 0:
                _record_upload(channel_name, state, now)
                summary["uploaded"] += 1
                print(f"  ✓ Upload succeeded for {channel_name}")
            else:
                print(f"  ✗ Upload returned code {rc} for {channel_name}")
                summary["errors"] += 1
        except Exception as e:
            print(f"  ✗ Upload error for {channel_name}: {e}")
            summary["errors"] += 1

        # Small pause between accounts (avoid rate limits)
        if not dry_run:
            time.sleep(5)

    if not dry_run:
        _save_schedule(state)

    print(f"\n  Result: {len(summary['eligible'])} eligible, "
          f"{summary['uploaded']} uploaded, "
          f"{summary['errors']} errors, "
          f"{len(summary['skipped'])} skipped")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Clip Empire upload scheduler")
    parser.add_argument("--dry-run", action="store_true", help="Show what would upload, don't actually upload")
    parser.add_argument("--channel", help="Restrict to one channel")
    parser.add_argument("--headless", action="store_true", help="Run browser headless")
    args = parser.parse_args()

    channels = [args.channel] if args.channel else list(CHANNEL_SOURCES.keys())

    if args.channel and args.channel not in CHANNEL_SOURCES:
        print(f"ERROR: Unknown channel '{args.channel}'. Available: {', '.join(CHANNEL_SOURCES)}")
        sys.exit(1)

    run_scheduler(channels, dry_run=args.dry_run, headless=args.headless)


if __name__ == "__main__":
    main()
