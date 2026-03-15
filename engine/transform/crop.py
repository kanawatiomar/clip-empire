"""9:16 crop transform.

For horizontal (landscape) video: blurred background fill + centered original.
For vertical (portrait) video:   simple center crop to exact 1080x1920.
For square video:                blurred background fill.

All output: 1080x1920 @ 30fps.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


TARGET_W = 1080
TARGET_H = 1920
TARGET_FPS = 30


def _probe_dimensions(video_path: str) -> tuple[int, int]:
    """Return (width, height) of the video using ffprobe."""
    cmd = [
        "ffprobe", "-v", "quiet",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0",
        video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    try:
        w, h = result.stdout.strip().split(",")
        return int(w), int(h)
    except Exception:
        return 1920, 1080  # fallback assume landscape


class CropTransform:
    """Convert any video to 1080x1920 (9:16) vertical format."""

    def __init__(self, output_dir: str = "intermediate"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def process(
        self,
        input_path: str,
        clip_id: str,
        trim_to_s: float = 55.0,
        crop_anchor: str = "center",
    ) -> str:
        """Crop/reframe video to 9:16 and trim to target length.

        Args:
            input_path:   Source video file path.
            clip_id:      Unique ID for naming the output.
            trim_to_s:    Max duration in seconds (default 55s, under 60s limit).
            crop_anchor:  Horizontal anchor for landscape crops:
                          "left"   — crop window at left  (subject on left side)
                          "center" — center crop (default)
                          "right"  — crop window at right (subject on right side)

        Returns:
            Path to the cropped output video.
        """
        output_path = str(self.output_dir / f"{clip_id}_cropped.mp4")

        if os.path.exists(output_path):
            return output_path  # already processed

        w, h = _probe_dimensions(input_path)

        # Determine crop strategy
        if h > w:
            # Already vertical — center crop to 9:16
            filter_graph = self._vertical_crop_filter(w, h)
        else:
            # Landscape — blur background + anchored original
            filter_graph = self._blur_background_filter(w, h, anchor=crop_anchor)

        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-t", str(trim_to_s),
            "-filter_complex", filter_graph,
            "-map", "[out_v]",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "128k",
            "-r", str(TARGET_FPS),
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            output_path,
        ]

        print(f"[crop] Processing {os.path.basename(input_path)} -> {os.path.basename(output_path)}")
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg crop failed: {result.stderr.decode()[:400]}")

        return output_path

    def _vertical_crop_filter(self, w: int, h: int) -> str:
        """Center crop a vertical video to exactly 1080x1920."""
        # Scale to fit width = 1080, then crop height to 1920
        scale_h = int(h * TARGET_W / w)
        crop_y = max(0, (scale_h - TARGET_H) // 2)
        return (
            f"[0:v]scale={TARGET_W}:{scale_h},"
            f"crop={TARGET_W}:{TARGET_H}:0:{crop_y},"
            f"setsar=1[out_v]"
        )

    def _blur_background_filter(self, w: int, h: int, anchor: str = "center") -> str:
        """Landscape video: blurred full-screen background + anchored original overlay.

        anchor controls where the foreground is horizontally positioned:
          "left"   — foreground snapped to left edge  (keeps left-side content)
          "center" — foreground centered               (default)
          "right"  — foreground snapped to right edge (keeps right-side content)

        Background: scale to 1080x1920, apply heavy gaussian blur.
        Foreground: scale original to fit height, position by anchor.
        """
        # Foreground: scale to full TARGET_H height, keeping aspect ratio
        # This makes the foreground taller → we crop width to TARGET_W via bg
        fg_w = int(w * TARGET_H / h)   # width of fg when scaled to full canvas height
        fg_scale = f"scale={fg_w}:{TARGET_H}:flags=lanczos"

        # Horizontal offset based on anchor
        if anchor == "left":
            overlay_x = "0"
            log_anchor = "left"
        elif anchor == "right":
            overlay_x = f"main_w-overlay_w"   # flush right
            log_anchor = "right"
        else:
            overlay_x = "(main_w-overlay_w)/2"
            log_anchor = "center"

        print(f"[crop] Anchor={log_anchor} (fg_w={fg_w}px -> crop to {TARGET_W}px)")

        return (
            # Background: scale + blur fill
            f"[0:v]scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
            f"crop={TARGET_W}:{TARGET_H},"
            f"gblur=sigma=30[bg];"
            # Foreground: scale to full height
            f"[0:v]{fg_scale}[fg];"
            # Overlay fg on bg at anchor position, crop to canvas
            f"[bg][fg]overlay={overlay_x}:0[out_v]"
        )
