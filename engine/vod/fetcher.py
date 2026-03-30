"""VOD fetcher — downloads Twitch VOD audio, finds energy peaks, extracts video clips.

Strategy (audio-first to save bandwidth):
  1. List recent VODs for creator via yt-dlp --flat-playlist
  2. Download AUDIO ONLY of the VOD (small, fast)
  3. Run sliding-window RMS energy analysis → find top N peak moments
  4. Download VIDEO for only those moments using yt-dlp --download-sections
  5. Write segments to DB (engine/vod/db.py)

Output clips: raw_clips/vod_highlights/{creator}/{vod_id}_{start_s}_{end_s}.mp4
"""

from __future__ import annotations

import os
import subprocess
import struct
import tempfile
import wave
from datetime import datetime
from pathlib import Path
from typing import Optional

import yt_dlp

from engine.vod.db import (
    insert_segment,
    update_clip_path,
    vod_already_processed,
)

# ── ffmpeg/ffprobe paths (mirrors encode.py) ───────────────────────────────
_FFMPEG_BIN_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / (
    "Microsoft/WinGet/Packages/"
    "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/"
    "ffmpeg-8.1-full_build/bin"
)
FFMPEG_BIN  = str(_FFMPEG_BIN_DIR / "ffmpeg.exe")  if (_FFMPEG_BIN_DIR / "ffmpeg.exe").exists()  else "ffmpeg"
FFPROBE_BIN = str(_FFMPEG_BIN_DIR / "ffprobe.exe") if (_FFMPEG_BIN_DIR / "ffprobe.exe").exists() else "ffprobe"

# ── Config ─────────────────────────────────────────────────────────────────
CLIP_MIN_DUR   = 20     # seconds — minimum moment window
CLIP_MAX_DUR   = 60     # seconds — maximum moment window
CLIP_PAD       = 5      # seconds — pad before/after peak
WINDOW_S       = 2      # RMS window size in seconds
PEAK_MIN_RATIO = 1.5    # peak RMS must be this many times the mean to count
MERGE_GAP_S    = 15     # merge peaks closer than this many seconds


def _out_dir(creator: str) -> Path:
    d = Path("raw_clips") / "vod_highlights" / creator
    d.mkdir(parents=True, exist_ok=True)
    return d


# ── ffmpeg PATH helper ────────────────────────────────────────────────────

def _with_ffmpeg_in_path(func):
    """Temporarily add ffmpeg bin dir to PATH so yt-dlp partial downloads work."""
    import functools
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        ffmpeg_dir = str(_FFMPEG_BIN_DIR)
        original_path = os.environ.get("PATH", "")
        if ffmpeg_dir not in original_path:
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + original_path
        try:
            return func(*args, **kwargs)
        finally:
            os.environ["PATH"] = original_path
    return wrapper


# ── VOD listing ────────────────────────────────────────────────────────────

def list_recent_vods(creator: str, max_vods: int = 3) -> list[dict]:
    """Return metadata for the most recent VODs on a Twitch channel.

    Returns list of dicts: {id, url, title, duration_s}
    """
    url = f"https://www.twitch.tv/{creator}/videos"
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",
        "playlistend": max_vods,
    }
    vods = []
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            entries = (info or {}).get("entries", []) or []
            for entry in entries:
                if not entry:
                    continue
                vod_id  = str(entry.get("id", ""))
                # yt-dlp flat-playlist returns IDs like "v2735556296"; strip the 'v' prefix
                vod_id_clean = vod_id.lstrip("v")
                vod_url = f"https://www.twitch.tv/videos/{vod_id_clean}"
                title   = entry.get("title", "")
                dur     = float(entry.get("duration") or 0)
                vods.append({"id": vod_id_clean, "url": vod_url, "title": title, "duration_s": dur})
    except Exception as e:
        print(f"[vod.fetcher] list_recent_vods error: {e}")
    return vods


# ── Audio download + energy analysis ──────────────────────────────────────

