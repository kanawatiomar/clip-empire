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

sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template_string, request, jsonify
from PIL import Image, ImageDraw, ImageFont
from engine.config.styles import CHANNEL_STYLE_MAP, STYLE_PRESETS, get_overlay_style, get_caption_style
from engine.config.templates import get_hook, get_cta
from engine.transform.overlay import _strip_emoji
from accounts.channel_definitions import CHANNELS

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
  .preview-panel { padding: 12px 24px; border-right: 1px solid var(--border); }
  .preview-panel h2 { font-size: 13px; color: var(--muted); margin-bottom: 16px; text-transform: uppercase; letter-spacing: 1px; }
  .phone-frame { width: 190px; height: 338px; border: 3px solid #333; border-radius: 18px; overflow: hidden;
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
        <button class="tab" onclick="setTab('crop', this)">Crop Anchor</button>
        <button class="tab" onclick="setTab('creators', this)">Creators</button>
      </div>
      <div class="phone-frame" id="phone-frame">
        <div class="loading" id="loading">Loading...</div>
        <img id="preview-img" style="display:none" src="" alt="preview">
      </div>
      <div id="creator-panel" style="display:none;max-height:420px;overflow-y:auto"></div>
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
    const creatorPanel = document.getElementById('creator-panel');

    // Creators tab — renders a card grid instead of a phone frame
    if (currentTab === 'creators') {
      img.style.display = 'none';
      loading.style.display = 'none';
      document.getElementById('phone-frame').style.display = 'none';
      if (creatorPanel) creatorPanel.style.display = 'block';
      document.getElementById('preview-label').textContent = '';
      fetch(`/creators?channel=${currentChannel}`)
        .then(r => r.json())
        .then(data => {
          if (creatorPanel) creatorPanel.innerHTML = renderCreatorCards(data.creators || []);
          document.getElementById('config-display').innerHTML = '';
        })
        .catch(e => { if (creatorPanel) creatorPanel.textContent = 'Error: ' + e; });
      return;
    }

    if (creatorPanel) creatorPanel.style.display = 'none';
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

  let currentCreator = '';

  function renderCreatorCards(creators) {
    if (!creators.length) return '<p style="color:var(--muted);font-size:13px;padding:8px">No creator profiles for this channel yet.</p>';
    return `<div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:12px;padding:8px 0">` +
      creators.map(c => `
        <div style="background:var(--card);border:1px solid var(--border);border-radius:10px;padding:14px;cursor:pointer"
             onclick="previewCreator('${c.name}', this)"
             title="Click to preview this creator's style">
          <div style="font-weight:700;font-size:14px;margin-bottom:4px">${c.name} <span style="font-size:10px;color:#6c63ff">▶ preview</span></div>
          <div style="font-size:11px;color:#6c63ff;margin-bottom:8px;text-transform:uppercase;letter-spacing:.06em">${(c.content_types||[]).join(' · ')}</div>
          <div style="font-size:11px;color:var(--muted);margin-bottom:6px">✂️ Crop: <b style="color:var(--text)">${c.crop_anchor}</b> &nbsp; 🪝 Hook: <b style="color:var(--text)">${c.hook_style}</b></div>
          ${c.llm_context ? `<div style="font-size:11px;color:#aaa;border-top:1px solid var(--border);padding-top:7px;margin-top:6px;line-height:1.5">${c.llm_context}</div>` : ''}
          ${c.prefer_keywords && c.prefer_keywords.length ? `<div style="margin-top:8px;display:flex;flex-wrap:wrap;gap:4px">${c.prefer_keywords.map(k=>`<span style="font-size:10px;padding:2px 7px;border-radius:20px;background:rgba(0,200,100,.12);color:#00c864;border:1px solid rgba(0,200,100,.2)">${k}</span>`).join('')}</div>` : ''}
          ${c.avoid_keywords && c.avoid_keywords.length ? `<div style="margin-top:4px;display:flex;flex-wrap:wrap;gap:4px">${c.avoid_keywords.map(k=>`<span style="font-size:10px;padding:2px 7px;border-radius:20px;background:rgba(200,50,50,.12);color:#e06060;border:1px solid rgba(200,50,50,.2)">✗ ${k}</span>`).join('')}</div>` : ''}
          ${c.hook_overrides && c.hook_overrides.length ? `<div style="margin-top:8px;border-top:1px solid var(--border);padding-top:7px"><div style="font-size:10px;color:var(--muted);margin-bottom:4px">HOOK OVERRIDES</div>${c.hook_overrides.map(h=>`<div style="font-size:11px;color:#f0c060;font-family:monospace;margin-bottom:2px">"${h}"</div>`).join('')}</div>` : ''}
        </div>`
      ).join('') + '</div>';
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

  function previewCreator(creatorKey, el) {
    currentCreator = creatorKey;
    // Switch to hook frame to show the style
    document.querySelectorAll('.tab').forEach(b => b.classList.remove('active'));
    document.querySelectorAll('.tab')[0].classList.add('active');
    currentTab = 'hook';
    document.getElementById('creator-panel').style.display = 'none';
    document.getElementById('phone-frame').style.display = 'block';
    const img = document.getElementById('preview-img');
    const loading = document.getElementById('loading');
    img.style.display = 'none';
    loading.style.display = 'flex';
    loading.textContent = `Rendering ${creatorKey} style...`;
    const url = `/preview?channel=${currentChannel}&tab=hook&creator=${creatorKey}&t=${Date.now()}`;
    fetch(url).then(r => r.json()).then(data => {
      img.src = 'data:image/png;base64,' + data.image;
      img.style.display = 'block';
      loading.style.display = 'none';
      document.getElementById('preview-label').textContent = `Style: ${creatorKey}`;
      renderConfig(data.style);
    }).catch(e => { loading.textContent = 'Error: ' + e; });
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


def _render_frame(channel_name: str, tab: str, creator: str = "") -> tuple[bytes, str]:
    """Render a 540x960 (half of 1080x1920) preview frame as PNG bytes."""
    W, H = 540, 960
    cs = get_caption_style(channel_name, creator)
    os_ = get_overlay_style(channel_name, creator)

    hook_text = _strip_emoji(get_hook(channel_name, creator=creator))
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
        # ── Word-highlight caption demo with position ruler ──────────────────
        fontname   = cs.get("fontname", "Impact")
        font_sz    = max(14, cs.get("fontsize", 72) // 2)
        font       = _pil_font(fontname, font_sz)
        outline_sz = cs.get("outline_size", 4)
        margin_v   = cs.get("margin_v", 960)
        prim       = _ass_to_rgba(cs.get("primary_color",        "&H00FFFFFF"))
        outl       = _ass_to_rgba(cs.get("outline_color",        "&H00000000"))
        hl         = _ass_to_rgba(cs.get("word_highlight_color", "&H0000FFFF"))
        back       = _ass_to_rgba(cs.get("back_color",           "&H80000000"))

        # Position ruler — horizontal zone lines
        guide_font = _pil_font("Arial", 11)
        for zy, zlabel in [(int(H*0.1),"TOP"), (H//2,"CENTER"), (int(H*0.65),"LOWER"), (int(H*0.83),"BOTTOM")]:
            draw.line([(0, zy), (W, zy)], fill=(55, 55, 75, 200), width=1)
            draw.text((5, zy - 12), zlabel, font=guide_font, fill=(80, 80, 120, 200))

        # Compute caption y position from margin_v
        base_y = int((margin_v / 1920) * H)

        # Arrow pointing to caption position
        draw.line([(10, base_y), (30, base_y)], fill=(100, 200, 100, 220), width=2)
        draw.polygon([(30, base_y-4), (30, base_y+4), (38, base_y)], fill=(100, 200, 100, 220))
        draw.text((42, base_y - 7), f"margin_v={margin_v}px", font=guide_font,
                  fill=(100, 200, 100, 200))

        # Three word-groups, each showing a different word highlighted
        word_groups = [
            ["This", "clip", "is"],
            ["absolutely", "INSANE", "bro"],
            ["no", "way", "that"],
        ]
        for row_idx, words in enumerate(word_groups):
            active_idx = row_idx % len(words)
            y = base_y + row_idx * (font_sz + 12)
            space_w = max(6, int(font_sz * 0.28))
            word_sizes = [draw.textbbox((0,0), w, font=font)[2] for w in words]
            total_w = sum(word_sizes) + space_w * (len(words) - 1)
            x = (W - total_w) // 2
            for w_idx, (word, ww) in enumerate(zip(words, word_sizes)):
                color = hl if w_idx == active_idx else prim
                if back[3] > 20:
                    draw.rectangle([x-3, y-2, x+ww+3, y+font_sz+2],
                                   fill=(back[0], back[1], back[2], back[3]))
                for dx in range(-outline_sz, outline_sz+1, max(1, outline_sz//2)):
                    for dy in range(-outline_sz, outline_sz+1, max(1, outline_sz//2)):
                        if dx or dy:
                            draw.text((x+dx, y+dy), word, font=font,
                                      fill=(outl[0], outl[1], outl[2], 180))
                draw.text((x, y), word, font=font, fill=(color[0], color[1], color[2], 255))
                x += ww + space_w

        hl_label = f"RGB({hl[0]},{hl[1]},{hl[2]})"
        pct = int(margin_v / 1920 * 100)
        label = (f"Caption: {fontname} {cs.get('fontsize')}px | "
                 f"position {pct}% down | highlight {hl_label}")

    elif tab == "crop":
        # ── Crop anchor comparison ────────────────────────────────────────────
        # Draw a simulated 16:9 landscape frame with 3 crop windows:
        # left / center / right — showing what each anchor keeps vs. cuts
        img = Image.new("RGBA", (W, H), (18, 18, 18, 255))
        draw = ImageDraw.Draw(img)

        # Simulated landscape frame (16:9 = 540 wide × 304 tall)
        FRAME_W, FRAME_H = 510, 287
        FRAME_X, FRAME_Y = (W - FRAME_W) // 2, 40

        # Gradient background (simulates video)
        for i in range(FRAME_H):
            t = i / FRAME_H
            draw.line([(FRAME_X, FRAME_Y + i), (FRAME_X + FRAME_W, FRAME_Y + i)],
                      fill=(int(20+50*t), int(18+40*t), int(40+60*t), 255))

        # Simulated webcam bubble (bottom-right corner of landscape)
        cam_r = 28
        cam_center = (FRAME_X + FRAME_W - cam_r - 8, FRAME_Y + FRAME_H - cam_r - 8)
        draw.ellipse([cam_center[0]-cam_r, cam_center[1]-cam_r,
                      cam_center[0]+cam_r, cam_center[1]+cam_r], fill=(80, 130, 200, 220))
        draw.text(cam_center, "CAM", font=_pil_font("Arial", 9), fill=(255,255,255,255), anchor="mm")

        # Simulated gameplay (left side content)
        draw.rectangle([FRAME_X+10, FRAME_Y+10, FRAME_X+200, FRAME_Y+FRAME_H-10],
                       fill=(30, 60, 30, 180))
        draw.text((FRAME_X+105, FRAME_Y+FRAME_H//2), "GAMEPLAY",
                  font=_pil_font("Arial", 10), fill=(100,200,100,255), anchor="mm")

        # Frame border
        draw.rectangle([FRAME_X, FRAME_Y, FRAME_X+FRAME_W, FRAME_Y+FRAME_H],
                       outline=(80,80,80,255), width=2)

        # 9:16 crop window width in landscape coordinates
        # 9:16 aspect at FRAME_H height → crop_w = FRAME_H * 9/16
        CROP_W = int(FRAME_H * 9 / 16)  # ~162px at this scale

        anchors = [
            ("left",   FRAME_X,                              (100, 220, 100),  "LEFT\nKeeps left action"),
            ("center", FRAME_X + (FRAME_W - CROP_W)//2,     (220, 220, 100),  "CENTER\nStandard crop"),
            ("right",  FRAME_X + FRAME_W - CROP_W,          (220, 100, 100),  "RIGHT\nKeeps cam side"),
        ]

        # Draw crop windows on the landscape frame
        for anchor_name, crop_x, color, _ in anchors:
            draw.rectangle([crop_x, FRAME_Y, crop_x + CROP_W, FRAME_Y + FRAME_H],
                           outline=color + (255,), width=3)

        # Show source config for this channel
        from engine.config.sources import SOURCES
        ch_sources = SOURCES.get(channel_name, [])
        anchor_map = {s.get("url","")[-30:]: s.get("crop_anchor","center") for s in ch_sources}

        # Three mini previews below showing what each crop keeps
        MINI_H = int((H - FRAME_Y - FRAME_H - 100) // 3)
        MINI_W = int(MINI_H * 9 / 16)
        BASE_Y = FRAME_Y + FRAME_H + 20

        small_font = _pil_font("Arial", 12)
        label_font = _pil_font("Impact", 14)

        for idx, (anchor_name, crop_x, color, desc) in enumerate(anchors):
            mx = (W - MINI_W * 3 - 20) // 2 + idx * (MINI_W + 10)
            my = BASE_Y

            # Crop the simulated frame to this window
            src_x0 = crop_x - FRAME_X
            src_x1 = src_x0 + CROP_W
            region = img.crop([FRAME_X + src_x0, FRAME_Y,
                               FRAME_X + src_x1, FRAME_Y + FRAME_H])
            region = region.resize((MINI_W, MINI_H), Image.LANCZOS)
            img.paste(region, (mx, my))

            # Border
            mini_draw = ImageDraw.Draw(img)
            mini_draw.rectangle([mx, my, mx+MINI_W, my+MINI_H], outline=color+(255,), width=2)

            # Label
            mini_draw.text((mx + MINI_W//2, my + MINI_H + 6), anchor_name.upper(),
                           font=label_font, fill=color+(255,), anchor="mt")

        # Source config legend
        y_leg = BASE_Y + MINI_H + 36
        legend_font = _pil_font("Arial", 11)
        draw.text((W//2, y_leg), "Source anchor config:", font=legend_font,
                  fill=(150,150,150,255), anchor="mt")
        for si, src in enumerate(ch_sources[:4]):
            url_short = src.get("url","?").split("/")[-1][:28] or src.get("url","")[-28:]
            anchor_val = src.get("crop_anchor","center")
            col = {"left":(100,220,100),"right":(220,100,100),"center":(220,220,100)}.get(anchor_val,(200,200,200))
            draw.text((W//2, y_leg + 16 + si*14),
                      f"{url_short}  →  {anchor_val}",
                      font=legend_font, fill=col+(255,), anchor="mt")

        label = f"Crop anchors for {channel_name} — red box = 9:16 window"

    # Convert to PNG bytes
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="PNG")
    return buf.getvalue(), label


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template_string(HTML, channels=CHANNELS)


@app.route("/creators")
def creators():
    channel = request.args.get("channel", "arc_highlightz")
    try:
        from engine.config.creator_profiles import CREATOR_PROFILES
        result = []
        for creator_key, profile in CREATOR_PROFILES.items():
            if profile.get("channel") == channel:
                result.append({
                    "name": creator_key.replace("wallstreetmillennial", "WallStMillennial"),
                    "crop_anchor": profile.get("crop_anchor", "center"),
                    "content_types": profile.get("content_types", []),
                    "hook_style": profile.get("hook_style", "hype"),
                    "min_views": profile.get("min_views", 0),
                    "llm_context": profile.get("llm_context", ""),
                    "prefer_keywords": profile.get("prefer_keywords", []),
                    "avoid_keywords": profile.get("avoid_keywords", []),
                    "hook_overrides": profile.get("hook_overrides", []),
                })
        return jsonify({"channel": channel, "creators": result})
    except Exception as e:
        return jsonify({"error": str(e), "creators": []}), 500


@app.route("/preview")
def preview():
    channel = request.args.get("channel", "arc_highlightz")
    tab = request.args.get("tab", "hook")
    creator = request.args.get("creator", "")

    try:
        png_bytes, label = _render_frame(channel, tab, creator=creator)
        img_b64 = base64.b64encode(png_bytes).decode()
        from engine.config.styles import get_style
        style = get_style(channel, creator)
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
