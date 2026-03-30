"""Montage assembler: concatenate clips into a long-form 16:9 compilation.

Takes rendered Shorts clips, pillarboxes vertical ones to 1920x1080,
adds title/outro cards, mixes in background music, and produces a
single montage MP4 ready for YouTube upload.
"""

from __future__ import annotations

import os
import random
import shutil
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

# ── ffmpeg path (mirrors encode.py) ────────────────────────────────────────
_FFMPEG_BIN_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / (
    "Microsoft/WinGet/Packages/"
    "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/"
    "ffmpeg-8.1-full_build/bin"
)
FFMPEG_BIN = str(_FFMPEG_BIN_DIR / "ffmpeg.exe") if (_FFMPEG_BIN_DIR / "ffmpeg.exe").exists() else "ffmpeg"
FFPROBE_BIN = str(_FFMPEG_BIN_DIR / "ffprobe.exe") if (_FFMPEG_BIN_DIR / "ffprobe.exe").exists() else "ffprobe"

OUT_W, OUT_H = 1920, 1080
TITLE_CARD_DUR = 3
OUTRO_CARD_DUR = 3

# Windows font path — use arial as universal fallback, Impact if available
_IMPACT_PATH = Path("C:/Windows/Fonts/impact.ttf")
_ARIAL_PATH = Path("C:/Windows/Fonts/arial.ttf")
_FONT_PATH = str(_IMPACT_PATH) if _IMPACT_PATH.exists() else str(_ARIAL_PATH)
# ffmpeg drawtext needs forward slashes and escaped colons
_FONT_PATH_FF = _FONT_PATH.replace("\\", "/").replace(":", "\\:")

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def _find_bg_music() -> Optional[str]:
    """Pick a random .mp3 from data/ for background music."""
    mp3s = list(DATA_DIR.glob("*.mp3"))
    if not mp3s:
        return None
    return str(random.choice(mp3s))


def _probe_resolution(path: str) -> tuple[int, int]:
    """Return (width, height) of a video file."""
    result = subprocess.run(
        [
            FFPROBE_BIN, "-v", "error",
            "-select_streams", "v:0",
            "-show_entries", "stream=width,height",
            "-of", "csv=p=0:s=x",
            path,
        ],
        capture_output=True, text=True, timeout=15,
    )
    w, h = result.stdout.strip().split("x")
    return int(w), int(h)


def _is_vertical(path: str) -> bool:
    """True if the clip is portrait (9:16)."""
    w, h = _probe_resolution(path)
    return h > w


def _make_title_card(title: str, work_dir: str, filename: str = "title_card.mp4") -> str:
    """Generate a 3-second title card (black bg, white text)."""
    out = os.path.join(work_dir, filename)
    # Escape special characters for drawtext
    safe_title = title.replace("'", "\u2019").replace(":", "\\:")
    subprocess.run(
        [
            FFMPEG_BIN, "-y", "-hide_banner", "-loglevel", "warning",
            "-f", "lavfi", "-i",
            f"color=c=black:s={OUT_W}x{OUT_H}:d={TITLE_CARD_DUR}:r=30",
            "-f", "lavfi", "-i",
            f"anullsrc=r=48000:cl=stereo",
            "-t", str(TITLE_CARD_DUR),
            "-vf", (
                f"drawtext=text='{safe_title}'"
                f":fontfile='{_FONT_PATH_FF}':fontsize=72"
                f":fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2"
                f":borderw=3:bordercolor=black"
            ),
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            out,
        ],
        check=True, capture_output=True, timeout=30,
    )
    return out


def _make_outro_card(work_dir: str) -> str:
    """Generate a 3-second outro card."""
    out = os.path.join(work_dir, "outro_card.mp4")
    subprocess.run(
        [
            FFMPEG_BIN, "-y", "-hide_banner", "-loglevel", "warning",
            "-f", "lavfi", "-i",
            f"color=c=black:s={OUT_W}x{OUT_H}:d={OUTRO_CARD_DUR}:r=30",
            "-f", "lavfi", "-i",
            f"anullsrc=r=48000:cl=stereo",
            "-t", str(OUTRO_CARD_DUR),
            "-vf", (
                "drawtext=text='Subscribe for more\\!'"
                f":fontfile='{_FONT_PATH_FF}':fontsize=80"
                ":fontcolor=white:x=(w-text_w)/2:y=(h-text_h)/2"
                ":borderw=3:bordercolor=black"
            ),
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            out,
        ],
        check=True, capture_output=True, timeout=30,
    )
    return out


