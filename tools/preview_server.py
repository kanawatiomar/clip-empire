"""Clip Empire — Style Preview Server

Renders live preview frames showing hook text, CTA, and caption style
for any channel. No actual clip needed — generates test frames on the fly.

Usage:
    python tools/preview_server.py
    # Then open http://localhost:5050 in your browser
"""

from __future__ import annotations

import os
import sys
import io
import base64
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template_string, request, jsonify
from PIL import Image, ImageDraw, ImageFont
from engine.config.styles import CHANNEL_STYLE_MAP, STYLE_PRESETS, get_overlay_style, get_caption_style
from engine.config.templates import get_hook, get_cta
from engine.transform.overlay import _strip_emoji
from accounts.channel_definitions import CHANNELS

# ── Smart crop import (graceful fallback) ─────────────────────────────────────
try:
    from engine.transform.smart_crop import SmartCropDetector, SmartCropResult
    _SMART_CROP_AVAILABLE = True
except ImportError:
    _SMART_CROP_AVAILABLE = False

app = Flask(__name__)

# ── ffmpeg path ───────────────────────────────────────────────────────────────
_FFMPEG_BIN_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / (
    "Microsoft/WinGet/Packages/"
    "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/"
    "ffmpeg-8.0.1-full_build/bin"
)
FFMPEG = str(_FFMPEG_BIN_DIR / "ffmpeg.exe") if (_FFMPEG_BIN_DIR / "ffmpeg.exe").exists() else "ffmpeg"

# Font paths for PIL rendering
PIL_FONTS = {
    "Impact":      "C:/Windows/Fonts/Impact.ttf",
    "Arial Black": "C:/Windows/Fonts/arialbd.ttf",
    "Arial":       "C:/Windows/Fonts/arial.ttf",
}

