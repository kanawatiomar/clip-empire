"""
Longform video segment extractor.

Downloads full creator videos (10-60 min), finds the highest-energy 30-60s window
via audio RMS analysis, and extracts it as a short clip for the render pipeline.

Copyright approach:
  ✅ SAFE: Twitch clips (fan-clipped, different platform)
  ✅ SAFE: Longform extraction (transformative highlight, ~1% of video duration)
  ❌ RISKY: Reposting an existing YouTube Short verbatim
  ❌ RISKY: Downloading from YouTube channel pages (pulls their own Shorts)

Use source type "longform" for YouTube channels where you want to extract
your own highlight from their full videos, not repost their Shorts.
"""

from __future__ import annotations

import os
import struct
import subprocess
import tempfile
import uuid
from pathlib import Path
from typing import Optional, Tuple

# ── ffmpeg path (mirrors crop.py / encode.py) ─────────────────────────────────
_FFMPEG_DIR = r"C:\Users\kanaw\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin"
if _FFMPEG_DIR not in os.environ.get("PATH", ""):
    os.environ["PATH"] = _FFMPEG_DIR + os.pathsep + os.environ.get("PATH", "")

FFMPEG_BIN = os.path.join(_FFMPEG_DIR, "ffmpeg.exe")
FFPROBE_BIN = os.path.join(_FFMPEG_DIR, "ffprobe.exe")

# ── Constants ─────────────────────────────────────────────────────────────────
PCM_SAMPLE_RATE = 8000      # 8 kHz mono — fast enough for energy analysis
BYTES_PER_SAMPLE = 2        # 16-bit signed
INTRO_SKIP_S = 15.0         # skip first N seconds (intros/title cards)
OUTRO_SKIP_S = 20.0         # skip last N seconds (outros/end screens)
MAX_LONGFORM_DUR_S = 3600   # skip videos longer than 1h (probably not useful)
MIN_LONGFORM_DUR_S = 120    # skip videos shorter than 2min (already short)


def get_video_duration(video_path: str) -> float:
    """Return video duration in seconds using ffprobe."""
    result = subprocess.run(
        [FFPROBE_BIN, "-v", "quiet", "-print_format", "json",
         "-show_format", video_path],
        capture_output=True, text=True, timeout=30,
    )
    import json
    data = json.loads(result.stdout)
    return float(data.get("format", {}).get("duration", 0))


def extract_pcm_audio(video_path: str, sample_rate: int = PCM_SAMPLE_RATE) -> bytes:
    """Extract mono PCM audio from video as raw bytes (16-bit signed little-endian)."""
    tmp = tempfile.mktemp(suffix=".pcm")
    try:
        subprocess.run(
            [FFMPEG_BIN, "-i", video_path,
             "-ac", "1",           # mono
             "-ar", str(sample_rate),
             "-f", "s16le",        # 16-bit PCM
             "-y", tmp],
            capture_output=True, timeout=120, check=True,
        )
        with open(tmp, "rb") as f:
            return f.read()
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def compute_rms_per_second(pcm_data: bytes, sample_rate: int = PCM_SAMPLE_RATE) -> list:
    """Compute RMS energy per second from raw 16-bit mono PCM data."""
    samples_per_sec = sample_rate
    chunk_bytes = samples_per_sec * BYTES_PER_SAMPLE
    rms_values = []

    for i in range(0, len(pcm_data) - chunk_bytes + 1, chunk_bytes):
        chunk = pcm_data[i : i + chunk_bytes]
        if len(chunk) < chunk_bytes:
            break
        samples = struct.unpack(f"<{samples_per_sec}h", chunk)
        rms = (sum(s * s for s in samples) / samples_per_sec) ** 0.5
        rms_values.append(rms)

    return rms_values


def find_best_window(
    rms_per_sec: list,
    target_dur: float,
    skip_start: float = INTRO_SKIP_S,
    skip_end_abs: float = 0.0,  # absolute second to stop searching
) -> Tuple[float, float]:
    """
    Find the window of `target_dur` seconds with highest average RMS energy.
    Returns (start_sec, end_sec).
    """
    window = int(target_dur)
    total = len(rms_per_sec)
    start_idx = int(skip_start)
    end_idx = int(skip_end_abs) if skip_end_abs > 0 else total - window

    end_idx = max(start_idx + window, min(end_idx, total - window))

    best_score = -1.0
    best_start = start_idx

    for i in range(start_idx, end_idx):
        score = sum(rms_per_sec[i : i + window]) / window
        if score > best_score:
            best_score = score
            best_start = i

    return float(best_start), float(best_start + window)


def extract_segment(
    video_path: str,
    start_s: float,
    end_s: float,
    output_path: str,
) -> str:
    """Cut [start_s, end_s] from video_path and re-encode to output_path.

    Re-encode (not stream copy) to:
    - Avoid keyframe-boundary corruption
    - Ensure clean YouTube-compatible output
    """
    duration = end_s - start_s
    subprocess.run(
        [FFMPEG_BIN,
         "-ss", str(start_s),
         "-i", video_path,
         "-t", str(duration),
         "-c:v", "libx264", "-preset", "fast", "-crf", "23",
         "-c:a", "aac", "-b:a", "128k", "-ar", "48000",
         "-movflags", "+faststart",
         "-y", output_path],
        capture_output=True, timeout=300, check=True,
    )
    return output_path


def extract_best_segment(
    video_path: str,
    output_dir: str,
    target_dur: float = 40.0,
    clip_id: Optional[str] = None,
) -> Optional[str]:
    """
    Full pipeline: analyse audio → find best window → extract segment.
    Returns path to extracted segment file, or None on failure.
    """
    clip_id = clip_id or str(uuid.uuid4())[:8]
    output_path = str(Path(output_dir) / f"{clip_id}_segment.mp4")

    try:
        duration = get_video_duration(video_path)
        if duration < MIN_LONGFORM_DUR_S:
            print(f"[longform] Skipping — too short ({duration:.0f}s)")
            return None
        if duration > MAX_LONGFORM_DUR_S:
            print(f"[longform] Skipping — too long ({duration:.0f}s)")
            return None

        skip_end = duration - OUTRO_SKIP_S

        print(f"[longform] Analysing audio ({duration:.0f}s video)...")
        pcm = extract_pcm_audio(video_path)
        rms = compute_rms_per_second(pcm)

        start_s, end_s = find_best_window(
            rms, target_dur,
            skip_start=INTRO_SKIP_S,
            skip_end_abs=skip_end,
        )
        print(f"[longform] Best segment: {start_s:.1f}s → {end_s:.1f}s "
              f"(peak energy window)")

        extract_segment(video_path, start_s, end_s, output_path)
        print(f"[longform] Extracted: {output_path}")
        return output_path

    except subprocess.CalledProcessError as e:
        print(f"[longform] ffmpeg error: {e.stderr[:200] if e.stderr else e}")
        return None
    except Exception as e:
        print(f"[longform] Error: {e}")
        return None