@_with_ffmpeg_in_path
def _download_audio(vod_url: str, out_wav: str) -> bool:
    """Download audio-only track from a VOD and convert to mono 16kHz WAV for analysis."""
    out_template = out_wav.replace(".wav", ".%(ext)s")
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        # "audio_only" is Twitch's native audio-only stream (~48kbps AAC)
        # Falls back to bestaudio if not available (non-Twitch sources)
        # Twitch VOD audio-only stream (much smaller than video, ~900MB for 9h)
        "format": "Audio_Only/bestaudio/best",
        "outtmpl": out_template,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
            "preferredquality": "0",
        }],
        "postprocessor_args": {"ffmpeg": ["-ac", "1", "-ar", "16000"]},
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([vod_url])
        # yt-dlp outputs as .wav after postprocessing
        if not os.path.exists(out_wav):
            base = out_wav.replace(".wav", "")
            for ext in [".wav", ".mp3", ".m4a", ".opus", ".webm"]:
                if os.path.exists(base + ext):
                    # Convert to WAV via ffmpeg
                    subprocess.run(
                        [FFMPEG_BIN, "-y", "-i", base + ext,
                         "-ac", "1", "-ar", "16000", out_wav],
                        capture_output=True, timeout=120,
                    )
                    break
        return os.path.exists(out_wav)
    except Exception as e:
        print(f"[vod.fetcher] Audio download failed: {e}")
        return False


def _rms_peaks(wav_path: str, window_s: float = WINDOW_S) -> list[tuple[float, float]]:
    """Return list of (timestamp_s, rms_value) for each window in the WAV file."""
    try:
        with wave.open(wav_path, "rb") as wf:
            sample_rate = wf.getframerate()
            n_channels  = wf.getnchannels()
            sampwidth   = wf.getsampwidth()
            n_frames    = wf.getnframes()

            window_frames = int(window_s * sample_rate)
            results = []
            pos = 0

            while pos + window_frames <= n_frames:
                wf.setpos(pos)
                raw = wf.readframes(window_frames)
                if sampwidth == 2:
                    samples = struct.unpack(f"<{len(raw)//2}h", raw)
                elif sampwidth == 1:
                    samples = tuple(b - 128 for b in raw)
                else:
                    pos += window_frames
                    continue
                # Average channels
                if n_channels > 1:
                    samples = [sum(samples[i::n_channels]) / n_channels
                               for i in range(n_channels)]
                rms = (sum(s * s for s in samples) / len(samples)) ** 0.5
                t = pos / sample_rate
                results.append((t, rms))
                pos += window_frames

        return results
    except Exception as e:
        print(f"[vod.fetcher] RMS analysis failed: {e}")
        return []


def _find_peaks(rms_data: list[tuple[float, float]], top_n: int = 15) -> list[float]:
    """Return timestamps of top N energy peaks, merged if too close together."""
    if not rms_data:
        return []

    rms_values = [r for _, r in rms_data]
    mean_rms = sum(rms_values) / len(rms_values) if rms_values else 1.0

    # Filter to windows above threshold
    candidates = [
        (t, rms) for t, rms in rms_data
        if rms >= mean_rms * PEAK_MIN_RATIO
    ]
    # Sort by RMS descending
    candidates.sort(key=lambda x: x[1], reverse=True)

    # Greedy merge: take best peak, then skip any within MERGE_GAP_S
    peaks: list[float] = []
    used: set[float] = set()
    for t, rms in candidates:
        if any(abs(t - p) < MERGE_GAP_S for p in used):
            continue
        peaks.append(t)
        used.add(t)
        if len(peaks) >= top_n:
            break

    return sorted(peaks)


