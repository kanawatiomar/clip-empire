"""Niche-specific text overlays via ffmpeg drawtext.

Adds:
  1. HOOK TEXT   — bold, large, top third of frame (0-2.5s)
  2. CTA TEXT    — smaller, bottom area (last 3s)
  3. CHANNEL TAG — small watermark bottom-right (entire duration)

All text uses Impact font with thick black outline for maximum readability
on any background.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

_FFMPEG_BIN_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / (
    "Microsoft/WinGet/Packages/"
    "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/"
    "ffmpeg-8.0.1-full_build/bin"
)
FFMPEG_BIN = str(_FFMPEG_BIN_DIR / "ffmpeg.exe") if (_FFMPEG_BIN_DIR / "ffmpeg.exe").exists() else "ffmpeg"
from pathlib import Path
from typing import Optional

from engine.config.templates import get_hook, get_cta
from engine.config.styles import get_overlay_style


def _esc(text: str) -> str:
    """Escape text for ffmpeg drawtext filter."""
    return (
        text.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace(":", "\\:")
        .replace(",", "\\,")
    )


class OverlayTransform:
    """Add hook text + CTA + channel watermark to a video."""

    def __init__(self, output_dir: str = "intermediate"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def process(
        self,
        input_path: str,
        clip_id: str,
        channel_name: str,
        duration_s: float,
        hook_text: Optional[str] = None,
        cta_text: Optional[str] = None,
    ) -> str:
        """Add overlays to video.

        Returns:
            Path to the output video with overlays burned in.
        """
        output_path = str(self.output_dir / f"{clip_id}_overlay.mp4")

        if os.path.exists(output_path):
            return output_path

        hook = hook_text or get_hook(channel_name)
        cta = cta_text or get_cta(channel_name)
        hook_end = min(2.5, duration_s * 0.2)
        cta_start = max(0, duration_s - 3.0)

        filters = self._build_filters(
            hook=hook,
            cta=cta,
            hook_end=hook_end,
            cta_start=cta_start,
            duration_s=duration_s,
            channel_name=channel_name,
        )

        cmd = [
            FFMPEG_BIN, "-y",
            "-i", input_path,
            "-vf", filters,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "22",
            "-c:a", "copy",
            "-pix_fmt", "yuv420p",
            output_path,
        ]

        print(f"[overlay] Adding overlays to {os.path.basename(input_path)}...")
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg overlay failed: {result.stderr.decode()[:400]}")

        return output_path

    def _build_filters(
        self,
        hook: str,
        cta: str,
        hook_end: float,
        cta_start: float,
        duration_s: float,
        channel_name: str,
    ) -> str:
        """Build ffmpeg drawtext filter chain using per-channel style."""
        s = get_overlay_style(channel_name)

        fontfile     = s.get("fontfile", r"C\:/Windows/Fonts/Impact.ttf")
        hook_fs      = s.get("hook_fontsize", 88)
        cta_fs       = s.get("cta_fontsize", 56)
        fontcolor    = s.get("fontcolor", "white")
        borderw      = s.get("borderw", 5)
        bordercolor  = s.get("bordercolor", "black@0.9")
        shadowx      = s.get("shadowx", 3)
        shadowy      = s.get("shadowy", 3)
        shadowcolor  = s.get("shadowcolor", "black@0.7")
        hook_y       = s.get("hook_y", "h/4")

        outline = f"borderw={borderw}:bordercolor={bordercolor}"
        shadow  = f"shadowx={shadowx}:shadowy={shadowy}:shadowcolor={shadowcolor}"

        # Hook text — large, upper area, 0 → hook_end
        hook_filter = (
            f"drawtext=fontfile='{fontfile}':"
            f"text='{_esc(hook)}':"
            f"fontsize={hook_fs}:"
            f"fontcolor={fontcolor}:"
            f"{outline}:{shadow}:"
            f"x=(w-text_w)/2:y={hook_y}:"
            f"enable='between(t,0,{hook_end:.1f})':"
            f"alpha='if(lt(t,0.2),t/0.2,if(gt(t,{hook_end:.1f}-0.15),({hook_end:.1f}-t)/0.15,1))'"
        )

        # CTA text — smaller, lower area, cta_start → end
        cta_filter = (
            f"drawtext=fontfile='{fontfile}':"
            f"text='{_esc(cta)}':"
            f"fontsize={cta_fs}:"
            f"fontcolor={fontcolor}:"
            f"{outline}:{shadow}:"
            f"x=(w-text_w)/2:y=h*0.82:"
            f"enable='between(t,{cta_start:.1f},{duration_s:.1f})'"
        )

        # Channel watermark — small, bottom right, always visible
        watermark_text = channel_name.replace("_", " ").upper()
        watermark_filter = (
            f"drawtext=fontfile='{fontfile}':"
            f"text='{_esc(watermark_text)}':"
            f"fontsize=28:"
            f"fontcolor=white@0.5:"
            f"borderw=2:bordercolor=black@0.5:"
            f"x=w-text_w-20:y=h-text_h-20"
        )

        return ",".join([hook_filter, cta_filter, watermark_filter])
