"""Per-channel visual style configuration.

Each channel maps to a style preset that controls:
  - Caption (ASS subtitles): font, size, colors, outline, positioning
  - Overlay (hook/CTA drawtext): font, size, colors, effects

ASS color format: &HAABBGGRR  (alpha=00 fully opaque, FF fully transparent)
"""

# ── Font paths (absolute, Windows) ───────────────────────────────────────────
FONT_IMPACT   = r"C\:/Windows/Fonts/Impact.ttf"
FONT_ARIAL_BK = r"C\:/Windows/Fonts/arialbd.ttf"   # Arial Bold
FONT_ARIAL    = r"C\:/Windows/Fonts/arial.ttf"

# ── Style presets ─────────────────────────────────────────────────────────────

STYLE_PRESETS = {

    # ── GAMING — bold, loud, fire energy ─────────────────────────────────────
    "gaming": {
        "caption": {
            "fontname":      "Impact",
            "fontsize":      80,
            "primary_color": "&H00FFFFFF",   # white
            "outline_color": "&H00000000",   # black
            "back_color":    "&H00000000",   # no box
            "bold":          0,
            "outline_size":  5,
            "shadow":        3,
            "margin_v":      1300,           # lower center — gameplay action at top
            "words_per_line": 3,
            "word_highlight_color": "&H001AFFE4",  # neon yellow-green
        },
        "overlay": {
            "fontfile":       FONT_IMPACT,
            "hook_fontsize":  96,
            "cta_fontsize":   60,
            "fontcolor":      "white",
            "borderw":        6,
            "bordercolor":    "black@0.95",
            "shadowx":        4,
            "shadowy":        4,
            "shadowcolor":    "black@0.8",
            "hook_y":         "h/5",         # higher up — more dramatic
        },
    },

    # ── FINANCE — clean, credible, semi-transparent box ───────────────────────
    "finance": {
        "caption": {
            "fontname":      "Arial Black",
            "fontsize":      72,
            "primary_color": "&H00FFFFFF",
            "outline_color": "&H00000000",
            "back_color":    "&H99000000",   # dark semi-transparent box
            "bold":          -1,
            "outline_size":  3,
            "shadow":        0,
            "margin_v":      960,            # center — talking head clips
            "words_per_line": 4,
            "word_highlight_color": "&H0000D4FF",  # gold/amber
        },
        "overlay": {
            "fontfile":       FONT_ARIAL_BK,
            "hook_fontsize":  82,
            "cta_fontsize":   52,
            "fontcolor":      "white",
            "borderw":        4,
            "bordercolor":    "black@0.9",
            "shadowx":        2,
            "shadowy":        2,
            "shadowcolor":    "black@0.7",
            "hook_y":         "h/4",
        },
    },

    # ── BUSINESS — sharp, motivational, slight warmth ────────────────────────
    "business": {
        "caption": {
            "fontname":      "Arial Black",
            "fontsize":      74,
            "primary_color": "&H00FFFFFF",
            "outline_color": "&H00000000",
            "back_color":    "&H80000000",
            "bold":          -1,
            "outline_size":  4,
            "shadow":        2,
            "margin_v":      960,            # center — talking head
            "words_per_line": 4,
            "word_highlight_color": "&H0000AAFF",  # orange-amber
        },
        "overlay": {
            "fontfile":       FONT_IMPACT,
            "hook_fontsize":  88,
            "cta_fontsize":   56,
            "fontcolor":      "white",
            "borderw":        5,
            "bordercolor":    "black@0.9",
            "shadowx":        3,
            "shadowy":        3,
            "shadowcolor":    "black@0.75",
            "hook_y":         "h/4",
        },
    },

    # ── TECH/AI — futuristic, clean, cyan accent ──────────────────────────────
    "tech": {
        "caption": {
            "fontname":      "Arial Black",
            "fontsize":      70,
            "primary_color": "&H00FFFFFF",
            "outline_color": "&H00000000",
            "back_color":    "&H99000000",
            "bold":          -1,
            "outline_size":  3,
            "shadow":        1,
            "margin_v":      960,            # center — demo/screen content
            "words_per_line": 4,
            "word_highlight_color": "&H00FFE400",  # cyan
        },
        "overlay": {
            "fontfile":       FONT_ARIAL_BK,
            "hook_fontsize":  80,
            "cta_fontsize":   52,
            "fontcolor":      "white",
            "borderw":        4,
            "bordercolor":    "black@0.9",
            "shadowx":        2,
            "shadowy":        2,
            "shadowcolor":    "black@0.6",
            "hook_y":         "h/4",
        },
    },

    # ── FITNESS — explosive, yellow pops ─────────────────────────────────────
    "fitness": {
        "caption": {
            "fontname":      "Impact",
            "fontsize":      82,
            "primary_color": "&H00FFFFFF",
            "outline_color": "&H00000000",
            "back_color":    "&H00000000",
            "bold":          0,
            "outline_size":  5,
            "shadow":        3,
            "margin_v":      1200,           # lower center — gym action at top
            "words_per_line": 3,
            "word_highlight_color": "&H0000FFFF",  # yellow
        },
        "overlay": {
            "fontfile":       FONT_IMPACT,
            "hook_fontsize":  92,
            "cta_fontsize":   58,
            "fontcolor":      "white",
            "borderw":        6,
            "bordercolor":    "black@0.95",
            "shadowx":        4,
            "shadowy":        4,
            "shadowcolor":    "black@0.8",
            "hook_y":         "h/5",
        },
    },

    # ── FOOD — warm, inviting, orange tones ───────────────────────────────────
    "food": {
        "caption": {
            "fontname":      "Arial Black",
            "fontsize":      72,
            "primary_color": "&H00FFFFFF",
            "outline_color": "&H00000000",
            "back_color":    "&H80000000",
            "bold":          -1,
            "outline_size":  4,
            "shadow":        2,
            "margin_v":      1100,           # lower center — food/hands visible at center
            "words_per_line": 4,
            "word_highlight_color": "&H000066FF",  # warm orange
        },
        "overlay": {
            "fontfile":       FONT_IMPACT,
            "hook_fontsize":  86,
            "cta_fontsize":   54,
            "fontcolor":      "white",
            "borderw":        5,
            "bordercolor":    "black@0.9",
            "shadowx":        3,
            "shadowy":        3,
            "shadowcolor":    "black@0.7",
            "hook_y":         "h/4",
        },
    },

    # ── TRUE CRIME — dark, moody, red ─────────────────────────────────────────
    "truecrime": {
        "caption": {
            "fontname":      "Arial Black",
            "fontsize":      70,
            "primary_color": "&H00FFFFFF",
            "outline_color": "&H000000AA",   # dark red outline
            "back_color":    "&HCC000000",   # heavy dark box
            "bold":          -1,
            "outline_size":  3,
            "shadow":        1,
            "margin_v":      1400,           # lower third — classic documentary style
            "words_per_line": 4,
            "word_highlight_color": "&H002222CC",  # red
        },
        "overlay": {
            "fontfile":       FONT_ARIAL_BK,
            "hook_fontsize":  80,
            "cta_fontsize":   52,
            "fontcolor":      "white",
            "borderw":        4,
            "bordercolor":    "black@0.95",
            "shadowx":        3,
            "shadowy":        3,
            "shadowcolor":    "black@0.9",
            "hook_y":         "h/4",
        },
    },

    # ── EXPERIMENTAL — colorful, playful ─────────────────────────────────────
    "experimental": {
        "caption": {
            "fontname":      "Arial Black",
            "fontsize":      74,
            "primary_color": "&H00FFFFFF",
            "outline_color": "&H00000000",
            "back_color":    "&H80000000",
            "bold":          -1,
            "outline_size":  4,
            "shadow":        2,
            "margin_v":      1050,           # slightly below center
            "words_per_line": 4,
            "word_highlight_color": "&H00FF00FF",  # magenta
        },
        "overlay": {
            "fontfile":       FONT_IMPACT,
            "hook_fontsize":  88,
            "cta_fontsize":   56,
            "fontcolor":      "white",
            "borderw":        5,
            "bordercolor":    "black@0.9",
            "shadowx":        3,
            "shadowy":        3,
            "shadowcolor":    "black@0.75",
            "hook_y":         "h/4",
        },
    },
}

