"""yt-dlp based ingester — handles YouTube, TikTok, Reddit video, Twitter/X.

Usage:
    ingester = YtDlpIngester(download_dir="raw_clips/market_meltdowns")
    clips = ingester.fetch(source_config, limit=5)
"""

from __future__ import annotations

import os
import json
import uuid
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional

from engine.config.sources import SOURCE_DEFAULTS
from engine.ingest.base import RawClip


class YtDlpIngester:
    """Downloads clips from any yt-dlp-supported platform."""

    # Extensions we'll accept as video files
    VIDEO_EXTENSIONS = {".mp4", ".mkv", ".webm", ".mov", ".m4v"}

    def __init__(self, download_dir: str = "raw_clips", cookies_dir: str = "cookies"):
        self.download_dir = Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.cookies_dir = Path(cookies_dir)

    def fetch(
        self,
        source_config: Dict[str, Any],
        limit: int = 5,
        channel_name: str = "",
    ) -> List[RawClip]:
        """Download up to `limit` clips from a source config entry.

        Returns a list of RawClip objects for successfully downloaded clips.
        """
        platform = source_config.get("platform", "youtube")
        url = source_config["url"]
        source_type = source_config.get("type", "channel")
        min_dur = source_config.get("min_dur_s", SOURCE_DEFAULTS["min_dur_s"])
        max_dur = source_config.get("max_dur_s", SOURCE_DEFAULTS["max_dur_s"])
        max_age = source_config.get("max_age_days", SOURCE_DEFAULTS["max_age_days"])

        # Build yt-dlp command
        out_dir = self.download_dir / channel_name
        out_dir.mkdir(parents=True, exist_ok=True)

        clips = []

        if source_type == "subreddit":
            clips = self._fetch_reddit(url, limit, min_dur, max_dur, out_dir, channel_name)
        else:
            clips = self._fetch_ytdlp(
                url=url,
                platform=platform,
                limit=limit,
                min_dur=min_dur,
                max_dur=max_dur,
                max_age_days=max_age,
                out_dir=out_dir,
                channel_name=channel_name,
            )

        return clips

    def _fetch_ytdlp(
        self,
        url: str,
        platform: str,
        limit: int,
        min_dur: float,
        max_dur: float,
        max_age_days: int,
        out_dir: Path,
        channel_name: str,
    ) -> List[RawClip]:
        """Run yt-dlp to download clips from YouTube, TikTok, or Twitter."""

        uid = str(uuid.uuid4())[:8]
        output_template = str(out_dir / f"%(id)s_%(title).50s.%(ext)s")

        # Date cutoff for max_age_days
        cutoff = (datetime.now() - timedelta(days=max_age_days)).strftime("%Y%m%d")

        cmd = [
            "yt-dlp",
            "--no-playlist" if "watch?v=" in url or "tiktok.com" in url else "--yes-playlist",
            "--match-filter", f"duration>={int(min_dur)} & duration<={int(max_dur)}",
            "--dateafter", cutoff,
            "--max-downloads", str(limit),
            "--format", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--merge-output-format", "mp4",
            "--write-info-json",
            "--no-write-comments",
            "--no-write-thumbnail",
            "--restrict-filenames",
            "--output", output_template,
            "--quiet",
            "--no-warnings",
        ]

        # Add cookies for platforms that need them
        cookies_file = self.cookies_dir / f"{platform}_cookies.txt"
        if cookies_file.exists():
            cmd += ["--cookies", str(cookies_file)]

        cmd.append(url)

        print(f"[ingest] Downloading from {platform}: {url[:80]}...")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 min max per source
            )
            if result.returncode not in (0, 1):  # 1 = "no more videos" which is OK
                print(f"[ingest] yt-dlp warning (rc={result.returncode}): {result.stderr[:200]}")
        except subprocess.TimeoutExpired:
            print(f"[ingest] Timeout downloading from {url[:80]}")
            return []
        except FileNotFoundError:
            print("[ingest] yt-dlp not found! Install with: pip install yt-dlp")
            return []

        # Collect downloaded files + their metadata
        return self._collect_downloads(out_dir, platform)

    def _fetch_reddit(
        self,
        url: str,
        limit: int,
        min_dur: float,
        max_dur: float,
        out_dir: Path,
        channel_name: str,
    ) -> List[RawClip]:
        """Download top video posts from a subreddit using yt-dlp.

        yt-dlp can handle Reddit video URLs directly.
        We use the JSON API to find video post URLs, then download them.
        """
        import urllib.request

        # Convert Reddit URL to JSON feed
        json_url = url.rstrip("/") + ".json?limit=25"
        headers = {"User-Agent": "clip-empire/1.0 (by /u/clipempirebot)"}

        try:
            req = urllib.request.Request(json_url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
        except Exception as e:
            print(f"[ingest] Reddit fetch error: {e}")
            return []

        video_urls = []
        for post in data.get("data", {}).get("children", []):
            post_data = post.get("data", {})
            if post_data.get("is_video") and not post_data.get("over_18", False):
                video_urls.append("https://www.reddit.com" + post_data.get("permalink", ""))
            if len(video_urls) >= limit * 2:
                break

        clips = []
        for video_url in video_urls[:limit * 2]:
            uid = str(uuid.uuid4())[:8]
            output_template = str(out_dir / f"%(id)s_%(title).50s.%(ext)s")
            cmd = [
                "yt-dlp",
                "--format", "bestvideo[ext=mp4]+bestaudio/best[ext=mp4]/best",
                "--merge-output-format", "mp4",
                "--write-info-json",
                "--restrict-filenames",
                "--output", output_template,
                "--quiet",
                "--no-warnings",
                video_url,
            ]
            try:
                subprocess.run(cmd, capture_output=True, timeout=60)
            except Exception:
                continue
            if len(clips) >= limit:
                break

        return self._collect_downloads(out_dir, "reddit")

    def _collect_downloads(self, out_dir: Path, platform: str) -> List[RawClip]:
        """Scan out_dir for newly downloaded mp4 + info.json pairs."""
        clips = []
        for info_file in out_dir.glob("*.info.json"):
            video_file = info_file.with_suffix("").with_suffix(".mp4")
            if not video_file.exists():
                # Try other extensions
                for ext in self.VIDEO_EXTENSIONS:
                    candidate = info_file.with_suffix("").with_suffix(ext)
                    if candidate.exists():
                        video_file = candidate
                        break
                else:
                    continue

            try:
                with open(info_file) as f:
                    info = json.load(f)
            except Exception:
                continue

            clip = RawClip(
                clip_id=str(uuid.uuid4()),
                source_url=info.get("webpage_url", ""),
                download_path=str(video_file),
                duration_s=float(info.get("duration", 0) or 0),
                title=info.get("title", "")[:200],
                platform=platform,
                creator=info.get("uploader", info.get("channel", ""))[:100],
                view_count=int(info.get("view_count", 0) or 0),
                upload_date=info.get("upload_date", ""),
                width=int(info.get("width", 0) or 0),
                height=int(info.get("height", 0) or 0),
                metadata={
                    "ext": info.get("ext", "mp4"),
                    "fps": info.get("fps", 30),
                    "like_count": info.get("like_count", 0),
                    "description": (info.get("description", "") or "")[:500],
                },
            )
            clips.append(clip)

        return clips
