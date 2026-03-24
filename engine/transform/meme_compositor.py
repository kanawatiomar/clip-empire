"""Meme compositor for viral_recaps — combines background, image, and text into a Short."""

from __future__ import annotations

import subprocess
import os
import tempfile
from pathlib import Path
from typing import Optional
import requests
from PIL import Image
import re


def get_ffmpeg() -> str:
    """Get FFmpeg executable path."""
    _ffmpeg_bin_dir = Path(os.environ.get("LOCALAPPDATA", "")) / (
        "Microsoft/WinGet/Packages/"
        "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/"
        "ffmpeg-8.0.1-full_build/bin"
    )
    if (_ffmpeg_bin_dir / "ffmpeg.exe").exists():
        return str(_ffmpeg_bin_dir / "ffmpeg.exe")
    
    return "ffmpeg"


def download_image(image_url: str, max_retries: int = 3) -> Optional[str]:
    """Download Reddit image to temp file.
    
    Args:
        image_url: URL to download
        max_retries: Number of retry attempts
    
    Returns:
        Path to downloaded image, or None if failed
    """
    for attempt in range(max_retries):
        try:
            headers = {"User-Agent": "ViralRecaps/1.0"}
            response = requests.get(image_url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Determine extension from URL
            ext = ".jpg"
            if ".png" in image_url:
                ext = ".png"
            elif ".gif" in image_url:
                ext = ".gif"
            elif ".webp" in image_url:
                ext = ".webp"
            
            # Save to temp file
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
            temp_file.write(response.content)
            temp_file.close()
            
            print(f"[compositor] Downloaded image: {temp_file.name}")
            return temp_file.name
        
        except Exception as e:
            print(f"[compositor] Error downloading image (attempt {attempt+1}): {e}")
            if attempt < max_retries - 1:
                continue
    
    return None


def resize_and_optimize_image(image_path: str, max_width: int = 900, output_path: Optional[str] = None) -> str:
    """Resize image to fit the video, maintain aspect ratio.
    
    Args:
        image_path: Path to original image
        max_width: Maximum width in pixels
        output_path: Where to save resized image
    
    Returns:
        Path to resized image
    """
    try:
        img = Image.open(image_path)
        
        # Resize to fit width
        if img.width > max_width:
            ratio = max_width / img.width
            new_height = int(img.height * ratio)
            img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
        
        # Save to output
        if output_path is None:
            output_path = image_path.replace(".jpg", "_resized.jpg")
        
        img.save(output_path, quality=90)
        print(f"[compositor] Resized image: {output_path} ({img.width}x{img.height})")
        return output_path
    
    except Exception as e:
        print(f"[compositor] Error resizing image: {e}")
        return image_path


def escape_ffmpeg_text(text: str) -> str:
    """Escape special characters for FFmpeg drawtext filter."""
    # Replace problematic characters
    text = text.replace("'", "'\\''")  # Single quotes
    text = text.replace('"', '\\"')    # Double quotes
    text = text.replace("\\", "\\\\")  # Backslashes
    text = text.replace(":", "\\:")    # Colons
    # Keep newlines as \n for line breaks
    return text


def build_drawtext_filter(
    text: str,
    y_position: int,
    font_size: int = 52,
    is_hook: bool = True,
) -> str:
    """Build FFmpeg drawtext filter string.
    
    Args:
        text: Text to draw (may contain \n for line breaks)
        y_position: Y position on video
        font_size: Font size in points
        is_hook: True for hook (bold), False for punchline (normal)
    
    Returns:
        FFmpeg filter string
    """
    # Choose font
    font_file = r"C:\Windows\Fonts\arialbd.ttf" if is_hook else r"C:\Windows\Fonts\arial.ttf"
    if not Path(font_file).exists():
        # Fallback fonts
        font_file = r"C:\Windows\Fonts\arial.ttf"
    
    # Escape text for FFmpeg drawtext filter
    # For drawtext, we need to escape: quotes, colons, and newlines
    safe_text = text.replace("\\", "\\\\")  # Backslash first
    safe_text = safe_text.replace(":", "\\:")  # Colons
    safe_text = safe_text.replace("'", "\\'")  # Single quotes
    safe_text = safe_text.replace("\n", "\\n")  # Newlines as literal \n
    
    # Build filter using proper syntax
    filter_str = (
        f"drawtext=fontfile='{font_file}':"
        f"text='{safe_text}':"
        f"fontsize={font_size}:"
        f"fontcolor=white:"
        f"box=1:"
        f"boxcolor=black@0.3:"
        f"boxborderw=3:"
        f"x=(w-text_w)/2:"
        f"y={y_position}"
    )
    
    return filter_str


def composite_video(
    bg_video_path: str,
    image_path: str,
    hook_text: str,
    punchline_text: str,
    output_path: str,
    duration_s: int = 20,
) -> bool:
    """Composite all elements into final video.
    
    Args:
        bg_video_path: Path to looping background video
        image_path: Path to Reddit screenshot image
        hook_text: Hook text for top
        punchline_text: Punchline text for bottom
        output_path: Where to save final MP4
        duration_s: Duration of final video
    
    Returns:
        True if successful, False otherwise
    """
    ffmpeg = get_ffmpeg()
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # Get image dimensions to calculate overlay position
        img = Image.open(image_path)
        img_width = img.width
        img_height = img.height
        
        # Center image horizontally, position vertically
        overlay_x = (1080 - img_width) // 2  # Center X
        overlay_y = 400  # Center-ish vertically
        
        print(f"[compositor] Image dims: {img_width}x{img_height}")
        print(f"[compositor] Overlay position: x={overlay_x}, y={overlay_y}")
        
        # Build simple filter chain: scale bg, overlay image
        filter_str = (
            f"[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,"
            f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2[bg];"
            f"[1:v]scale={img_width}:{img_height}[img];"
            f"[bg][img]overlay=x={overlay_x}:y={overlay_y}:eof_action=endall[final]"
        )
        
        cmd = [
            ffmpeg,
            "-y",  # Overwrite output
            "-i", bg_video_path,  # Background video input
            "-i", image_path,  # Image input
            "-f", "lavfi",  # Audio: silent
            "-i", "anullsrc=r=44100:cl=stereo",
            "-t", str(duration_s),  # Limit output to specified duration
            "-filter_complex", filter_str,  # Complex filter
            "-map", "[final]",  # Map final video
            "-map", "2:a",  # Map silent audio (input 2)
            "-c:v", "libx264",  # Video codec
            "-c:a", "aac",  # Audio codec
            "-b:a", "128k",  # Audio bitrate
            "-pix_fmt", "yuv420p",  # Pixel format
            "-preset", "fast",  # Speed
            str(output_path),
        ]
        
        print(f"[compositor] Running FFmpeg...")
        print(f"[compositor] Output: {output_path}")
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            timeout=300,  # 5 minute timeout for encoding
            encoding='utf-8',
            errors='replace'
        )
        
        if result.returncode != 0:
            err_msg = result.stderr if result.stderr else "Unknown error"
            print(f"[compositor] FFmpeg error: {err_msg[-500:]}")  # Last 500 chars
            return False
        
        if not Path(output_path).exists():
            print(f"[compositor] Output file not created")
            return False
        
        file_size_mb = Path(output_path).stat().st_size / (1024 * 1024)
        print(f"[compositor] Success! Output: {file_size_mb:.1f} MB")
        return True
    
    except subprocess.TimeoutExpired:
        print("[compositor] FFmpeg timeout")
        return False
    except Exception as e:
        print(f"[compositor] Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def create_short(
    bg_video_path: str,
    image_url: str,
    hook_text: str,
    punchline_text: str,
    output_path: str,
    duration_s: int = 20,
) -> bool:
    """Create a viral_recaps short from Reddit post data.
    
    Args:
        bg_video_path: Path to background video
        image_url: URL to Reddit image/screenshot
        hook_text: Hook text (already word-wrapped)
        punchline_text: Punchline text (already word-wrapped)
        output_path: Where to save final MP4
        duration_s: Duration of short
    
    Returns:
        True if successful, False otherwise
    """
    print(f"\n[compositor] Creating short: {output_path}")
    
    # Download image
    image_path = download_image(image_url)
    if not image_path:
        print("[compositor] Failed to download image")
        return False
    
    try:
        # Resize image
        resized_path = resize_and_optimize_image(image_path, max_width=900)
        
        # Composite video
        success = composite_video(
            bg_video_path,
            resized_path,
            hook_text,
            punchline_text,
            output_path,
            duration_s=duration_s,
        )
        
        return success
    
    finally:
        # Clean up temp files
        if Path(image_path).exists():
            Path(image_path).unlink()
        if resized_path != image_path and Path(resized_path).exists():
            Path(resized_path).unlink()


if __name__ == "__main__":
    print("[compositor] Testing meme compositor...")
    
    # This would require actual files, so just print test info
    hook = "This is wild\nSeriously crazy"
    punchline = "Can't believe it\nLol"
    
    print(f"Hook text escaped: {escape_ffmpeg_text(hook)}")
    print(f"Punchline text escaped: {escape_ffmpeg_text(punchline)}")
    print("[compositor] Test complete")
