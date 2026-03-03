"""Clip Empire Engine — command-line interface.

Run from repo root:

  # Process one channel (1 clip):
  python -m engine.cli --channel market_meltdowns

  # Process all channels (1 clip each):
  python -m engine.cli --all

  # Produce 3 clips for one channel:
  python -m engine.cli --channel crypto_confessions --count 3

  # Dry run (no downloads, no encodes, no queue writes):
  python -m engine.cli --all --dry-run

  # Skip captions (faster, no Whisper needed):
  python -m engine.cli --channel gym_moments --skip-caption

  # Use specific Whisper model:
  python -m engine.cli --all --model medium

  # Keep intermediate files (for debugging):
  python -m engine.cli --channel kitchen_chaos --keep-intermediate

  # List channels + today's budget status:
  python -m engine.cli --status
"""

from __future__ import annotations

import argparse
import sys

from accounts.channel_definitions import CHANNELS
from engine.scheduler.budget import BudgetManager
from engine.scheduler.runner import Runner
from engine.ops.status_exporter import export_status


def cmd_status() -> None:
    """Print budget status for all channels."""
    budget = BudgetManager()
    print(f"\n{'Channel':<22} {'Niche':<12} {'Target':<8} {'Used':<6} {'Slots'}")
    print("─" * 60)
    for name, cfg in sorted(CHANNELS.items()):
        target = budget.get_daily_target(name)
        used = budget.get_queued_today(name)
        slots = budget.slots_remaining(name)
        status = "✓" if slots > 0 else "FULL"
        niche = cfg.get("niche", "?")
        print(f"{name:<22} {niche:<12} {target:<8} {used:<6} {slots}  {status}")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Clip Empire Engine — automated content pipeline for 50-channel Shorts empire",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--channel", "-c", help="Process a specific channel")
    parser.add_argument("--all", "-a", action="store_true", help="Process all channels")
    parser.add_argument("--count", "-n", type=int, default=1, help="Clips per channel (default 1)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without downloading or encoding")
    parser.add_argument("--skip-caption", action="store_true", help="Skip Whisper transcription")
    parser.add_argument("--keep-intermediate", action="store_true", help="Keep cropped/overlaid files")
    parser.add_argument("--model", default="auto", help="Whisper model: tiny|base|small|medium|large|auto")
    parser.add_argument("--status", "-s", action="store_true", help="Show channel budget status")
    parser.add_argument("--export-status", help="Export ops dashboard JSON to path and exit")
    parser.add_argument("--db", default="data/clip_empire.db", help="Path to SQLite database")
    parser.add_argument("--trend-radar", action="store_true", help="Enable trend radar supplemental sources")
    parser.add_argument("--no-policy-filter", action="store_true", help="Disable safety/policy pre-filter")
    parser.add_argument("--enable-sora-lane", action="store_true", help="Enable optional Sora lane scaffold")

    args = parser.parse_args()

    if args.status:
        cmd_status()
        return

    if args.export_status:
        out = export_status(db_path=args.db, out_path=args.export_status)
        print(f"Exported status: {out}")
        return

    if not args.channel and not args.all:
        parser.print_help()
        sys.exit(1)

    runner = Runner(
        dry_run=args.dry_run,
        skip_caption=args.skip_caption,
        keep_intermediate=args.keep_intermediate,
        model_size=args.model,
        db_path=args.db,
        trend_radar_enabled=args.trend_radar,
        policy_filter_enabled=not args.no_policy_filter,
        sora_lane_enabled=args.enable_sora_lane,
    )

    if args.all:
        results = runner.run_all(count_per_channel=args.count)
        total = sum(len(v) for v in results.values())
        print(f"\n✅ Done: {total} jobs queued")
    else:
        jobs = runner.run_channel(args.channel, count=args.count)
        print(f"\n✅ Done: {len(jobs)} job(s) queued for {args.channel}")


if __name__ == "__main__":
    main()