# ── HTML template ─────────────────────────────────────────────────────────────
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Clip Empire — Style Preview</title>
<style>
  :root { --bg: #0d0d0d; --card: #1a1a1a; --border: #2a2a2a; --accent: #6c63ff; --text: #e8e8e8; --muted: #888; }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { background: var(--bg); color: var(--text); font-family: 'Segoe UI', system-ui, sans-serif; min-height: 100vh; }
  header { padding: 20px 32px; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 12px; }
  header h1 { font-size: 20px; font-weight: 700; }
  header span { color: var(--muted); font-size: 13px; }
  .layout { display: grid; grid-template-columns: 280px 1fr; height: calc(100vh - 65px); }
  .sidebar { border-right: 1px solid var(--border); overflow-y: auto; padding: 16px; }
  .sidebar h2 { font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: var(--muted); margin-bottom: 10px; }
  .ch-btn { display: block; width: 100%; text-align: left; padding: 10px 14px; margin-bottom: 4px;
            background: var(--card); border: 1px solid var(--border); border-radius: 8px;
            color: var(--text); font-size: 13px; cursor: pointer; transition: all .15s; }
  .ch-btn:hover { border-color: var(--accent); }
  .ch-btn.active { border-color: var(--accent); background: #1d1b33; }
  .ch-btn .niche { font-size: 11px; color: var(--muted); margin-top: 2px; }
  .main { display: grid; grid-template-columns: 1fr 1fr; gap: 0; overflow-y: auto; }
  .preview-panel { padding: 24px; border-right: 1px solid var(--border); }
  .preview-panel h2 { font-size: 13px; color: var(--muted); margin-bottom: 16px; text-transform: uppercase; letter-spacing: 1px; }
  .phone-frame { width: 270px; height: 480px; border: 3px solid #333; border-radius: 24px; overflow: hidden;
                 position: relative; background: #111; margin: 0 auto; }
  .phone-frame img { width: 100%; height: 100%; object-fit: cover; }
  .loading { display: flex; align-items: center; justify-content: center; height: 100%; color: var(--muted); font-size: 13px; }
  .config-panel { padding: 24px; overflow-y: auto; }
  .config-panel h2 { font-size: 13px; color: var(--muted); margin-bottom: 16px; text-transform: uppercase; letter-spacing: 1px; }
  .config-group { background: var(--card); border: 1px solid var(--border); border-radius: 10px; padding: 16px; margin-bottom: 12px; }
  .config-group h3 { font-size: 12px; text-transform: uppercase; letter-spacing: 1px; color: var(--accent); margin-bottom: 12px; }
  .config-row { display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }
  .config-row label { font-size: 12px; color: var(--muted); }
  .config-row .val { font-size: 12px; font-family: monospace; color: var(--text); }
  .preview-label { text-align: center; margin-top: 10px; font-size: 12px; color: var(--muted); }
  .tab-row { display: flex; gap: 8px; margin-bottom: 16px; }
  .tab { padding: 6px 14px; border-radius: 6px; border: 1px solid var(--border); background: var(--card);
         color: var(--muted); font-size: 12px; cursor: pointer; }
  .tab.active { border-color: var(--accent); color: var(--text); background: #1d1b33; }
  .swatch { display: inline-block; width: 14px; height: 14px; border-radius: 3px; border: 1px solid #444;
            vertical-align: middle; margin-right: 4px; }
</style>
</head>
<body>
<header>
  <h1>🎬 Style Preview</h1>
  <span>Clip Empire — Channel Visual Identity</span>
</header>
<div class="layout">
  <div class="sidebar">
    <h2>Channels</h2>
    {% for ch, defn in channels.items() %}
    <button class="ch-btn {% if loop.first %}active{% endif %}" onclick="selectChannel('{{ ch }}', this)">
      {{ defn.display_name }}
      <div class="niche">{{ defn.niche }}</div>
    </button>
    {% endfor %}
  </div>
  <div class="main">
    <div class="preview-panel">
      <h2>Preview</h2>
      <div class="tab-row">
        <button class="tab active" onclick="setTab('hook', this)">Hook Frame</button>
        <button class="tab" onclick="setTab('cta', this)">CTA Frame</button>
        <button class="tab" onclick="setTab('caption', this)">Captions</button>
        <button class="tab" onclick="setTab('crop', this)">Crop Preview</button>
      </div>
      <div class="phone-frame">
        <div class="loading" id="loading">Loading...</div>
        <img id="preview-img" style="display:none" src="" alt="preview">
      </div>
      <div class="preview-label" id="preview-label"></div>
    </div>
    <div class="config-panel">
      <h2>Style Config</h2>
      <div id="config-display"></div>
    </div>
  </div>
</div>
<script>
  let currentChannel = '{{ channels.keys()|list|first }}';
  let currentTab = 'hook';

  function selectChannel(ch, btn) {
    document.querySelectorAll('.ch-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentChannel = ch;
    loadPreview();
  }

  function setTab(tab, btn) {
    document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentTab = tab;
    loadPreview();
  }

  function loadPreview() {
    const img = document.getElementById('preview-img');
    const loading = document.getElementById('loading');
    img.style.display = 'none';
    loading.style.display = 'flex';
    loading.textContent = 'Rendering...';

    const url = `/preview?channel=${currentChannel}&tab=${currentTab}&t=${Date.now()}`;
    fetch(url)
      .then(r => r.json())
      .then(data => {
        img.src = 'data:image/png;base64,' + data.image;
        img.style.display = 'block';
        loading.style.display = 'none';
        document.getElementById('preview-label').textContent = data.label || '';
        renderConfig(data.style);
      })
      .catch(e => { loading.textContent = 'Error: ' + e; });
  }

  function renderConfig(style) {
    if (!style) return;
    const el = document.getElementById('config-display');

    const section = (title, data) => {
      const rows = Object.entries(data).map(([k, v]) => {
        const isColor = typeof v === 'string' && v.startsWith('&H');
        const swatch = isColor ? `<span class="swatch" style="background:${assColorToCSS(v)}"></span>` : '';
        return `<div class="config-row"><label>${k}</label><span class="val">${swatch}${v}</span></div>`;
      }).join('');
      return `<div class="config-group"><h3>${title}</h3>${rows}</div>`;
    };

    el.innerHTML = section('Caption Style', style.caption) + section('Overlay Style', style.overlay);
  }

  function assColorToCSS(ass) {
    // &HAABBGGRR → rgba
    if (!ass || ass.length < 8) return '#888';
    const hex = ass.replace('&H', '');
    const a = parseInt(hex.substring(0, 2), 16);
    const b = parseInt(hex.substring(2, 4), 16);
    const g = parseInt(hex.substring(4, 6), 16);
    const r = parseInt(hex.substring(6, 8), 16);
    return `rgba(${r},${g},${b},${1 - a/255})`;
  }

  // Load first channel on start
  loadPreview();
</script>
</body>
</html>
"""

# ── Crop Preview renderer ─────────────────────────────────────────────────────

def _find_latest_raw_clip() -> Optional[str]:
    """Find the most recently downloaded raw clip across all channel folders."""
    base = Path(__file__).parent.parent / "raw_clips"
    if not base.exists():
        return None
    candidates = list(base.rglob("*.mp4")) + list(base.rglob("*.mkv")) + list(base.rglob("*.webm"))
    if not candidates:
        return None
    # Sort by modification time descending
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return str(candidates[0])


def _render_crop_preview() -> tuple[bytes, str]:
    """Render a before/after composite showing smart crop face detection results.

    Returns (PNG bytes, label string).
    """
    import numpy as np

    PREVIEW_W = 540  # composite image width

    # ── 1. Find a raw clip ────────────────────────────────────────────────────
    clip_path = _find_latest_raw_clip()
    test_frame_generated = False

    if clip_path is None or not _SMART_CROP_AVAILABLE:
        # Generate a synthetic test frame (solid color + simulated face box)
        frame_w, frame_h = 1920, 1080
        arr = np.zeros((frame_h, frame_w, 3), dtype=np.uint8)
        arr[:] = (40, 60, 80)  # dark blue-grey background
        # Simulated face region
        face_x, face_y, face_w, face_h = 700, 200, 200, 260
        arr[face_y:face_y + face_h, face_x:face_x + face_w] = (180, 140, 110)
        result = SmartCropResult(
            anchor="center",
            crop_x=420,
            face_boxes=[{"x": face_x, "y": face_y, "w": face_w, "h": face_h,
                         "frame_w": frame_w, "frame_h": frame_h}],
            sampled_frames=[arr],
        ) if _SMART_CROP_AVAILABLE else None
        test_frame_generated = True
        source_frame = Image.fromarray(arr[..., ::-1])  # BGR→RGB
        crop_x = 420
        anchor = "center"
        faces_found = 1
    else:
        # ── 2. Run SmartCropDetector on the clip ──────────────────────────────
        try:
            detector = SmartCropDetector(clip_path)
            result = detector.detect()
        except Exception as e:
            # Fall back to a blank result
            result = SmartCropResult(anchor="center", crop_x=420)

        crop_x = result.crop_x
        anchor = result.anchor
        faces_found = len(result.face_boxes)

        # Use first sampled frame for the preview
        if result.sampled_frames:
            raw_frame = result.sampled_frames[0]  # BGR numpy array
            source_frame = Image.fromarray(raw_frame[..., ::-1])  # BGR→RGB
        else:
            # Blank frame
            source_frame = Image.new("RGB", (1920, 1080), (40, 40, 40))

    # ── 3. Build composite image ──────────────────────────────────────────────
    # Dimensions
    orig_w, orig_h = source_frame.size  # e.g. 1920x1080

    # Scale source frame to PREVIEW_W wide
    scale = PREVIEW_W / orig_w
    thumb_w = PREVIEW_W
    thumb_h = int(orig_h * scale)

    thumb = source_frame.resize((thumb_w, thumb_h), Image.LANCZOS)
    draw_thumb = ImageDraw.Draw(thumb)

    # Draw face detection boxes in green (scaled to thumb coords)
    for box in (result.face_boxes if result else []):
        bx = int(box["x"] * scale)
        by = int(box["y"] * scale)
        bw = int(box["w"] * scale)
        bh = int(box["h"] * scale)
        draw_thumb.rectangle([bx, by, bx + bw, by + bh], outline=(0, 255, 0), width=2)

    # Draw 9:16 crop window rectangle in red (scaled)
    crop_w_orig = 1080  # the 1080px crop window on original frame
    rx0 = int(crop_x * scale)
    rx1 = int((crop_x + crop_w_orig) * scale)
    draw_thumb.rectangle([rx0, 0, rx1, thumb_h - 1], outline=(255, 0, 0), width=3)

    # Build the cropped result preview
    # Crop from source frame, then scale down to a 9:16 thumbnail
    crop_left = crop_x
    crop_right = crop_x + crop_w_orig
    crop_left = max(0, min(crop_left, orig_w - crop_w_orig))
    crop_right = crop_left + crop_w_orig

    cropped_full = source_frame.crop((crop_left, 0, crop_right, orig_h))
    # Scale cropped (1080x1080 or narrower) to fill 9:16: scale height to 1920 proportion
    # For preview: show as 9:16 thumbnail, ~270x480 (half of 540x960)
    crop_thumb_w = PREVIEW_W // 2
    crop_thumb_h = int(crop_thumb_w * (1920 / 1080))  # 9:16 ratio
    # Fit-within box
    crop_preview = cropped_full.resize(
        (crop_thumb_w, int(cropped_full.size[1] * crop_thumb_w / cropped_full.size[0])),
        Image.LANCZOS,
    )

    # ── 4. Compose: top = landscape thumb, bottom = 9:16 crop result ─────────
    try:
        label_font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 14)
    except Exception:
        label_font = ImageFont.load_default()

    label_h = 24
    gap = 8
    total_h = thumb_h + label_h + gap + crop_preview.size[1] + label_h

    composite = Image.new("RGB", (PREVIEW_W, total_h), (13, 13, 13))
    composite.paste(thumb, (0, 0))

    cdraw = ImageDraw.Draw(composite)
    # Top label
    cdraw.text(
        (8, thumb_h + 4),
        f"Original (1920×1080) | faces={faces_found} | anchor={anchor} | crop_x={crop_x}",
        font=label_font,
        fill=(200, 200, 200),
    )

    # Paste cropped preview centered
    crop_y_offset = thumb_h + label_h + gap
    paste_x = (PREVIEW_W - crop_preview.size[0]) // 2
    composite.paste(crop_preview, (paste_x, crop_y_offset))

    # Bottom label
    cdraw.text(
        (8, crop_y_offset + crop_preview.size[1] + 4),
        f"9:16 crop result (from crop_x={crop_x}){' [TEST FRAME]' if test_frame_generated else ''}",
        font=label_font,
        fill=(180, 180, 180),
    )

    buf = io.BytesIO()
    composite.save(buf, format="PNG")
    label_str = (
        f"Smart Crop Preview | anchor={anchor} | faces={faces_found} | crop_x={crop_x}"
        + (f" | source: {Path(clip_path).name}" if clip_path else " | [test frame]")
    )
    return buf.getvalue(), label_str


# ── PIL-based frame renderer ───────────────────────────────────────────────────

def _pil_font(fontname: str, size: int) -> ImageFont.FreeTypeFont:
    path = PIL_FONTS.get(fontname, PIL_FONTS["Arial Black"])
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _ass_to_rgba(ass_color: str) -> tuple:
    """Convert &HAABBGGRR to (R,G,B,A) tuple."""
    hex_ = ass_color.replace("&H", "").replace("&h", "")
    if len(hex_) < 8:
        return (255, 255, 255, 255)
    a = int(hex_[0:2], 16)
    b = int(hex_[2:4], 16)
    g = int(hex_[4:6], 16)
    r = int(hex_[6:8], 16)
    alpha = 255 - a
    return (r, g, b, alpha)


def _render_frame(channel_name: str, tab: str) -> tuple[bytes, str]:
    """Render a preview frame as PNG bytes.

    For tab='crop', delegates to _render_crop_preview().
    All other tabs render a 540x960 (half of 1080x1920) styled frame.
    """
    if tab == "crop":
        return _render_crop_preview()

    W, H = 540, 960
    cs = get_caption_style(channel_name)
    os_ = get_overlay_style(channel_name)

    hook_text = _strip_emoji(get_hook(channel_name))
    cta_text = _strip_emoji(get_cta(channel_name))

    # Background: blurred gradient to simulate video
    img = Image.new("RGBA", (W, H), (18, 18, 18, 255))
    draw = ImageDraw.Draw(img)

    # Simulated blurred video background (gradient bars)
    for i in range(H):
        t = i / H
        r = int(20 + 30 * t)
        g = int(18 + 20 * t)
        b = int(30 + 40 * t)
        draw.line([(0, i), (W, i)], fill=(r, g, b, 255))

    # Simulated content area (lighter rectangle in center)
    draw.rectangle([60, 120, W-60, H-120], fill=(40, 40, 40, 180))

    # Watermark
    wm_font = _pil_font("Impact", 14)
    wm_text = channel_name.replace("_", " ").upper()
    draw.text((W - 10, H - 10), wm_text, font=wm_font, fill=(255, 255, 255, 100), anchor="rb")

    if tab == "hook":
        # Render hook text (top area)
        font_sz = max(20, os_.get("hook_fontsize", 88) // 2)
        font = _pil_font("Impact", font_sz)
        text = hook_text
        bw = os_.get("borderw", 5)
        # Outline
        for dx in range(-bw, bw+1, max(1, bw//2)):
            for dy in range(-bw, bw+1, max(1, bw//2)):
                if dx or dy:
                    draw.text((W//2 + dx, H//5 + dy), text, font=font, fill=(0,0,0,230), anchor="mm")
        draw.text((W//2, H//5), text, font=font, fill=(255,255,255,255), anchor="mm")
        label = f'Hook: "{hook_text}"'

    elif tab == "cta":
        # Render CTA text (bottom area)
        font_sz = max(14, os_.get("cta_fontsize", 56) // 2)
        font = _pil_font("Impact", font_sz)
        text = cta_text
        bw = os_.get("borderw", 5)
        for dx in range(-bw, bw+1, max(1, bw//2)):
            for dy in range(-bw, bw+1, max(1, bw//2)):
                if dx or dy:
                    draw.text((W//2 + dx, int(H*0.82) + dy), text, font=font, fill=(0,0,0,230), anchor="mm")
        draw.text((W//2, int(H*0.82)), text, font=font, fill=(255,255,255,255), anchor="mm")
        label = f'CTA: "{cta_text}"'

    elif tab == "caption":
        # ── Word-highlight caption demo ──────────────────────────────────────
        # Shows 3 rows, each with a different word highlighted — simulates the
        # TikTok karaoke effect exactly as it appears in the actual ASS render.
        fontname   = cs.get("fontname", "Impact")
        font_sz    = max(16, cs.get("fontsize", 72) // 2)
        font       = _pil_font(fontname, font_sz)
        outline_sz = cs.get("outline_size", 4)
        margin_v   = cs.get("margin_v", 400)
        prim       = _ass_to_rgba(cs.get("primary_color",          "&H00FFFFFF"))
        outl       = _ass_to_rgba(cs.get("outline_color",          "&H00000000"))
        hl         = _ass_to_rgba(cs.get("word_highlight_color",   "&H0000FFFF"))
        back       = _ass_to_rgba(cs.get("back_color",             "&H80000000"))

        # Three 3-word groups to demo
        word_groups = [
            ["This", "clip", "is"],
            ["absolutely",  "INSANE", "bro"],
            ["no", "way", "that"],
        ]

        base_y = int((margin_v / 1920) * H)

        for row_idx, words in enumerate(word_groups):
            active_idx = row_idx % len(words)   # rotate which word is highlighted
            y = base_y + row_idx * (font_sz + 18)

            # Measure total line width to center it
            word_sizes = []
            space_w = int(font_sz * 0.28)
            for w in words:
                bb = draw.textbbox((0, 0), w, font=font)
                word_sizes.append(bb[2] - bb[0])
            total_w = sum(word_sizes) + space_w * (len(words) - 1)
            x = (W - total_w) // 2

            for w_idx, (word, ww) in enumerate(zip(words, word_sizes)):
                color = hl if w_idx == active_idx else prim

                # Optional back box for this word
                if back[3] > 20:
                    pad = 4
                    draw.rectangle(
                        [x - pad, y - pad, x + ww + pad, y + font_sz + pad],
                        fill=(back[0], back[1], back[2], back[3])
                    )

                # Outline
                for dx in range(-outline_sz, outline_sz + 1, max(1, outline_sz // 2)):
                    for dy in range(-outline_sz, outline_sz + 1, max(1, outline_sz // 2)):
                        if dx or dy:
                            draw.text((x + dx, y + dy), word, font=font,
                                      fill=(outl[0], outl[1], outl[2], 200))

                # Word text
                draw.text((x, y), word, font=font,
                          fill=(color[0], color[1], color[2], 255))
                x += ww + space_w

        # Legend
        legend_font = _pil_font("Arial", 13)
        hl_css = f"RGB({hl[0]},{hl[1]},{hl[2]})"
        draw.text((W // 2, base_y + len(word_groups) * (font_sz + 18) + 10),
                  f"highlighted word -> {hl_css}",
                  font=legend_font, fill=(hl[0], hl[1], hl[2], 200), anchor="mt")

        label = (
            f"Caption: {fontname} {cs.get('fontsize')}px | "
            f"outline {outline_sz}px | {cs.get('words_per_line',3)} words/line | "
            f"highlight color shown"
        )

    # Convert to PNG bytes
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue(), label


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML, channels=CHANNELS)


@app.route("/preview")
def preview():
    channel = request.args.get("channel", "arc_highlightz")
    tab = request.args.get("tab", "hook")

    try:
        png_bytes, label = _render_frame(channel, tab)
        img_b64 = base64.b64encode(png_bytes).decode()
        from engine.config.styles import get_style
        style = get_style(channel)
        return jsonify({"image": img_b64, "label": label, "style": style})
    except Exception as e:
        import traceback
        return jsonify({"error": str(e), "trace": traceback.format_exc()}), 500


if __name__ == "__main__":
    import webbrowser, threading
    port = 5050
    print(f"[preview] Starting style preview server at http://localhost:{port}")
    threading.Timer(1.2, lambda: webbrowser.open(f"http://localhost:{port}")).start()
    app.run(host="0.0.0.0", port=port, debug=False)