def _normalize_clip(clip_path: str, index: int, work_dir: str) -> str:
    """Re-encode a single clip to 1920x1080 30fps with pillarboxing if needed.

    Vertical clips get black bars on the sides. Horizontal clips get
    scaled/padded to exactly 1920x1080.

    Args:
        clip_path: Direct path to the video file.
        index:     Sequence number (for output filename).
        work_dir:  Temporary working directory.
    """
    out = os.path.join(work_dir, f"clip_{index:03d}.mp4")
    # Scale to fit within 1920x1080, then pad to exactly that size
    vf = (
        f"scale={OUT_W}:{OUT_H}:force_original_aspect_ratio=decrease,"
        f"pad={OUT_W}:{OUT_H}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"setsar=1,fps=30"
    )
    subprocess.run(
        [
            FFMPEG_BIN, "-y", "-hide_banner", "-loglevel", "warning",
            "-i", clip_path,
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
            "-pix_fmt", "yuv420p",
            "-shortest",
            out,
        ],
        check=True, capture_output=True, timeout=120,
    )
    return out


def build_montage(
    channel: str,
    clips: list[dict],
    output_path: str | None = None,
    title: str = "Best Moments Compilation",
) -> str:
    """Assemble clips into a montage MP4.

    Args:
        channel:     Channel name (for output directory).
        clips:       List of clip dicts, each with 'render_path' and 'duration_s'.
        output_path: Override output file path. Defaults to
                     rendered_clips/{channel}/montage_{YYYYMMDD}.mp4.
        title:       Title text for the intro card.

    Returns:
        Path to the final montage MP4.
    """
    if not clips:
        raise ValueError("No clips provided for montage")

    # Determine output path
    if output_path is None:
        date_str = datetime.now().strftime("%Y%m%d")
        out_dir = Path("rendered_clips") / channel
        out_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(out_dir / f"montage_{date_str}.mp4")
    else:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Accept either 'duration_s' (DB selector) or 'duration' (fetcher) — skip title card markers
    total_dur = sum(
        c.get("duration_s") or c.get("duration", 0)
        for c in clips if not c.get("is_title_card")
    )
    print(f"[assembler] Building montage: {len(clips)} clips, ~{total_dur:.0f}s")

    with tempfile.TemporaryDirectory(prefix="montage_") as work_dir:
        # 1. Generate title and outro cards
        print("[assembler] Creating title card...")
        title_card = _make_title_card(title, work_dir)

        print("[assembler] Creating outro card...")
        outro_card = _make_outro_card(work_dir)

        # 2. Normalize each clip to 1920x1080 30fps
        normalized = []
        for i, clip in enumerate(clips):
            if clip.get("is_title_card"):
                display = clip.get("creator_display", "???")
                safe_name = display.lower().replace(" ", "_").replace("/", "_")
                print(f"[assembler] Creating creator card: {display}")
                card = _make_title_card(display, work_dir, filename=f"creator_card_{safe_name}_{i}.mp4")
                normalized.append(card)
                continue
            clip_path = clip.get("path") or clip.get("render_path", "")
            print(f"[assembler] Normalizing clip {i+1}/{len(clips)}: {clip.get('title', 'untitled')}")
            norm_path = _normalize_clip(clip_path, i, work_dir)
            normalized.append(norm_path)

        # 3. Write concat list
        concat_list = os.path.join(work_dir, "concat.txt")
        with open(concat_list, "w") as f:
            f.write(f"file '{title_card}'\n")
            for p in normalized:
                f.write(f"file '{p}'\n")
            f.write(f"file '{outro_card}'\n")

        # 4. Concatenate all segments
        concat_out = os.path.join(work_dir, "concat_raw.mp4")
        subprocess.run(
            [
                FFMPEG_BIN, "-y", "-hide_banner", "-loglevel", "warning",
                "-f", "concat", "-safe", "0",
                "-i", concat_list,
                "-c", "copy",
                concat_out,
            ],
            check=True, capture_output=True, timeout=300,
        )

        # 5. Mix in background music if available
        bg_music = _find_bg_music()
        if bg_music:
            print(f"[assembler] Mixing background music: {Path(bg_music).name}")
            subprocess.run(
                [
                    FFMPEG_BIN, "-y", "-hide_banner", "-loglevel", "warning",
                    "-i", concat_out,
                    "-stream_loop", "-1", "-i", bg_music,
                    "-filter_complex",
                    "[0:a]volume=1.0[game];"
                    "[1:a]volume=0.125[music];"  # ~-18dB
                    "[game][music]amix=inputs=2:duration=first:dropout_transition=2[out]",
                    "-map", "0:v", "-map", "[out]",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                    "-c:a", "aac", "-b:a", "192k",
                    "-shortest",
                    output_path,
                ],
                check=True, capture_output=True, timeout=600,
            )
        else:
            print("[assembler] No background music found, re-encoding without")
            subprocess.run(
                [
                    FFMPEG_BIN, "-y", "-hide_banner", "-loglevel", "warning",
                    "-i", concat_out,
                    "-c:v", "libx264", "-preset", "fast", "-crf", "22",
                    "-c:a", "aac", "-b:a", "192k",
                    output_path,
                ],
                check=True, capture_output=True, timeout=600,
            )

        # 6. Apply branding overlays (watermark + subscribe animation)
        print("[assembler] Applying branding overlays...")
        branded_path = output_path.replace(".mp4", "_branded.mp4") if output_path.endswith(".mp4") else output_path + "_branded.mp4"
        _apply_branding(output_path, branded_path, channel_name="Arc Highlightz")
        # Replace final output with branded version
        shutil.move(branded_path, output_path)

    print(f"[assembler] Montage saved to {output_path}")
    return output_path


