"""Background video generator for viral_recaps shorts.

Generates an animated gradient background that loops seamlessly.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
import os


def get_ffmpeg() -> str:
    """Get FFmpeg executable path."""
    # Try explicit path first
    _ffmpeg_bin_dir = Path(os.environ.get("LOCALAPPDATA", "")) / (
        "Microsoft/WinGet/Packages/"
        "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/"
        "ffmpeg-8.0.1-full_build/bin"
    )
    if (_ffmpeg_bin_dir / "ffmpeg.exe").exists():
        return str(_ffmpeg_bin_dir / "ffmpeg.exe")
    
    # Fallback: ffmpeg in PATH
    return "ffmpeg"


def generate_background_video(output_path: str = "data/viral_bg.mp4", duration_s: int = 30) -> bool:
    """Generate animated gradient background video.
    
    Args:
        output_path: Where to save the MP4
        duration_s: Duration in seconds (default 30 for 20-second clips with buffer)
    
    Returns:
        True if successful, False otherwise
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    ffmpeg = get_ffmpeg()
    
    # Generate dark animated gradient background (longer to support 20s clips)
    cmd = [
        ffmpeg,
        "-y",  # Overwrite output
        "-f", "lavfi",
        "-i", "gradients=size=1080x1920:x0=0:y0=0:x1=1080:y1=1920:c0=#0f0c29:c1=#302b63:c2=#24243e:nb_colors=3:speed=0.3",
        "-t", str(duration_s),
        "-r", "30",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",  # Speed up encoding
        str(output_path),
    ]
    
    try:
        print(f"[bg_gen] Generating background video: {output_path}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        
        if result.returncode != 0:
            print(f"[bg_gen] FFmpeg error: {result.stderr}")
            return False
        
        print(f"[bg_gen] Background video created: {output_path}")
        return True
    
    except subprocess.TimeoutExpired:
        print("[bg_gen] FFmpeg timeout")
        return False
    except Exception as e:
        print(f"[bg_gen] Error: {e}")
        return False


def get_or_create_background(output_path: str = "data/viral_bg.mp4") -> str:
    """Get existing background or create if missing.
    
    Returns:
        Path to background video
    """
    if Path(output_path).exists():
        print(f"[bg_gen] Using existing background: {output_path}")
        return output_path
    
    if generate_background_video(output_path):
        return output_path
    
    raise RuntimeError(f"Failed to generate background video")


if __name__ == "__main__":
    bg_path = get_or_create_background()
    print(f"Background ready: {bg_path}")
    print(f"File size: {Path(bg_path).stat().st_size / (1024*1024):.1f} MB")
