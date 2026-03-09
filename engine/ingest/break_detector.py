"""break_detector.py - Detect and trim Twitch commercial break screens from clip start.

Twitch commercial break screens are solid purple/blue gradient frames.
We detect them by checking for low scene complexity + dominant cool hue.
If the first N seconds look like a break screen, we trim that section.

Ported and adapted from Arc Highlightz standalone engine.
"""

from __future__ import annotations

import subprocess
import logging
from pathlib import Path

logger = logging.getLogger("clip_empire.break_detector")

# Purple/blue hue range typical of Twitch break screens (ffmpeg hue 200-290 degrees)
BREAK_HUE_MIN = 180
BREAK_HUE_MAX = 300
BREAK_MAX_COMPLEXITY = 0.15   # Low complexity = mostly uniform color
BREAK_MIN_SATURATION = 20     # Must be somewhat saturated (not gray)
MAX_BREAK_SCAN_S = 5.0        # Only scan the first 5s for a break screen
BREAK_FRAME_INTERVAL = 0.5    # Check every 0.5s


def _get_frame_stats(video_path: Path, timestamp: float) -> dict | None:
    """Extract color stats for a single frame via ffmpeg signalstats."""
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-select_streams", "v:0",
        "-read_intervals", f"%+#{int(timestamp * 30)}",  # approximate frame seek
        "-show_entries", "frame_tags=lavfi.signalstats.HUEAVG,lavfi.signalstats.SATAVG,lavfi.signalstats.YAVG",
        "-vf", f"select='eq(n\\,{max(0, int(timestamp * 30))})',signalstats",
        "-of", "json",
        str(video_path),
    ]
    # Simpler approach: use ffmpeg stderr with signalstats filter
    cmd2 = [
        "ffmpeg",
        "-ss", f"{timestamp:.2f}",
        "-i", str(video_path),
        "-vframes", "1",
        "-vf", "signalstats",
        "-f", "null", "-",
    ]
    try:
        result = subprocess.run(cmd2, capture_output=True, text=True, timeout=10)
        stats: dict = {}
        for line in result.stderr.split("\n"):
            if "YAVG=" in line:
                try:
                    stats["luma"] = float(line.split("YAVG=")[1].split()[0])
                except (ValueError, IndexError):
                    pass
            if "SATAVG=" in line:
                try:
                    stats["sat"] = float(line.split("SATAVG=")[1].split()[0])
                except (ValueError, IndexError):
                    pass
            if "HUEAVG=" in line:
                try:
                    stats["hue"] = float(line.split("HUEAVG=")[1].split()[0])
                except (ValueError, IndexError):
                    pass
        return stats if stats else None
    except Exception as e:
        logger.debug("Frame stats failed at %.2fs: %s", timestamp, e)
        return None


def _is_break_frame(stats: dict) -> bool:
    """Return True if frame stats look like a Twitch break screen."""
    if not stats:
        return False
    hue = stats.get("hue", -1)
    sat = stats.get("sat", 0)
    # Must have cool hue (blue/purple) AND be saturated AND be relatively bright
    if BREAK_HUE_MIN <= hue <= BREAK_HUE_MAX and sat >= BREAK_MIN_SATURATION:
        return True
    return False


def detect_break_duration(video_path: Path) -> float:
    """Scan the clip start for a commercial break screen.

    Returns the number of seconds to trim from the start (0.0 if no break detected).
    """
    trim_s = 0.0
    t = 0.0
    consecutive_break = 0

    while t <= MAX_BREAK_SCAN_S:
        stats = _get_frame_stats(video_path, t)
        if stats and _is_break_frame(stats):
            consecutive_break += 1
            trim_s = t + BREAK_FRAME_INTERVAL  # trim up to this point
            logger.debug("Break frame at %.2fs: hue=%.1f sat=%.1f", t, stats.get("hue", 0), stats.get("sat", 0))
        else:
            if consecutive_break >= 2:
                # Found a real break screen, confirmed
                break
            consecutive_break = 0
            trim_s = 0.0  # Reset if we saw non-break frames first
        t += BREAK_FRAME_INTERVAL

    if trim_s > 0:
        logger.info("Break screen detected — trimming first %.1fs of %s", trim_s, video_path.name)
    return trim_s


def trim_break_screen(video_path: Path, output_path: Path) -> Path:
    """Trim commercial break screen from clip start if detected.

    Returns output_path (trimmed) or video_path (unchanged if no break detected).
    """
    trim_s = detect_break_duration(video_path)
    if trim_s <= 0:
        return video_path  # Nothing to trim

    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{trim_s:.2f}",
        "-i", str(video_path),
        "-c", "copy",
        str(output_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode == 0 and output_path.exists():
            logger.info("Trimmed %.1fs break screen: %s -> %s", trim_s, video_path.name, output_path.name)
            return output_path
        else:
            logger.warning("Break trim failed: %s", result.stderr[:200])
            return video_path
    except Exception as e:
        logger.warning("Break trim error: %s", e)
        return video_path
