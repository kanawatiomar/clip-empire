"""Thumbnail generator for YouTube Shorts.

Extracts the brightest/highest-contrast frame from a clip, then overlays:
  - Streamer name (large, top area)
  - Hook text (bold, center)
  - Gradient bar at bottom

Output: 1280x720 JPEG (YouTube standard thumbnail size).
Falls back to first frame if brightness analysis fails.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

_FFMPEG_BIN_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / (
    "Microsoft/WinGet/Packages/"
    "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/"
    "ffmpeg-8.0.1-full_build/bin"
)
FFMPEG_BIN = str(_FFMPEG_BIN_DIR / "ffmpeg.exe") if (_FFMPEG_BIN_DIR / "ffmpeg.exe").exists() else "ffmpeg"

THUMB_W = 1280
THUMB_H = 720

# Per-creator accent colors (BGR hex for ffmpeg drawtext)
CREATOR_COLORS: dict[str, str] = {
    "tfue":         "1AFFE4",  # neon cyan
    "cloakzy":      "FF8800",  # orange
    "shroud":       "FFE066",  # gold
    "nickmercs":    "FF5500",  # orange-red
    "timthetatman": "66AAFF",  # sky blue
    "default":      "FFFFFF",  # white
}


def _get_accent(creator: str) -> str:
    return CREATOR_COLORS.get((creator or "").lower(), CREATOR_COLORS["default"])


def _esc(text: str) -> str:
    """Escape for ffmpeg drawtext."""
    return (
        text.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace(":", "\\:")
        .replace(",", "\\,")
    )


def _strip_emoji(text: str) -> str:
    return "".join(c if ord(c) < 128 and (c.isprintable() or c == " ") else "" for c in text).strip()


def _best_frame_timestamp(video_path: str, duration_s: float) -> float:
    """Find the timestamp of the brightest frame in the middle 60% of the clip.

    Samples every 2 seconds in the middle section. Falls back to 25% mark.
    """
    try:
        start = duration_s * 0.2
        end = duration_s * 0.8
        sample_step = max(2.0, (end - start) / 10)

        best_ts = duration_s * 0.25
        best_score = -1.0

        t = start
        while t < end:
            result = subprocess.run(
                [
                    FFMPEG_BIN, "-ss", str(t), "-i", video_path,
                    "-frames:v", "1", "-vf",
                    "scale=160:90,signalstats",
                    "-f", "null", "-",
                ],
                capture_output=True, text=True, timeout=8,
            )
            # Parse YAVG (average luma) from signalstats output
            for line in result.stderr.splitlines():
                if "YAVG" in line:
                    try:
                        val = float(line.split("YAVG:")[1].split()[0])
                        if val > best_score:
                            best_score = val
                            best_ts = t
                    except Exception:
                        pass
            t += sample_step

        return best_ts
    except Exception:
        return duration_s * 0.25


def generate(
    video_path: str,
    output_path: str,
    hook_text: str,
    creator: Optional[str] = None,
    channel_name: Optional[str] = None,
    duration_s: Optional[float] = None,
) -> str:
    """Generate a thumbnail for a clip.

    Args:
        video_path:   Path to the source MP4 (vertical 9:16).
        output_path:  Where to save the thumbnail JPEG.
        hook_text:    Text to display (hook line — max ~40 chars).
        creator:      Streamer name (for accent color + label).
        channel_name: Channel name for watermark.
        duration_s:   Clip duration (auto-detected if None).

    Returns:
        Path to the generated thumbnail JPEG.
    """
    # Auto-detect duration
    if not duration_s:
        try:
            r = subprocess.run(
                [FFMPEG_BIN, "-i", video_path],
                capture_output=True, text=True, timeout=10,
            )
            for line in r.stderr.splitlines():
                if "Duration:" in line:
                    t = line.split("Duration:")[1].split(",")[0].strip()
                    h, m, s = t.split(":")
                    duration_s = float(h) * 3600 + float(m) * 60 + float(s)
                    break
        except Exception:
            duration_s = 30.0

    # Find best frame
    ts = _best_frame_timestamp(video_path, duration_s)

    # Strip emoji from hook text (ffmpeg drawtext doesn't support Unicode)
    hook_clean = _strip_emoji(hook_text)[:45]
    accent = _get_accent(creator or "")

    # Creator label (e.g. "TFUE")
    creator_label = (creator or "").upper()

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tf:
        raw_frame = tf.name

    try:
        # Step 1: Extract best frame, scale to 1280x720 (letterbox the 9:16 source)
        subprocess.run(
            [
                FFMPEG_BIN, "-y", "-ss", str(ts), "-i", video_path,
                "-frames:v", "1",
                "-vf", f"scale={THUMB_W}:{THUMB_H}:force_original_aspect_ratio=decrease,"
                       f"pad={THUMB_W}:{THUMB_H}:(ow-iw)/2:(oh-ih)/2:color=black",
                "-q:v", "2",
                raw_frame,
            ],
            capture_output=True, timeout=15,
        )

        if not os.path.exists(raw_frame) or os.path.getsize(raw_frame) == 0:
            # Fallback: grab first frame
            subprocess.run(
                [FFMPEG_BIN, "-y", "-i", video_path, "-frames:v", "1",
                 "-vf", f"scale={THUMB_W}:{THUMB_H}:force_original_aspect_ratio=decrease,"
                        f"pad={THUMB_W}:{THUMB_H}:(ow-iw)/2:(oh-ih)/2:color=black",
                 "-q:v", "2", raw_frame],
                capture_output=True, timeout=10,
            )

        # Step 2: Burn text overlays onto thumbnail
        font = "C:/Windows/Fonts/Impact.ttf"
        filters = []

        # Dark gradient bar at bottom for CTA area
        filters.append(
            f"drawbox=x=0:y={THUMB_H - 120}:w={THUMB_W}:h=120:color=black@0.55:t=fill"
        )

        # Creator name — large, top-left, accent color
        if creator_label:
            filters.append(
                f"drawtext=fontfile='{font}':"
                f"text='{_esc(creator_label)}':"
                f"fontsize=96:fontcolor=#{accent}:"
                f"borderw=5:bordercolor=black@1.0:"
                f"shadowx=4:shadowy=4:shadowcolor=black@0.8:"
                f"x=40:y=30"
            )

        # Hook text — bold white, center, lower-middle area
        # Split into 2 lines if too long
        words = hook_clean.split()
        if len(hook_clean) > 22 and len(words) > 2:
            mid = len(words) // 2
            line1 = " ".join(words[:mid])
            line2 = " ".join(words[mid:])
            filters.append(
                f"drawtext=fontfile='{font}':"
                f"text='{_esc(line1)}':"
                f"fontsize=88:fontcolor=white:"
                f"borderw=6:bordercolor=black@1.0:"
                f"shadowx=4:shadowy=4:shadowcolor=black@0.8:"
                f"x=(w-text_w)/2:y={THUMB_H // 2 - 60}"
            )
            filters.append(
                f"drawtext=fontfile='{font}':"
                f"text='{_esc(line2)}':"
                f"fontsize=88:fontcolor=white:"
                f"borderw=6:bordercolor=black@1.0:"
                f"shadowx=4:shadowy=4:shadowcolor=black@0.8:"
                f"x=(w-text_w)/2:y={THUMB_H // 2 + 40}"
            )
        else:
            filters.append(
                f"drawtext=fontfile='{font}':"
                f"text='{_esc(hook_clean)}':"
                f"fontsize=96:fontcolor=white:"
                f"borderw=6:bordercolor=black@1.0:"
                f"shadowx=4:shadowy=4:shadowcolor=black@0.8:"
                f"x=(w-text_w)/2:y={THUMB_H // 2 - 30}"
            )

        # Channel watermark — small, bottom-right
        if channel_name:
            watermark = channel_name.replace("_", " ").upper()
            filters.append(
                f"drawtext=fontfile='{font}':"
                f"text='{_esc(watermark)}':"
                f"fontsize=30:fontcolor=white@0.6:"
                f"borderw=2:bordercolor=black@0.5:"
                f"x=w-text_w-20:y=h-text_h-20"
            )

        vf = ",".join(filters)
        result = subprocess.run(
            [
                FFMPEG_BIN, "-y", "-i", raw_frame,
                "-vf", vf,
                "-q:v", "3",
                output_path,
            ],
            capture_output=True, timeout=15,
        )

        if result.returncode != 0:
            # Fallback: use raw frame without text
            import shutil
            shutil.copy(raw_frame, output_path)

    finally:
        try:
            os.unlink(raw_frame)
        except Exception:
            pass

    size_kb = os.path.getsize(output_path) / 1024 if os.path.exists(output_path) else 0
    print(f"[thumbnail] Generated: {os.path.basename(output_path)} ({size_kb:.0f} KB)")
    return output_path
