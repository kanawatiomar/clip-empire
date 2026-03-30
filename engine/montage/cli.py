"""CLI entry point for the montage pipeline.

Usage:
    python -m engine.montage.cli --channel arc_highlightz
    python -m engine.montage.cli --channel arc_highlightz --dry-run
    python -m engine.montage.cli --channel arc_highlightz --range-days 7
    python -m engine.montage.cli --channel arc_highlightz --all-time
"""

from __future__ import annotations

import argparse
import sys

from engine.montage.runner import run_montage


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build a long-form montage for a Clip Empire channel"
    )
    parser.add_argument(
        "--channel", default="arc_highlightz",
        help="Channel name (default: arc_highlightz)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Fetch clip metadata only — no download, no encode, no queue"
    )
    parser.add_argument(
        "--range-days", type=int, default=30,
        help="How many days back to search for clips (default: 30)"
    )
    parser.add_argument(
        "--all-time", action="store_true",
        help="All-time greatest mode: fetch top clips of all time (high min_views)"
    )
    args = parser.parse_args()

    range_days = 3650 if args.all_time else args.range_days

    result = run_montage(
        channel=args.channel,
        range_days=range_days,
        dry_run=args.dry_run,
        all_time=args.all_time,
    )

    if result:
        print(f"\nSuccess: {result}")
        sys.exit(0)
    elif args.dry_run:
        print("\nDry run complete.")
        sys.exit(0)
    else:
        print("\nMontage failed or not enough clips.")
        sys.exit(1)


if __name__ == "__main__":
    main()
