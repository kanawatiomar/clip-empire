"""9:16 crop transform.

For horizontal (landscape) video: blurred background fill + centered original.
For vertical (portrait) video:   simple center crop to exact 1080x1920.
For square video:                blurred background fill.

All output: 1080x1920 @ 30fps.
"""

from __future__ import annotations

import os
import statistics
import subprocess
from pathlib import Path

# ── FFmpeg/FFprobe path resolution ───────────────────────────────────────────
_FFMPEG_BIN_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / (
    "Microsoft/WinGet/Packages/"
    "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/"
    "ffmpeg-8.0.1-full_build/bin"
)
FFPROBE_BIN = str(_FFMPEG_BIN_DIR / "ffprobe.exe") if (_FFMPEG_BIN_DIR / "ffprobe.exe").exists() else "ffprobe"
FFMPEG_BIN  = str(_FFMPEG_BIN_DIR / "ffmpeg.exe")  if (_FFMPEG_BIN_DIR / "ffmpeg.exe").exists()  else "ffmpeg"

TARGET_W = 1080
TARGET_H = 1920
TARGET_FPS = 30


def _probe_dimensions(video_path: str) -> tuple[int, int]:
    """Return (width, height) of the video using ffprobe."""
    cmd = [
        FFPROBE_BIN, "-v", "quiet",
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

    def process(self, input_path: str, clip_id: str, trim_to_s: float = 55.0,
                smart: bool = True) -> str:
        """Crop/reframe video to 9:16 and trim to target length.

        Args:
            input_path: Source video file path.
            clip_id:    Unique ID for naming the output.
            trim_to_s:  Max duration in seconds (default 55s, keeps under 60s limit).
            smart:      Use face-detection smart crop for landscape videos.

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
            # Landscape — attempt smart (face-detection) crop, fall back to blur+center
            smart_crop_x = None
            if smart:
                try:
                    from engine.transform.smart_crop import SmartCropDetector
                    result = SmartCropDetector(input_path).detect()
                    if result.face_boxes:
                        smart_crop_x = result.crop_x
                        face_center_x = (
                            statistics.median(
                                b["x"] + b["w"] / 2 for b in result.face_boxes
                            )
                            if result.face_boxes else None
                        )
                        print(
                            f"[crop] Smart crop: anchor={result.anchor}, "
                            f"face_center_x={face_center_x:.0f}, "
                            f"faces_found={len(result.face_boxes)}"
                        )
                except Exception as e:
                    print(f"[crop] Smart crop failed (non-fatal): {e}")

            if smart_crop_x is not None:
                filter_graph = self._smart_crop_filter(w, h, smart_crop_x)
            else:
                filter_graph = self._blur_background_filter(w, h)

        cmd = [
            FFMPEG_BIN, "-y",
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

        print(f"[crop] Processing {os.path.basename(input_path)} → {os.path.basename(output_path)}")
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode != 0:
            raise RuntimeError(f"ffmpeg crop failed: {result.stderr.decode()[:400]}")

        return output_path

    def _smart_crop_filter(self, w: int, h: int, crop_x: int) -> str:
        """Landscape video: smart face-anchored crop to 9:16 (no blur background).

        Crops a 1080-wide window starting at crop_x, then scales to 1080x1920.
        """
        crop_w = TARGET_W    # 1080
        crop_h = h           # full height (e.g. 1080)
        # Clamp crop_x to valid range
        crop_x = max(0, min(crop_x, w - crop_w))
        # Scale crop to 1080x1920
        return (
            f"[0:v]crop={crop_w}:{crop_h}:{crop_x}:0,"
            f"scale={TARGET_W}:{TARGET_H}:flags=lanczos,"
            f"setsar=1[out_v]"
        )

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

    def _blur_background_filter(self, w: int, h: int) -> str:
        """Landscape video: blurred full-screen background + centered original overlay.

        Background: scale to 1080x1920, apply heavy gaussian blur.
        Foreground: scale original to fit within 1080x1080 (centered).
        """
        # Foreground: fit within 1080 wide (letterboxed)
        fg_scale = f"scale={TARGET_W}:-2:flags=lanczos"
        # Position foreground in center of 1920-height canvas
        overlay_y = "(main_h-overlay_h)/2"

        return (
            # Background: scale + blur fill
            f"[0:v]scale={TARGET_W}:{TARGET_H}:force_original_aspect_ratio=increase,"
            f"crop={TARGET_W}:{TARGET_H},"
            f"gblur=sigma=30[bg];"
            # Foreground: scale to fit width
            f"[0:v]{fg_scale}[fg];"
            # Overlay fg centered on bg
            f"[bg][fg]overlay=(main_w-overlay_w)/2:{overlay_y}[out_v]"
        )
