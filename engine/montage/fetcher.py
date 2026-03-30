"""Fetch top Twitch clips for a creator using yt-dlp.

Downloads in original 16:9 quality (no cropping) for use in long-form montage.
"""

from __future__ import annotations

import os
import subprocess
import json
import uuid
from pathlib import Path
from typing import Optional

import yt_dlp

# ── ffmpeg path (mirrors encode.py) ─────────────────────────────────────────
_FFMPEG_BIN_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / (
    "Microsoft/WinGet/Packages/"
    "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/"
    "ffmpeg-8.1-full_build/bin"
)
FFMPEG_BIN = str(_FFMPEG_BIN_DIR / "ffmpeg.exe") if (_FFMPEG_BIN_DIR / "ffmpeg.exe").exists() else "ffmpeg"
FFPROBE_BIN = str(_FFMPEG_BIN_DIR / "ffprobe.exe") if (_FFMPEG_BIN_DIR / "ffprobe.exe").exists() else "ffprobe"

_STAGING_DIR = Path("raw_clips/montage_staging")

# Range param map
_RANGE_MAP = {7: "7d", 14: "14d", 30: "30d", 90: "90d"}


def _twitch_clips_url(creator: str, range_days: int = 30) -> str:
    if range_days >= 365:
        range_str = "all"
    else:
        range_str = _RANGE_MAP.get(range_days, "30d")
    return f"https://www.twitch.tv/{creator}/clips?filter=clips&range={range_str}"


def _probe_duration(path: str) -> float:
    """Return video duration in seconds via ffprobe."""
    try:
        result = subprocess.run(
            [FFPROBE_BIN, "-v", "error",
             "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, timeout=15,
        )
        return float(result.stdout.strip())
    except Exception:
        return 0.0


def fetch_top_clips(
    creator: str,
    count: int = 20,
    range_days: int = 30,
    output_dir: Optional[str] = None,
    min_dur_s: float = 15.0,
    max_dur_s: float = 90.0,
    min_views: Optional[int] = None,
) -> list[dict]:
    """Download top `count` Twitch clips for `creator` in original 16:9.

    Returns list of dicts with keys:
        path, creator, title, view_count, duration, clip_id
    """
    out_dir = Path(output_dir) if output_dir else _STAGING_DIR / creator
    out_dir.mkdir(parents=True, exist_ok=True)

    url = _twitch_clips_url(creator, range_days)
    print(f"[fetcher] Fetching top {count} clips for {creator} ({range_days}d) ...")

    downloaded: list[dict] = []

    def _progress_hook(d: dict) -> None:
        pass  # silent

    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": str(out_dir / f"{creator}_%(id)s.%(ext)s"),
        "playlist_items": f"1-{count}",
        "ignoreerrors": True,
        "quiet": False,
        "no_warnings": True,
        "noprogress": False,
        "ffmpeg_location": str(_FFMPEG_BIN_DIR),
        "merge_output_format": "mp4",
        # Force Twitch clips in landscape (not mobile portrait)
        "format_sort": ["res:1080", "ext:mp4:m4a"],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
        except Exception as e:
            print(f"[fetcher] yt-dlp error for {creator}: {e}")
            return []

    if not info:
        return []

    entries = info.get("entries") or []
    for entry in entries:
        if not entry:
            continue
        # Reconstruct the expected file path
        clip_id = entry.get("id", str(uuid.uuid4())[:8])
        expected = out_dir / f"{creator}_{clip_id}.mp4"

        # yt-dlp may have used a different extension
        if not expected.exists():
            # Try to find any file matching the clip_id
            matches = list(out_dir.glob(f"{creator}_{clip_id}.*"))
            if not matches:
                continue
            expected = matches[0]

        dur = _probe_duration(str(expected))
        if dur < min_dur_s or dur > max_dur_s:
            print(f"[fetcher] Skipping {clip_id} (dur={dur:.1f}s out of range)")
            continue

        views = entry.get("view_count") or 0
        if min_views and views < min_views:
            print(f"[fetcher] Skipping {clip_id} (views={views} < {min_views})")
            continue

        downloaded.append({
            "path": str(expected),
            "creator": creator,
            "title": entry.get("title", clip_id),
            "view_count": entry.get("view_count") or 0,
            "duration": dur,
            "clip_id": clip_id,
        })

    print(f"[fetcher] Got {len(downloaded)} usable clips for {creator}")
    return downloaded
