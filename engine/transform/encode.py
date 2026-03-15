"""Final encode: burn captions + normalize audio + produce publish-ready MP4.

Uses NVENC (CUDA) when available on RTX GPU, falls back to libx264.
Output: 1080x1920, H.264, AAC -14 LUFS, ready for YouTube Shorts.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional

_FFMPEG_BIN_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / (
    "Microsoft/WinGet/Packages/"
    "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/"
    "ffmpeg-8.0.1-full_build/bin"
)
FFMPEG_BIN = str(_FFMPEG_BIN_DIR / "ffmpeg.exe") if (_FFMPEG_BIN_DIR / "ffmpeg.exe").exists() else FFMPEG_BIN

TARGET_W = 1080
TARGET_H = 1920
TARGET_LUFS = -14.0
TARGET_PEAK = -1.5


def detect_gpu() -> bool:
    """Return True if ffmpeg NVENC works (tests actual encode, not just presence)."""
    try:
        result = subprocess.run(
            [FFMPEG_BIN, "-hide_banner", "-encoders"],
            capture_output=True, text=True, timeout=10,
        )
        if "h264_nvenc" not in result.stdout:
            return False
        # Actually test NVENC works (driver version check)
        test = subprocess.run(
            [FFMPEG_BIN, "-hide_banner", "-f", "lavfi", "-i", "nullsrc=s=1080x1920:d=0.1",
             "-c:v", "h264_nvenc", "-f", "null", "-"],
            capture_output=True, timeout=10,
        )
        return test.returncode == 0
    except Exception:
        return False


class EncodeTransform:
    """Final encode step: burns ASS captions + normalizes audio + outputs final MP4."""

    def __init__(self, output_dir: str = "renders", use_gpu: Optional[bool] = None):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        # Auto-detect GPU unless explicitly set
        self.use_gpu = detect_gpu() if use_gpu is None else use_gpu
        if self.use_gpu:
            print("[encode] NVENC GPU encoding enabled")
        else:
            print("[encode] CPU encoding (libx264) - no NVENC detected")

    def process(
        self,
        video_path: str,
        clip_id: str,
        channel_name: str,
        ass_path: Optional[str] = None,
    ) -> str:
        """Burn captions into video, normalize audio, produce final MP4.

        Args:
            video_path:   Path to video with overlays already applied.
            clip_id:      Unique clip ID for output naming.
            channel_name: Used for organizing output directory.
            ass_path:     Optional path to .ass subtitle file.

        Returns:
            Path to the final publish-ready MP4.
        """
        channel_dir = self.output_dir / channel_name
        channel_dir.mkdir(parents=True, exist_ok=True)
        output_path = str(channel_dir / f"{clip_id}_final.mp4")

        if os.path.exists(output_path):
            return output_path

        # Build video filter chain
        vf_parts = []

        # Burn ASS subtitles if available
        if ass_path and os.path.exists(ass_path):
            # Escape path for ffmpeg on Windows
            safe_ass = ass_path.replace("\\", "/").replace(":", "\\:")
            vf_parts.append(f"ass={safe_ass}")

        vf_filter = ",".join(vf_parts) if vf_parts else "copy"

        # Build audio filter for loudness normalization
        af_filter = f"loudnorm=I={TARGET_LUFS}:TP={TARGET_PEAK}:LRA=11"

        # Select video codec
        if self.use_gpu:
            vcodec_args = [
                "-c:v", "h264_nvenc",
                "-preset", "p4",        # balanced quality/speed
                "-rc", "vbr",
                "-cq", "23",
                "-b:v", "6M",           # 6 Mbit/s minimum — YouTube rejects sub-1Mbit/s
                "-maxrate", "15M",      # cap at 15 Mbit/s
                "-bufsize", "20M",
                "-profile:v", "high",
            ]
        else:
            vcodec_args = [
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "22",
                "-profile:v", "high",
            ]

        cmd = [
            FFMPEG_BIN, "-y",
            "-i", video_path,
        ]

        if vf_filter != "copy":
            cmd += ["-vf", vf_filter]

        cmd += [
            *vcodec_args,
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "48000",   # resample to 48kHz — YouTube rejects 96kHz audio
            "-af", af_filter,
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-r", "30",
            output_path,
        ]

        print(f"[encode] Final encode -> {os.path.basename(output_path)} ({'NVENC' if self.use_gpu else 'CPU'})")
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg final encode failed:\n{result.stderr.decode()[:500]}")

        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        print(f"[encode] Done: {os.path.basename(output_path)} ({size_mb:.1f} MB)")
        return output_path
