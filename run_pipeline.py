"""Clip Empire — Content Pipeline Runner

Ingests clips from configured sources, processes them into publish-ready
Shorts MP4s, and adds them to the upload queue.

Usage:
    python run_pipeline.py --channel market_meltdowns --limit 3
    python run_pipeline.py --all --limit 2
    python run_pipeline.py --all --no-captions --limit 1
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from engine.config.sources import CHANNEL_SOURCES
from pipeline.ingest import ingest_for_channel
from pipeline.process import process_clip
from publisher.queue import add_publish_job
from accounts.channel_definitions import CHANNELS


STATE_FILE = Path("data/pipeline_state.json")


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_state(state: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _make_caption(channel_name: str, title: str, creator: str) -> str:
    """Generate a YouTube caption/description for a clip."""
    ch = CHANNELS.get(channel_name, {})
    tags = " ".join(f"#{t}" for t in ch.get("tags", [])[:5])
    return f"{title}\n\nCredit: @{creator}\n\n{tags}"


def run_channel(
    channel_name: str,
    limit: int = 3,
    use_captions: bool = True,
) -> dict:
    """Run the full pipeline for one channel. Returns summary dict."""
    print(f"\n{'='*60}")
    print(f"  PIPELINE: {channel_name}  (limit={limit})")
    print(f"{'='*60}")

    state = _load_state()
    summary = {"channel": channel_name, "ingested": 0, "processed": 0, "queued": 0, "errors": 0}

    # ── Ingest ────────────────────────────────────────────────────────────
    clips = ingest_for_channel(channel_name, limit=limit)
    summary["ingested"] = len(clips)

    if not clips:
        print(f"[pipeline:{channel_name}] No new clips — nothing to do")
        state.setdefault(channel_name, {})["last_run"] = datetime.utcnow().isoformat()
        _save_state(state)
        return summary

    # ── Process + Queue ───────────────────────────────────────────────────
    for clip in clips:
        print(f"\n[pipeline:{channel_name}] ── Clip: {clip.title[:55]}")
        result = process_clip(clip, channel_name=channel_name, use_captions=use_captions)

        if result is None:
            print(f"[pipeline:{channel_name}] ✗ Process failed — skipping")
            summary["errors"] += 1
            continue

        summary["processed"] += 1

        # Schedule upload 30 min from now (scheduler will adjust)
        schedule_at = datetime.now(tz=timezone.utc) + timedelta(minutes=30)
        caption = _make_caption(channel_name, result["title"], result["creator"])
        ch_info = CHANNELS.get(channel_name, {})
        hashtags = ch_info.get("tags", [])[:10]

        try:
            variant_id = str(uuid.uuid4())
            job_id = add_publish_job(
                variant_id=variant_id,
                platform="youtube",
                channel_name=channel_name,
                publisher_account=f"youtube:{channel_name}",
                schedule_at=schedule_at,
                caption_text=caption,
                hashtags=hashtags,
                render_path=result["render_path"],
            )
            summary["queued"] += 1
            print(f"[pipeline:{channel_name}] ✓ Queued job {job_id[:8]}…")
        except Exception as e:
            print(f"[pipeline:{channel_name}] ✗ Queue error: {e}")
            summary["errors"] += 1

    # ── Save state ────────────────────────────────────────────────────────
    state.setdefault(channel_name, {}).update({
        "last_run": datetime.utcnow().isoformat(),
        "last_ingested": summary["ingested"],
        "last_queued": summary["queued"],
    })
    _save_state(state)

    print(f"\n[pipeline:{channel_name}] Summary: "
          f"{summary['ingested']} ingested, "
          f"{summary['processed']} processed, "
          f"{summary['queued']} queued, "
          f"{summary['errors']} errors")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Clip Empire content pipeline")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--channel", help="Single channel name (e.g. market_meltdowns)")
    group.add_argument("--all", action="store_true", help="Run all 10 channels")
    parser.add_argument("--limit", type=int, default=3, help="Max clips per channel (default: 3)")
    parser.add_argument("--no-captions", action="store_true", help="Skip Whisper captioning")
    args = parser.parse_args()

    use_captions = not args.no_captions
    channels = list(CHANNEL_SOURCES.keys()) if args.all else [args.channel]

    if args.channel and args.channel not in CHANNEL_SOURCES:
        print(f"ERROR: Unknown channel '{args.channel}'. Available: {', '.join(CHANNEL_SOURCES)}")
        sys.exit(1)

    totals = {"ingested": 0, "processed": 0, "queued": 0, "errors": 0}
    for ch in channels:
        result = run_channel(ch, limit=args.limit, use_captions=use_captions)
        for k in totals:
            totals[k] += result.get(k, 0)

    if args.all:
        print(f"\n{'='*60}")
        print(f"  TOTAL: {totals['ingested']} ingested | "
              f"{totals['processed']} processed | "
              f"{totals['queued']} queued | "
              f"{totals['errors']} errors")
        print(f"{'='*60}")


if __name__ == "__main__":
    main()
