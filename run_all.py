"""Clip Empire — Master Orchestrator

One-shot runner: ingest → process → schedule → upload.

Usage:
    python run_all.py --channel market_meltdowns
    python run_all.py --all
    python run_all.py --all --limit 2 --dry-run
    python run_all.py --all --no-captions --limit 1
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from engine.config.sources import CHANNEL_SOURCES
from run_pipeline import run_channel
from run_scheduler import run_scheduler


def main():
    parser = argparse.ArgumentParser(description="Clip Empire full pipeline orchestrator")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--channel", help="Single channel (e.g. market_meltdowns)")
    group.add_argument("--all", action="store_true", help="Run all 10 channels")
    parser.add_argument("--limit", type=int, default=2, help="Max clips per channel to ingest (default: 2)")
    parser.add_argument("--no-captions", action="store_true", help="Skip Whisper captioning (faster)")
    parser.add_argument("--dry-run", action="store_true", help="Ingest+process but don't actually upload")
    parser.add_argument("--headless", action="store_true", help="Run YouTube Studio headless")
    args = parser.parse_args()

    channels = list(CHANNEL_SOURCES.keys()) if args.all else [args.channel]

    if args.channel and args.channel not in CHANNEL_SOURCES:
        print(f"ERROR: Unknown channel '{args.channel}'. Available: {', '.join(CHANNEL_SOURCES)}")
        sys.exit(1)

    started_at = datetime.utcnow()
    print(f"\n{'#'*60}")
    print(f"  CLIP EMPIRE — Full Run  [{started_at.strftime('%Y-%m-%d %H:%M UTC')}]")
    print(f"  Channels: {', '.join(channels)}")
    print(f"  Limit: {args.limit}/channel  |  Captions: {not args.no_captions}  |  Dry-run: {args.dry_run}")
    print(f"{'#'*60}\n")

    # ── Phase 1: Ingest + Process + Queue ─────────────────────────────────
    print("PHASE 1: Ingest & Process")
    totals = {"ingested": 0, "processed": 0, "queued": 0, "errors": 0}

    for ch in channels:
        result = run_channel(
            ch,
            limit=args.limit,
            use_captions=not args.no_captions,
        )
        for k in totals:
            totals[k] += result.get(k, 0)

    print(f"\nPhase 1 complete: "
          f"{totals['ingested']} ingested | "
          f"{totals['processed']} processed | "
          f"{totals['queued']} queued | "
          f"{totals['errors']} errors")

    if totals["queued"] == 0:
        print("\nNothing queued — skipping upload phase.")
    else:
        # ── Phase 2: Schedule + Upload ─────────────────────────────────────
        print(f"\nPHASE 2: Schedule & Upload{' (DRY RUN)' if args.dry_run else ''}")
        sched = run_scheduler(channels, dry_run=args.dry_run, headless=args.headless)

    # ── Summary ────────────────────────────────────────────────────────────
    elapsed = (datetime.utcnow() - started_at).total_seconds()
    print(f"\n{'#'*60}")
    print(f"  DONE in {elapsed:.0f}s")
    print(f"  Ingested:  {totals['ingested']}")
    print(f"  Processed: {totals['processed']}")
    print(f"  Queued:    {totals['queued']}")
    if totals["queued"] > 0 and not args.dry_run:
        uploaded = sched.get("uploaded", 0)
        print(f"  Uploaded:  {uploaded}")
    print(f"{'#'*60}\n")


if __name__ == "__main__":
    main()
