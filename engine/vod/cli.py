"""VOD highlights ingestion CLI.

Usage:
    # Ingest recent VODs for all arc_highlightz creators:
    python -m engine.vod.cli --channel arc_highlightz

    # Ingest for a specific creator:
    python -m engine.vod.cli --creator tfue --channel arc_highlightz

    # Check how many ready segments exist:
    python -m engine.vod.cli --status

    # Limit to 1 VOD per creator (faster for testing):
    python -m engine.vod.cli --channel arc_highlightz --max-vods 1
"""

from __future__ import annotations

import argparse
import sys

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from engine.vod.fetcher import ingest_vod_highlights
from engine.vod.db import get_ready_segments, segment_count

# Creator configs per channel (mirrors montage runner)
_CHANNEL_CREATORS: dict[str, list[dict]] = {
    "arc_highlightz": [
        {"name": "tfue",     "display": "Tfue"},
        {"name": "cloakzy",  "display": "Cloakzy"},
        {"name": "ninja",    "display": "Ninja"},
        {"name": "taxi2g",   "display": "Taxi2g"},
    ],
}


def cmd_ingest(channel: str, creator: str | None, max_vods: int, top_moments: int) -> None:
    creators = _CHANNEL_CREATORS.get(channel, [])
    if not creators:
        print(f"[vod.cli] No creator config for channel: {channel}")
        return

    if creator:
        creators = [c for c in creators if c["name"] == creator]
        if not creators:
            print(f"[vod.cli] Creator '{creator}' not found in {channel} config")
            return

    total = 0
    for cfg in creators:
        ids = ingest_vod_highlights(
            creator=cfg["name"],
            channel_name=channel,
            max_vods=max_vods,
            top_moments=top_moments,
        )
        total += len(ids)
        ready = segment_count(cfg["name"], channel, "ready")
        print(f"[vod.cli] {cfg['display']}: +{len(ids)} new segments → {ready} ready in pool\n")

    print(f"[vod.cli] Total new segments: {total}")


def cmd_status(channel: str | None) -> None:
    channels = [channel] if channel else list(_CHANNEL_CREATORS.keys())
    for ch in channels:
        print(f"\n=== {ch} ===")
        for cfg in _CHANNEL_CREATORS.get(ch, []):
            ready     = segment_count(cfg["name"], ch, "ready")
            used_s    = segment_count(cfg["name"], ch, "used_short")
            used_m    = segment_count(cfg["name"], ch, "used_montage")
            exhausted = segment_count(cfg["name"], ch, "exhausted")
            print(f"  {cfg['display']:<12} ready={ready:>3}  used_short={used_s:>3}  "
                  f"used_montage={used_m:>3}  exhausted={exhausted:>3}")


def main() -> None:
    p = argparse.ArgumentParser(description="VOD highlights ingestion")
    p.add_argument("--channel",     default="arc_highlightz", help="Channel name")
    p.add_argument("--creator",     default=None, help="Single creator (optional)")
    p.add_argument("--max-vods",    type=int, default=2, help="Max VODs per creator")
    p.add_argument("--top-moments", type=int, default=10, help="Top N moments per VOD")
    p.add_argument("--status",      action="store_true", help="Show segment pool status")
    args = p.parse_args()

    if args.status:
        cmd_status(args.channel)
    else:
        cmd_ingest(args.channel, args.creator, args.max_vods, args.top_moments)


if __name__ == "__main__":
    main()
