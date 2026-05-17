"""Real content ingestion — replaces the dummy placeholder.

Pulls clips from configured sources using yt-dlp, deduplicates,
and returns a list of RawClip objects ready for processing.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.config.sources import CHANNEL_SOURCES
from engine.ingest.ytdlp import YtDlpIngester
from engine.ingest.dedup import DedupTracker
from engine.ingest.base import RawClip


def ingest_for_channel(
    channel_name: str,
    limit: int = 5,
    download_dir: str = "raw_clips",
) -> List[RawClip]:
    """Download clips for a channel from its configured sources.

    Sources are processed in priority order (1 = highest).
    Clips already seen globally are skipped.

    Args:
        channel_name: Key from CHANNEL_SOURCES (e.g. 'market_meltdowns')
        limit:        Max clips to return across all sources
        download_dir: Base dir for raw downloads (subdir per channel created)

    Returns:
        List of RawClip objects ready for processing.
    """
    sources = CHANNEL_SOURCES.get(channel_name)
    if not sources:
        print(f"[ingest] No sources configured for channel: {channel_name}")
        return []

    # Sort by priority (1 = highest priority)
    sources_sorted = sorted(sources, key=lambda s: s.get("priority", 99))

    channel_dl_dir = str(Path(download_dir) / channel_name)
    ingester = YtDlpIngester(download_dir=channel_dl_dir)
    dedup = DedupTracker()

    collected: List[RawClip] = []
    remaining = limit

    for source in sources_sorted:
        if remaining <= 0:
            break

        platform = source.get("platform", "youtube")
        url = source.get("url", "")
        print(f"[ingest:{channel_name}] Fetching from {platform}: {url[:70]}...")

        try:
            raw_clips = ingester.fetch(source, limit=remaining * 2, channel_name=channel_name)
        except Exception as e:
            print(f"[ingest:{channel_name}] ERROR fetching {url[:50]}: {e}")
            continue

        # Filter already-seen clips globally (no cross-channel duplication)
        fresh = dedup.filter_unused(raw_clips, channel_name=channel_name, global_dedup=True)

        for clip in fresh:
            if remaining <= 0:
                break
            dedup.mark_used(clip, channel_name=channel_name)
            collected.append(clip)
            remaining -= 1
            print(f"[ingest:{channel_name}]   + {clip.title[:60]} ({clip.duration_s:.0f}s)")

    print(f"[ingest:{channel_name}] Done — {len(collected)} new clips ready")
    return collected