def _timestamp_to_hhmmss(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


# ── Video clip extraction ──────────────────────────────────────────────────

def _with_ffmpeg_in_path(func):
    """Decorator: temporarily add our ffmpeg bin dir to PATH so yt-dlp finds it."""
    import functools
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        ffmpeg_dir = str(_FFMPEG_BIN_DIR)
        original_path = os.environ.get("PATH", "")
        if ffmpeg_dir not in original_path:
            os.environ["PATH"] = ffmpeg_dir + os.pathsep + original_path
        try:
            return func(*args, **kwargs)
        finally:
            os.environ["PATH"] = original_path
    return wrapper


def _extract_clip(
    vod_url: str,
    start_s: float,
    end_s: float,
    out_path: str,
) -> bool:
    """Download a specific time range from a VOD as a video clip."""
    return _extract_clip_impl(vod_url, start_s, end_s, out_path)


@_with_ffmpeg_in_path
def _extract_clip_impl(
    vod_url: str,
    start_s: float,
    end_s: float,
    out_path: str,
) -> bool:
    start_str = _timestamp_to_hhmmss(start_s)
    end_str   = _timestamp_to_hhmmss(end_s)
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "bestvideo[height<=1080]+bestaudio/best[height<=1080]/best",
        "outtmpl": out_path,
        "merge_output_format": "mp4",
        "download_ranges": yt_dlp.utils.download_range_func(None, [(start_s, end_s)]),
        "force_keyframes_at_cuts": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([vod_url])
        return os.path.exists(out_path)
    except Exception as e:
        print(f"[vod.fetcher] Clip extract failed ({start_str}→{end_str}): {e}")
        return False


# ── Main entry point ───────────────────────────────────────────────────────

def ingest_vod_highlights(
    creator: str,
    channel_name: str,
    max_vods: int = 2,
    top_moments: int = 10,
    min_vod_duration_s: float = 600.0,
) -> list[str]:
    """Full pipeline: list VODs → find peaks → extract clips → write to DB.

    Returns list of segment_ids inserted.
    """
    print(f"[vod.fetcher] Fetching recent VODs for {creator}...")
    vods = list_recent_vods(creator, max_vods=max_vods)
    if not vods:
        print(f"[vod.fetcher] No VODs found for {creator}")
        return []

    segment_ids: list[str] = []
    out_base = _out_dir(creator)

    for vod in vods:
        vod_id  = vod["id"]
        vod_url = vod["url"]
        dur     = vod.get("duration_s", 0)

        if dur < min_vod_duration_s:
            print(f"[vod.fetcher] Skipping {vod_id} — too short ({dur:.0f}s)")
            continue

        if vod_already_processed(vod_id):
            print(f"[vod.fetcher] Skipping {vod_id} — already processed")
            continue

        print(f"[vod.fetcher] Processing VOD {vod_id}: '{vod.get('title', '')}' ({dur/3600:.1f}h)")

        with tempfile.TemporaryDirectory() as tmpdir:
            audio_path = os.path.join(tmpdir, f"{vod_id}.wav")

            print(f"[vod.fetcher]   Downloading audio track...")
            if not _download_audio(vod_url, audio_path):
                print(f"[vod.fetcher]   Audio download failed, skipping VOD")
                continue

            print(f"[vod.fetcher]   Analyzing energy peaks...")
            rms_data = _rms_peaks(audio_path)
            peak_times = _find_peaks(rms_data, top_n=top_moments)
            print(f"[vod.fetcher]   Found {len(peak_times)} peak moment(s)")

            if not peak_times:
                print(f"[vod.fetcher]   No peaks found, skipping VOD")
                continue

            # Compute mean RMS for energy normalization
            rms_values = [r for _, r in rms_data]
            mean_rms = sum(rms_values) / len(rms_values) if rms_values else 1.0
            rms_lookup = {t: r for t, r in rms_data}

            for i, peak_t in enumerate(peak_times):
                start_s = max(0.0, peak_t - CLIP_PAD)
                end_s   = peak_t + (CLIP_MAX_DUR - CLIP_PAD)

                # Clamp to VOD duration if known
                if dur > 0:
                    end_s = min(end_s, dur)

                # Normalize energy score (ratio of peak to mean)
                peak_rms = rms_lookup.get(peak_t, 0.0)
                energy_score = round(peak_rms / mean_rms if mean_rms > 0 else 0.0, 3)

                # Insert DB record first (before downloading clip)
                segment_id = insert_segment(
                    vod_id=vod_id,
                    vod_url=vod_url,
                    creator=creator,
                    channel_name=channel_name,
                    start_ts=start_s,
                    end_ts=end_s,
                    energy_score=energy_score,
                    clip_path="",
                )

                # Download video clip for this moment
                clip_filename = f"{vod_id}_{int(start_s)}_{int(end_s)}.mp4"
                clip_path = str(out_base / clip_filename)

                print(f"[vod.fetcher]   Extracting clip {i+1}/{len(peak_times)}: "
                      f"{_timestamp_to_hhmmss(start_s)}→{_timestamp_to_hhmmss(end_s)} "
                      f"(energy={energy_score:.2f})")

                if _extract_clip(vod_url, start_s, end_s, clip_path):
                    update_clip_path(segment_id, clip_path)
                    segment_ids.append(segment_id)
                    print(f"[vod.fetcher]     → {clip_filename}")
                else:
                    print(f"[vod.fetcher]     Extract failed, segment recorded without file")
                    segment_ids.append(segment_id)

    print(f"[vod.fetcher] Done. {len(segment_ids)} segment(s) added for {creator}")
    return segment_ids