# ── Channel → style mapping ───────────────────────────────────────────────────
CHANNEL_STYLE_MAP = {
    "arc_highlightz":   "gaming",
    "fomo_highlights":  "gaming",
    "market_meltdowns": "finance",
    "crypto_confessions": "finance",
    "rich_or_ruined":   "finance",
    "startup_graveyard": "business",
    "self_made_clips":  "business",
    "ai_did_what":      "tech",
    "gym_moments":      "fitness",
    "kitchen_chaos":    "food",
    "cases_unsolved":   "truecrime",
    "unfiltered_clips": "experimental",
    "viral_recaps":     "experimental",   # comedy/variety — bold but loose
}


def get_style(channel_name: str, creator: str = "") -> dict:
    """Return style dict — creator-specific first, then channel fallback."""
    if creator:
        try:
            from engine.config.creator_profiles import get_creator_style
            creator_style = get_creator_style(creator)
            if creator_style:
                return creator_style
        except Exception:
            pass
    preset_key = CHANNEL_STYLE_MAP.get(channel_name, "experimental")
    return STYLE_PRESETS.get(preset_key, STYLE_PRESETS["experimental"])


def get_caption_style(channel_name: str, creator: str = "") -> dict:
    return get_style(channel_name, creator)["caption"]


def get_overlay_style(channel_name: str, creator: str = "") -> dict:
    return get_style(channel_name, creator)["overlay"]
