"""Montage assembler: concatenate clips into a long-form 16:9 compilation.

Takes rendered Shorts clips, pillarboxes vertical ones to 1920x1080,
adds title/outro cards, mixes in background music, and produces a
single montage MP4 ready for YouTube upload.
"""

from __future__ import annotations

import os
import random
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
FONT = "Impact"

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


def _make_title_card(title: str, work_dir: str) -> str:
    """Generate a 3-second title card (black bg, white text)."""
    out = os.path.join(work_dir, "title_card.mp4")
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
                f":fontfile=Impact.ttf:fontsize=72"
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
                ":fontfile=Impact.ttf:fontsize=80"
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

    total_dur = sum(c["duration_s"] for c in clips)
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
                print(f"[assembler] Creating creator card: {clip.get('creator_display', '???')}")
                card = _make_title_card(clip["creator_display"], work_dir)
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

    print(f"[assembler] Montage saved to {output_path}")
    return output_path
