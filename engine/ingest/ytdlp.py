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


def _extract_broadcaster(url: str, info: dict) -> str:
    """For Twitch clips, extract the broadcaster (streamer) name from the URL,
    not the clip uploader (the viewer who created the clip).
    URL format: https://www.twitch.tv/{broadcaster}/clip/{clip_id}
    Falls back to yt-dlp channel/uploader fields for non-Twitch sources.
    """
    import re
    if "twitch.tv" in url:
        m = re.search(r"twitch\.tv/([^/]+)/clip/", url)
        if m:
            return m.group(1)
    # Non-Twitch: use channel name (more reliable than uploader for YT)
    return info.get("channel", info.get("uploader", ""))


def _find_ytdlp() -> str:
    """Return the yt-dlp executable path, searching common locations."""
    import shutil
    if shutil.which("yt-dlp"):
        return "yt-dlp"
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / "Python311" / "Scripts" / "yt-dlp.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Python" / "pythoncore-3.14-64" / "Scripts" / "yt-dlp.exe",
        Path(os.environ.get("APPDATA", "")) / "Python" / "Scripts" / "yt-dlp.exe",
        Path("C:/Users/kanaw/AppData/Local/Programs/Python/Python311/Scripts/yt-dlp.exe"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return "yt-dlp"  # fallback, will raise FileNotFoundError if missing


YTDLP_BIN = _find_ytdlp()


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
        elif source_type == "longform":
            clips = self._fetch_longform(
                url=url,
                platform=platform,
                limit=limit,
                target_dur=source_config.get("target_dur_s", 40.0),
                max_age_days=max_age,
                out_dir=out_dir,
                channel_name=channel_name,
            )
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
                min_views=source_config.get("min_views", 0),
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
        min_views: int = 0,
    ) -> List[RawClip]:
        """Run yt-dlp to download clips from YouTube, TikTok, or Twitter."""

        uid = str(uuid.uuid4())[:8]
        output_template = str(out_dir / f"%(id)s_%(title).50s.%(ext)s")

        # Date cutoff for max_age_days
        cutoff = (datetime.now() - timedelta(days=max_age_days)).strftime("%Y%m%d")

        # Build match filter — duration range + optional view count floor
        match_filter = f"duration>={int(min_dur)} & duration<={int(max_dur)}"
        if min_views > 0:
            match_filter += f" & view_count>={min_views}"

        cmd = [
            YTDLP_BIN,
            "--no-playlist" if "watch?v=" in url or "tiktok.com" in url else "--yes-playlist",
            "--match-filter", match_filter,
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
                YTDLP_BIN,
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

    def _fetch_longform(
        self,
        url: str,
        platform: str,
        limit: int,
        target_dur: float,
        max_age_days: int,
        out_dir: Path,
        channel_name: str,
    ) -> List[RawClip]:
        """
        Download full long-form videos and extract the highest-energy segment.

        Steps:
        1. List videos from channel (no download) to get URLs + metadata
        2. For each video (up to limit), download full video
        3. Run audio RMS analysis to find best 30-60s window
        4. Extract that segment, delete the full video
        5. Return RawClip for the segment

        Copyright note: extracting a 40s highlight from a 20-min video is
        transformative; far safer than reposting an existing Short verbatim.
        """
        from engine.ingest.longform import extract_best_segment
        from datetime import datetime, timedelta

        cutoff = (datetime.now() - timedelta(days=max_age_days)).strftime("%Y%m%d")

        # Step 1: List videos (flat-playlist, no download) — get URLs only
        list_cmd = [
            YTDLP_BIN,
            "--flat-playlist",
            "--print", "%(id)s\t%(title)s\t%(duration)s\t%(upload_date)s",
            "--dateafter", cutoff,
            "--max-downloads", str(limit * 3),  # fetch extras in case some fail
            "--quiet", "--no-warnings",
            url,
        ]
        try:
            result = subprocess.run(
                list_cmd, capture_output=True, timeout=60,
                encoding="utf-8", errors="replace",
            )
            stdout = result.stdout or ""
            lines = [l.strip() for l in stdout.splitlines() if "\t" in l]
        except Exception as e:
            print(f"[longform] Failed to list videos: {e}")
            return []

        if not lines:
            print(f"[longform] No videos found at {url[:60]}")
            return []

        clips = []
        segment_dir = out_dir / "segments"
        segment_dir.mkdir(parents=True, exist_ok=True)

        for line in lines[:limit * 2]:
            if len(clips) >= limit:
                break

            parts = line.split("\t")
            vid_id = parts[0] if parts else ""
            title = parts[1] if len(parts) > 1 else ""
            duration_str = parts[2] if len(parts) > 2 else "0"
            upload_date = parts[3] if len(parts) > 3 else ""

            if not vid_id or vid_id.startswith("NA"):
                continue

            # Skip if duration looks too short or is unknown
            try:
                dur = float(duration_str)
                if dur < 120:   # skip anything under 2 min
                    continue
                if dur > 3600:  # skip anything over 1h
                    continue
            except (ValueError, TypeError):
                pass

            video_url = f"https://www.youtube.com/watch?v={vid_id}"
            full_video_path = out_dir / f"{vid_id}_full.mp4"

            # Step 2: Download full video
            print(f"[longform] Downloading full video: {title[:50]}...")
            dl_cmd = [
                YTDLP_BIN,
                "--format", "bestvideo[height<=1080][ext=mp4]+bestaudio[ext=m4a]/best[height<=1080][ext=mp4]/best",
                "--merge-output-format", "mp4",
                "--no-playlist",
                "--output", str(full_video_path),
                "--quiet", "--no-warnings",
                video_url,
            ]
            try:
                subprocess.run(
                    dl_cmd, capture_output=True, timeout=600, check=True,
                    encoding="utf-8", errors="replace",
                )
            except Exception as e:
                print(f"[longform] Download failed: {e}")
                continue

            if not full_video_path.exists():
                continue

            # Step 3+4: Extract best segment, delete full video
            clip_id = str(uuid.uuid4())[:8]
            segment_path = extract_best_segment(
                video_path=str(full_video_path),
                output_dir=str(segment_dir),
                target_dur=target_dur,
                clip_id=clip_id,
            )

            # Always delete the full video to save disk space
            try:
                full_video_path.unlink()
            except Exception:
                pass

            if not segment_path or not Path(segment_path).exists():
                continue

            # Step 5: Build RawClip for the segment
            clip = RawClip(
                clip_id=str(uuid.uuid4()),
                source_url=video_url,
                download_path=segment_path,
                duration_s=target_dur,
                title=title[:200],
                platform=platform,
                creator="",
                view_count=0,
                upload_date=upload_date,
                width=0,
                height=0,
                metadata={
                    "longform_source": video_url,
                    "segment_extracted": True,
                },
            )
            clips.append(clip)
            print(f"[longform] Segment ready: {title[:40]} → {clip_id}")

        return clips

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
                creator=_extract_broadcaster(info.get("webpage_url", ""), info)[:100],
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
