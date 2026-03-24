"""Meme compositor for viral_recaps.
Strategy: PIL renders text onto a 1080x1920 canvas (background + image + text),
then ffmpeg loops that canvas over the bg video for the final MP4.
This avoids all ffmpeg drawtext/font-path escaping headaches on Windows.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import Optional

import requests
from PIL import Image, ImageDraw, ImageFont, ImageFilter

FFMPEG_BIN_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / (
    "Microsoft/WinGet/Packages/"
    "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/"
    "ffmpeg-8.0.1-full_build/bin"
)
FFMPEG = str(FFMPEG_BIN_DIR / "ffmpeg.exe") if (FFMPEG_BIN_DIR / "ffmpeg.exe").exists() else "ffmpeg"

W, H = 1080, 1920

# Font paths
_FONTS = [
    r"C:\Windows\Fonts\arialbd.ttf",
    r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\DejaVuSans-Bold.ttf",
]
FONT_BOLD_PATH = next((f for f in _FONTS if Path(f).exists()), None)
FONT_REG_PATH  = next((f for f in [r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\DejaVuSans.ttf"] if Path(f).exists()), FONT_BOLD_PATH)


def _load_font(path: Optional[str], size: int) -> ImageFont.FreeTypeFont:
    if path and Path(path).exists():
        return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def download_image(url: str) -> Optional[str]:
    try:
        r = requests.get(url, headers={"User-Agent": "ViralRecaps/1.0"}, timeout=15)
        r.raise_for_status()
        ext = ".png" if url.lower().endswith(".png") else ".jpg"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
        tmp.write(r.content)
        tmp.close()
        return tmp.name
    except Exception as e:
        print(f"[compositor] Download failed: {e}")
        return None


def draw_text_wrapped(draw: ImageDraw.Draw, text: str, font: ImageFont.FreeTypeFont,
                      x: int, y: int, max_width: int, fill: str = "white",
                      stroke: int = 3, stroke_fill: str = "black", align: str = "center") -> int:
    """Draw word-wrapped text, return final y position."""
    lines = textwrap.wrap(text, width=28)
    line_h = font.size + 8
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        lw = bbox[2] - bbox[0]
        if align == "center":
            lx = x + (max_width - lw) // 2
        else:
            lx = x
        draw.text((lx, y), line, font=font, fill=fill,
                  stroke_width=stroke, stroke_fill=stroke_fill)
        y += line_h
    return y


def compose_frame(bg_frame_path: Optional[str], image_path: str,
                  hook_text: str, punchline_text: str) -> Optional[str]:
    """
    Build a 1080x1920 RGBA PNG overlay using PIL:
    - TRANSPARENT background (so bg video shows through)
    - Semi-transparent dark strip behind text for readability
    - Reddit image centered
    - Hook text at top
    - Punchline text at bottom
    Returns path to composed PNG (RGBA).
    """
    try:
        # Start with fully transparent canvas
        canvas = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        draw = ImageDraw.Draw(canvas)

        # Dark semi-transparent strip behind hook text (top)
        draw.rectangle([(0, 0), (W, 220)], fill=(0, 0, 0, 160))

        # Dark semi-transparent strip behind punchline text (bottom)
        if punchline_text and punchline_text.strip():
            draw.rectangle([(0, H - 220), (W, H)], fill=(0, 0, 0, 160))

        # Load fonts
        hook_font   = _load_font(FONT_BOLD_PATH, 56)
        punch_font  = _load_font(FONT_REG_PATH,  44)

        # --- Hook text (top) ---
        hook_y = 55
        hook_y = draw_text_wrapped(draw, hook_text, hook_font, 0, hook_y, W)

        # --- Reddit image (center) ---
        reddit_img = Image.open(image_path).convert("RGBA")
        # Resize to max 940px wide, max 900px tall
        max_iw, max_ih = 940, 900
        ratio = min(max_iw / reddit_img.width, max_ih / reddit_img.height)
        iw = int(reddit_img.width * ratio)
        ih = int(reddit_img.height * ratio)
        reddit_img = reddit_img.resize((iw, ih), Image.Resampling.LANCZOS)

        # Center horizontally, position vertically between hook and punchline
        ix = (W - iw) // 2
        iy_available_start = hook_y + 30
        iy_available_end   = H - 220  # leave room for punchline
        iy = iy_available_start + (iy_available_end - iy_available_start - ih) // 2
        iy = max(iy_available_start, iy)

        canvas.paste(reddit_img, (ix, iy), reddit_img)

        # --- Punchline text (bottom) ---
        if punchline_text and punchline_text.strip():
            punch_y = H - 190
            draw_text_wrapped(draw, punchline_text, punch_font, 0, punch_y, W)

        # Save as RGBA PNG (preserves transparency for ffmpeg overlay)
        out = tempfile.NamedTemporaryFile(delete=False, suffix=".png")
        canvas.save(out.name, "PNG")
        out.close()
        return out.name

    except Exception as e:
        import traceback
        print(f"[compositor] Frame compose error: {e}")
        traceback.print_exc()
        return None


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CAT_BG = str(REPO_ROOT / "data" / "cat_bg.mp4")
MUSIC_BG = str(REPO_ROOT / "data" / "lofi_bg.mp3")


def create_short(bg_video_path: str, image_url: str,
                 hook_text: str, punchline_text: str,
                 output_path: str, duration_s: int = 25) -> bool:
    """
    Full pipeline:
    1. Extract one frame from bg video using ffmpeg
    2. Compose the frame with PIL (bg + image + text)
    3. ffmpeg: loop bg video + composed frame overlay + background music
    """
    print(f"\n[compositor] Creating short: {Path(output_path).name}")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Prefer the real cat bg if available
    bg = CAT_BG if Path(CAT_BG).exists() else bg_video_path
    has_music = Path(MUSIC_BG).exists()

    img_path = download_image(image_url)
    if not img_path:
        return False

    bg_frame = None
    composed = None

    try:
        # Compose transparent overlay with PIL (reddit image + text, transparent bg)
        composed = compose_frame(None, img_path, hook_text, punchline_text)
        if not composed:
            return False

        print(f"[compositor] Frame composed, encoding {duration_s}s MP4 (music={'yes' if has_music else 'no'})...")

        # Step 3: ffmpeg — loop bg video, overlay composed frame, mix music
        # Inputs: [0] looping bg video, [1] composed static frame, [2] music or silence
        if has_music:
            audio_input = ["-stream_loop", "-1", "-i", MUSIC_BG]
            audio_map = ["-map", "2:a"]
            audio_filter = ["-af", f"volume=0.25,afade=t=in:st=0:d=1,afade=t=out:st={duration_s-2}:d=2"]
        else:
            audio_input = ["-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo"]
            audio_map = ["-map", "2:a"]
            audio_filter = []

        cmd = [
            FFMPEG, "-y",
            # bg video looping
            "-stream_loop", "-1", "-i", bg,
            # RGBA overlay PNG (Reddit image + text on transparent bg)
            "-loop", "1", "-i", composed,
            # audio
            *audio_input,
            # trim to duration
            "-t", str(duration_s),
            # video: scale bg, alpha-blend overlay on top
            "-filter_complex",
            "[0:v]scale=1080:1920,setsar=1[bg];"
            "[1:v]scale=1080:1920,format=rgba[overlay];"
            "[bg][overlay]overlay=0:0:format=auto[v]",
            "-map", "[v]",
            *audio_map,
            *audio_filter,
            "-c:v", "libx264", "-preset", "fast", "-crf", "22",
            "-c:a", "aac", "-b:a", "128k",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-r", "30",
            str(output_path),
        ]

        result = subprocess.run(cmd, capture_output=True, timeout=300)
        if result.returncode != 0:
            print(f"[compositor] FFmpeg error:\n{result.stderr.decode(errors='replace')[-800:]}")
            return False

        size_mb = Path(output_path).stat().st_size / (1024 * 1024)
        print(f"[compositor] Done: {size_mb:.1f} MB -> {output_path}")
        return True

    except Exception as e:
        import traceback
        print(f"[compositor] Exception: {e}")
        traceback.print_exc()
        return False
    finally:
        for p in [img_path, composed]:
            if p and Path(p).exists():
                try: Path(p).unlink()
                except: pass