def _get_video_duration_s(path: str) -> float:
    """Return video duration in seconds."""
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


def _apply_branding(input_path: str, output_path: str, channel_name: str = "Arc Highlightz") -> None:
    """Burn channel watermark + periodic subscribe animation into the video.

    Watermark:
      - Channel name, bottom-right, semi-transparent white with drop shadow
      - Persistent throughout the video

    Subscribe button:
      - Red box + "▶ SUBSCRIBE" text
      - Appears for 4s every 120s starting at t=30
      - Fades in/out via alpha (simulated with enable)
    """
    dur = _get_video_duration_s(input_path)
    if dur <= 0:
        shutil.copy2(input_path, output_path)
        return

    # Build subscribe button enable expression: appears at t=30, 150, 270, 390, ...
    sub_intervals = []
    t = 30.0
    while t + 4 < dur:
        sub_intervals.append(f"between(t,{t:.0f},{t+4:.0f})")
        t += 120.0
    sub_enable = "+".join(sub_intervals) if sub_intervals else "0"

    # Watermark: bottom-right corner, semi-transparent
    watermark_filter = (
        f"drawtext="
        f"text='{channel_name}':"
        f"fontfile='{_FONT_PATH_FF}':"
        f"fontsize=36:"
        f"fontcolor=white@0.55:"
        f"x=w-tw-28:"
        f"y=h-th-22:"
        f"shadowcolor=black@0.6:"
        f"shadowx=2:shadowy=2"
    )

    # Subscribe box (red background): bottom-left corner when subscribe button shows
    sub_box_filter = (
        f"drawbox="
        f"x=24:y=h-74:"
        f"w=280:h=50:"
        f"color=0xFF0000@0.88:"
        f"t=fill:"
        f"enable='{sub_enable}'"
    )

    # Subscribe text on top of red box
    sub_text_filter = (
        f"drawtext="
        f"text='SUBSCRIBE':"
        f"fontfile='{_FONT_PATH_FF}':"
        f"fontsize=26:"
        f"fontcolor=white:"
        f"x=38:"
        f"y=h-58:"
        f"enable='{sub_enable}'"
    )

    vf = ",".join([watermark_filter, sub_box_filter, sub_text_filter])

    result = subprocess.run(
        [
            FFMPEG_BIN, "-y", "-hide_banner", "-loglevel", "warning",
            "-i", input_path,
            "-vf", vf,
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "copy",
            output_path,
        ],
        capture_output=True, timeout=600,
    )
    if result.returncode != 0:
        # If overlay fails (e.g. font issue), just copy without branding
        print(f"[assembler] Warning: branding overlay failed ({result.stderr[:200]}), skipping")
        shutil.copy2(input_path, output_path)
