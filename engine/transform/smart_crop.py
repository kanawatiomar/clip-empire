"""Smart crop — face-detection-based 9:16 crop positioning.

Samples frames from the video, detects faces using OpenCV Haarcascade,
determines the best horizontal crop window, then delegates to the core
crop transform.

Falls back to center crop if no face detected.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

# ── Optional cv2 import (graceful fallback) ───────────────────────────────────
try:
    import cv2
    import numpy as np
    _CV2_AVAILABLE = True
except ImportError:
    _CV2_AVAILABLE = False
    cv2 = None
    np = None

# ── FFmpeg path ───────────────────────────────────────────────────────────────
_FFMPEG_BIN_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / (
    "Microsoft/WinGet/Packages/"
    "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/"
    "ffmpeg-8.0.1-full_build/bin"
)
FFMPEG_BIN = (
    str(_FFMPEG_BIN_DIR / "ffmpeg.exe")
    if (_FFMPEG_BIN_DIR / "ffmpeg.exe").exists()
    else "ffmpeg"
)
FFPROBE_BIN = (
    str(_FFMPEG_BIN_DIR / "ffprobe.exe")
    if (_FFMPEG_BIN_DIR / "ffprobe.exe").exists()
    else "ffprobe"
)

# Target: 9:16 portrait output
TARGET_W = 1080
TARGET_H = 1920
LANDSCAPE_INPUT_W = 1920
LANDSCAPE_INPUT_H = 1080


@dataclass
class SmartCropResult:
    """Result from face-detection-based crop analysis."""

    anchor: str          # "left", "center", or "right"
    crop_x: int          # horizontal pixel offset for 1080px crop window
    face_boxes: List[dict] = field(default_factory=list)   # [{x,y,w,h}, ...]
    sampled_frames: List = field(default_factory=list)     # list of np.ndarray (BGR)


def _get_video_duration(video_path: str) -> float:
    """Return video duration in seconds via ffprobe."""
    cmd = [
        FFPROBE_BIN, "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "csv=p=0",
        video_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return float(result.stdout.strip())
    except Exception:
        return 30.0


def _get_video_dimensions(video_path: str) -> tuple[int, int]:
    """Return (width, height) of the video via ffprobe."""
    cmd = [
        FFPROBE_BIN, "-v", "quiet",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0",
        video_path,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        w, h = result.stdout.strip().split(",")
        return int(w), int(h)
    except Exception:
        return LANDSCAPE_INPUT_W, LANDSCAPE_INPUT_H


def _extract_frame_at(video_path: str, timestamp: float, out_path: str) -> bool:
    """Extract a single frame at the given timestamp using ffmpeg.

    Uses ffmpeg (not cv2.VideoCapture) to avoid codec issues on Windows.
    """
    env = os.environ.copy()
    env["PATH"] = str(_FFMPEG_BIN_DIR) + os.pathsep + env.get("PATH", "")

    cmd = [
        FFMPEG_BIN, "-y",
        "-ss", str(timestamp),
        "-i", video_path,
        "-frames:v", "1",
        "-q:v", "2",
        out_path,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, timeout=30, env=env
        )
        return result.returncode == 0 and Path(out_path).exists()
    except Exception:
        return False


class SmartCropDetector:
    """Detect faces in video and compute optimal 9:16 crop anchor."""

    def __init__(self, video_path: str):
        self.video_path = video_path

    def detect(self) -> SmartCropResult:
        """Run face detection and return a SmartCropResult.

        Returns center crop if cv2 unavailable or no faces found.
        """
        if not _CV2_AVAILABLE:
            print("[smart_crop] cv2 not available — using center crop")
            return SmartCropResult(anchor="center", crop_x=420)

        w, h = _get_video_dimensions(self.video_path)

        # Skip face detection for vertical video
        if h > w:
            print("[smart_crop] Vertical video detected — skipping face detection, center crop")
            return SmartCropResult(anchor="center", crop_x=0)

        duration = _get_video_duration(self.video_path)

        # Sample 3 frames: 25%, 50%, 75% of video duration
        timestamps = [duration * p for p in (0.25, 0.50, 0.75)]

        all_face_centers_x: List[float] = []
        all_face_boxes: List[dict] = []
        sampled_frames = []

        # Load haarcascade classifiers
        frontal_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        profile_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_profileface.xml"
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            for i, ts in enumerate(timestamps):
                frame_path = str(Path(tmpdir) / f"frame_{i}.jpg")
                success = _extract_frame_at(self.video_path, ts, frame_path)
                if not success:
                    print(f"[smart_crop] Failed to extract frame at {ts:.1f}s")
                    continue

                frame = cv2.imread(frame_path)
                if frame is None:
                    print(f"[smart_crop] Could not read frame at {ts:.1f}s")
                    continue

                sampled_frames.append(frame.copy())
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                # Try frontal face detection
                faces = frontal_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.1,
                    minNeighbors=5,
                    minSize=(60, 60),
                )

                # Fallback: profile face detection
                if len(faces) == 0:
                    faces = profile_cascade.detectMultiScale(
                        gray,
                        scaleFactor=1.1,
                        minNeighbors=4,
                        minSize=(60, 60),
                    )

                frame_h, frame_w = frame.shape[:2]

                for (fx, fy, fw, fh) in faces:
                    # Scale to actual video dimensions if frame was resized
                    scale_x = w / frame_w
                    scale_y = h / frame_h
                    actual_x = int(fx * scale_x)
                    actual_y = int(fy * scale_y)
                    actual_w = int(fw * scale_x)
                    actual_h = int(fh * scale_y)

                    face_center_x = actual_x + actual_w / 2
                    all_face_centers_x.append(face_center_x)
                    all_face_boxes.append({
                        "x": actual_x,
                        "y": actual_y,
                        "w": actual_w,
                        "h": actual_h,
                        "frame_w": frame_w,
                        "frame_h": frame_h,
                    })

        if not all_face_centers_x:
            print("[smart_crop] No faces detected — using center crop")
            # Center crop for 1920-wide video: crop_x = (1920 - 1080) // 2 = 420
            center_x = (w - TARGET_W) // 2
            return SmartCropResult(
                anchor="center",
                crop_x=max(0, center_x),
                face_boxes=[],
                sampled_frames=sampled_frames,
            )

        # Compute median face center X
        face_center_x = statistics.median(all_face_centers_x)
        print(f"[smart_crop] Detected {len(all_face_centers_x)} face(s), "
              f"median center_x={face_center_x:.0f}")

        # Determine anchor based on face position in 1920px wide frame
        crop_width = TARGET_W  # 1080
        max_crop_x = w - crop_width  # 840 for 1920-wide video

        if face_center_x < 640:
            # Face is on the left side — anchor left
            anchor = "left"
            crop_x = 0
        elif face_center_x > 1280:
            # Face is on the right side — anchor right
            anchor = "right"
            crop_x = max_crop_x  # 840
        else:
            # Center crop window on the face
            anchor = "center"
            crop_x = int(face_center_x - crop_width / 2)
            # Clamp to valid range [0, max_crop_x]
            crop_x = max(0, min(crop_x, max_crop_x))

        print(f"[smart_crop] Anchor={anchor}, crop_x={crop_x}, "
              f"faces_found={len(all_face_centers_x)}")

        return SmartCropResult(
            anchor=anchor,
            crop_x=crop_x,
            face_boxes=all_face_boxes,
            sampled_frames=sampled_frames,
        )
