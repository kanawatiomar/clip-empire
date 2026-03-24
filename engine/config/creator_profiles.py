"""Creator Profiles — per-creator configuration for the engine.

Each creator has unique characteristics that influence:
- Crop anchor (webcam position in frame)
- Style (caption font/color, overlay font/size) — AUTHORITATIVE over channel style
- Content type personality
- Hook text and LLM title prompts
- Clip scoring (prefer/avoid keywords)

style_preset:    which base preset from styles.py to inherit from
style_overrides: fine-tuned overrides on top of the preset
  caption keys: fontname, fontsize, primary_color, outline_color, back_color,
                outline_size, shadow, margin_v, words_per_line, word_highlight_color
  overlay keys: hook_fontsize, cta_fontsize, fontcolor, borderw, bordercolor, hook_y
"""

from __future__ import annotations
from typing import Optional

CREATOR_PROFILES: dict[str, dict] = {

    # ── ARC HIGHLIGHTZ CREATORS ───────────────────────────────────────────────

    "tfue": {
        "display_name": "Tfue",
        "channel": "arc_highlightz",
        "crop_anchor": "right",
        "content_types": ["clutch", "rage", "skill"],
        "hook_style": "hype",
        "min_views": 2000,
        "llm_context": "Tfue is a legendary Fortnite/FPS player known for insane mechanical skill, clutch plays, and competitive moments. Titles should emphasize skill and impossibility.",
        "prefer_keywords": ["clutch", "insane", "cracked", "1v5", "rage", "no way", "hacking"],
        "avoid_keywords": ["irl", "just chatting", "podcast", "cooking", "react"],
        "hook_overrides": [
            "TFUE IS BUILT DIFFERENT",
            "NOBODY MOVES LIKE THIS",
            "CRACKED OR HACKING?",
            "THIS SHOULDN'T BE POSSIBLE",
            "TFUE SAID NOTHING AND DID EVERYTHING",
            "THE LOBBY HAD NO CHANCE",
            "ZERO HESITATION 💀",
            "TFUE WOKE UP AND CHOSE VIOLENCE",
            "TELL ME YOU'RE CRACKED WITHOUT TELLING ME",
            "TFUE COOKED",
            "I HAVE NO WORDS 😤",
            "BEST TFUE CLIP IN MONTHS",
            "THE AUDACITY 💀",
            "HOW IS THIS EVEN LEGAL",
            "CHAT FROZE WATCHING THIS",
        ],
        # Style: loud gaming energy, neon green highlights, Impact
        "style_preset": "gaming",
        "style_overrides": {
            "caption": {
                "word_highlight_color": "&H001AFFE4",  # neon green
                "margin_v": 1350,
                "words_per_line": 3,
            },
            "overlay": {
                "hook_fontsize": 100,
                "hook_y": "h/6",
            },
        },
    },

    "cloakzy": {
        "display_name": "Cloakzy",
        "channel": "arc_highlightz",
        "crop_anchor": "left",
        "content_types": ["clutch", "funny", "rage"],
        "hook_style": "reaction",
        "min_views": 2000,
        "llm_context": "Cloakzy is a chill Fortnite streamer known for funny moments, clutch plays, and genuine reactions. Titles should feel authentic and relatable.",
        "prefer_keywords": ["clutch", "funny", "insane", "rage", "lmao", "chat", "no way"],
        "avoid_keywords": ["irl", "podcast", "just chatting"],
        "hook_overrides": [
            "CLOAKZY DIDN'T EXPECT THAT",
            "CHAT LOST IT",
            "HOW DID HE DO THAT",
            "CLOAKZY COOKED 🎮",
            "NOT EVEN CLOSE",
            "THE LOBBY WAS NOT READY",
            "CLOAKZY SAID WATCH THIS 💀",
            "CHAT WAS GOING INSANE",
            "RARE CLOAKZY MOMENT",
            "ZERO THOUGHT. PERFECT EXECUTION.",
            "I WATCHED THIS 5 TIMES",
            "CLUTCH OR DELETE — HE CLUTCHED",
            "THIS CLIP GOT CLIPPED FOR A REASON",
        ],
        # Style: gaming but slightly softer — purple/blue accent
        "style_preset": "gaming",
        "style_overrides": {
            "caption": {
                "word_highlight_color": "&H00FF8800",  # blue-purple
                "margin_v": 1300,
                "words_per_line": 3,
            },
            "overlay": {
                "hook_fontsize": 92,
                "hook_y": "h/5",
            },
        },
    },

    "shinyatheninja": {
        "display_name": "Shinya",
        "channel": "arc_highlightz",
        "crop_anchor": "left",
        "content_types": ["clutch", "skill", "funny"],
        "hook_style": "hype",
        "min_views": 500,
        "llm_context": "ShinyaTheNinja is a skilled FPS/Warzone streamer known for insane clips. Keep titles short and punchy.",
        "prefer_keywords": ["insane", "clutch", "no way", "cracked", "clip"],
        "avoid_keywords": ["irl", "podcast", "just chatting"],
        "hook_overrides": [
            "SHINYA REALLY JUST DID THAT",
            "SHINYA COOKED 🎮",
            "HOW DID SHINYA DO THAT",
            "SHINYA SAID WATCH THIS",
            "CHAT LOST IT",
            "NOT EVEN CLOSE",
            "ZERO THOUGHT. PERFECT EXECUTION.",
            "I WATCHED THIS 5 TIMES",
        ],
        "style_preset": "gaming",
        "style_overrides": {
            "caption": {
                "word_highlight_color": "&H0000E5FF",
                "margin_v": 1300,
                "words_per_line": 3,
            },
            "overlay": {
                "hook_fontsize": 92,
                "hook_y": "h/6",
            },
        },
    },

    "myth": {
        "display_name": "Myth",
        "channel": "arc_highlightz",
        "crop_anchor": "left",
        "content_types": ["clutch", "skill", "funny"],
        "hook_style": "hype",
        "min_views": 500,
        "llm_context": "Myth is a popular Fortnite streamer known for building skills and clutch moments.",
        "prefer_keywords": ["insane", "clutch", "no way", "build", "myth"],
        "avoid_keywords": ["irl", "podcast", "just chatting"],
        "hook_overrides": [
            "MYTH REALLY JUST DID THAT",
            "MYTH COOKED 🎮",
            "HOW DID MYTH DO THAT",
            "MYTH SAID WATCH THIS",
        ],
        "style_preset": "gaming",
        "style_overrides": {
            "caption": {"word_highlight_color": "&H0000E5FF", "margin_v": 1300, "words_per_line": 3},
            "overlay": {"hook_fontsize": 92, "hook_y": "h/6"},
        },
    },

    "bugha": {
        "display_name": "Bugha",
        "channel": "arc_highlightz",
        "crop_anchor": "right",
        "content_types": ["clutch", "skill"],
        "hook_style": "hype",
        "min_views": 500,
        "llm_context": "Bugha is the Fortnite World Cup champion. Known for insane competitive plays.",
        "prefer_keywords": ["insane", "clutch", "no way", "competitive", "bugha"],
        "avoid_keywords": ["irl", "podcast", "just chatting"],
        "hook_overrides": [
            "BUGHA REALLY JUST DID THAT",
            "BUGHA COOKED 🎮",
            "HOW DID BUGHA DO THAT",
            "THE WORLD CHAMP SAID WATCH THIS",
        ],
        "style_preset": "gaming",
        "style_overrides": {
            "caption": {"word_highlight_color": "&H001AFFE4", "margin_v": 1300, "words_per_line": 3},
            "overlay": {"hook_fontsize": 92, "hook_y": "h/6"},
        },
    },

    # ── FOMO HIGHLIGHTS CREATORS ──────────────────────────────────────────────

    "shroud": {
        "display_name": "Shroud",
        "channel": "fomo_highlights",
        "crop_anchor": "right",
        "content_types": ["skill", "clutch", "reaction"],
        "hook_style": "statement",
        "min_views": 2000,
        "llm_context": "Shroud is the most mechanically skilled FPS player on Twitch. Known as 'the human aimbot'. Titles should emphasize impossible aim, godlike skill, and casual mastery.",
        "prefer_keywords": ["aim", "clip", "insane", "cracked", "no way", "god", "shroud"],
        "avoid_keywords": ["irl", "podcast", "just chatting", "react", "politics"],
        "hook_overrides": [
            "THE HUMAN AIMBOT STRIKES AGAIN",
            "SHROUD MAKES IT LOOK EASY",
            "THIS AIM IS ILLEGAL",
            "NOBODY SHOOTS LIKE SHROUD",
        ],
        # Style: clean pro-gamer — white/ice blue, less aggressive than Tfue
        "style_preset": "gaming",
        "style_overrides": {
            "caption": {
                "word_highlight_color": "&H00FFE066",  # ice blue
                "outline_size": 4,
                "margin_v": 1300,
                "words_per_line": 3,
            },
            "overlay": {
                "hook_fontsize": 90,
                "hook_y": "h/5",
            },
        },
    },

    "nickmercs": {
        "display_name": "NICKMERCS",
        "channel": "fomo_highlights",
        "crop_anchor": "left",
        "content_types": ["clutch", "rage", "hype"],
        "hook_style": "hype",
        "min_views": 2000,
        "llm_context": "NICKMERCS is a high-energy Warzone/Fortnite streamer known for hype moments, clutch plays, and intense reactions. Very competitive, emotional. Titles should be high energy.",
        "prefer_keywords": ["clutch", "insane", "hype", "let's go", "rage", "w", "squad"],
        "avoid_keywords": ["irl", "politics", "just chatting"],
        "hook_overrides": [
            "MFAM WENT CRAZY",
            "NICK DIDN'T MISS",
            "THAT'S WHY HE'S BUILT",
        ],
        # Style: high-energy orange (NICKMERCS brand color)
        "style_preset": "gaming",
        "style_overrides": {
            "caption": {
                "word_highlight_color": "&H000055FF",  # orange
                "margin_v": 1400,
                "words_per_line": 3,
            },
            "overlay": {
                "hook_fontsize": 104,
                "hook_y": "h/6",
            },
        },
    },

    "timthetatman": {
        "display_name": "TimTheTatman",
        "channel": "fomo_highlights",
        "crop_anchor": "right",
        "content_types": ["funny", "rage", "clutch"],
        "hook_style": "reaction",
        "min_views": 2000,
        "llm_context": "TimTheTatman is a personality-driven streamer known for funny moments, wholesome rage, and surprising clutches despite joking about being bad. Relatable underdog energy.",
        "prefer_keywords": ["funny", "rage", "clutch", "actually", "no way", "lmao", "win"],
        "avoid_keywords": ["irl", "politics"],
        "hook_overrides": [
            "TIM ACTUALLY DID IT",
            "NOBODY SAW THIS COMING",
            "THE UNDERDOG CLUTCH",
        ],
        # Style: fun blue accent, slightly larger font for personality
        "style_preset": "gaming",
        "style_overrides": {
            "caption": {
                "word_highlight_color": "&H00FF6600",  # sky blue
                "margin_v": 1250,
                "words_per_line": 4,
            },
            "overlay": {
                "hook_fontsize": 88,
                "hook_y": "h/5",
            },
        },
    },

    # ── VIRAL RECAPS CREATORS ─────────────────────────────────────────────────

    "moistcr1tikal": {
        "display_name": "Moistcr1tikal",
        "channel": "viral_recaps",
        "crop_anchor": "center",
        "content_types": ["funny", "reaction", "commentary"],
        "hook_style": "question",
        "min_views": 3000,
        "llm_context": "Moistcr1tikal (penguinz0) is a deadpan comedian streamer. Content is reactions, commentary, and absurdist humor. Very dry wit. Titles should feel surprising or absurd.",
        "prefer_keywords": ["funny", "insane", "wild", "actually", "what", "crazy", "lmao"],
        "avoid_keywords": ["gaming", "irl"],
        "hook_overrides": [
            "CHARLIE SAID WHAT?",
            "THIS IS ACTUALLY WILD",
            "HE REALLY DID THAT",
            "WAIT WHAT",
        ],
        # Style: deadpan — dark box, clean white, no impact font
        "style_preset": "experimental",
        "style_overrides": {
            "caption": {
                "fontname": "Arial Black",
                "fontsize": 72,
                "back_color": "&HAA000000",  # heavy dark box
                "outline_size": 2,
                "margin_v": 1000,
                "words_per_line": 5,
                "word_highlight_color": "&H00FFFFFF",  # plain white
            },
            "overlay": {
                "hook_fontsize": 80,
                "hook_y": "h/4",
            },
        },
    },

    "hasanabi": {
        "display_name": "HasanAbi",
        "channel": "viral_recaps",
        "crop_anchor": "right",
        "content_types": ["reaction", "funny", "rage"],
        "hook_style": "reaction",
        "min_views": 3000,
        "llm_context": "HasanAbi is a political commentary and reaction streamer. Content is hot takes, funny reactions, and passionate moments. Titles should feel opinionated or surprising.",
        "prefer_keywords": ["reaction", "insane", "actually", "wild", "crazy", "takes"],
        "avoid_keywords": [],
        "hook_overrides": [
            "HASAN COULDN'T BELIEVE IT",
            "THIS REACTION IS EVERYTHING",
            "HE HAD NO WORDS",
        ],
        # Style: bold reaction — red accent, news-commentary feel
        "style_preset": "experimental",
        "style_overrides": {
            "caption": {
                "fontname": "Arial Black",
                "back_color": "&H88000000",
                "word_highlight_color": "&H002222EE",  # red
                "margin_v": 950,
                "words_per_line": 4,
            },
            "overlay": {
                "hook_fontsize": 84,
                "hook_y": "h/4",
            },
        },
    },

    "ludwig": {
        "display_name": "Ludwig",
        "channel": "viral_recaps",
        "crop_anchor": "center",
        "content_types": ["funny", "reaction", "clutch"],
        "hook_style": "question",
        "min_views": 2000,
        "llm_context": "Ludwig is a variety streamer known for funny moments, game show formats, and genuinely surprising reactions. Playful, charismatic energy.",
        "prefer_keywords": ["funny", "insane", "actually", "no way", "wild", "lmao"],
        "avoid_keywords": [],
        "hook_overrides": [
            "LUDWIG HAD NO IDEA",
            "EVEN HE DIDN'T EXPECT THIS",
            "THIS GOT OUT OF HAND",
        ],
        # Style: playful yellow, clean
        "style_preset": "experimental",
        "style_overrides": {
            "caption": {
                "fontname": "Arial Black",
                "back_color": "&H88000000",
                "word_highlight_color": "&H0000EEFF",  # yellow
                "margin_v": 1000,
                "words_per_line": 4,
            },
            "overlay": {
                "hook_fontsize": 82,
                "hook_y": "h/4",
            },
        },
    },

    # ── MARKET MELTDOWNS CREATORS ─────────────────────────────────────────────

    "patrickboyle": {
        "display_name": "Patrick Boyle",
        "channel": "market_meltdowns",
        "crop_anchor": "top",
        "content_types": ["educational", "reaction", "funny"],
        "hook_style": "statement",
        "min_views": 0,
        "llm_context": "Patrick Boyle is a dry-witted British hedge fund manager who explains finance with deadpan humor. Best moments are when he reacts to absurd market events or exposes financial nonsense. Titles should be understated but intriguing.",
        "prefer_keywords": ["crash", "collapse", "fraud", "exposed", "insane", "ridiculous", "bubble", "bankrupt"],
        "avoid_keywords": ["tutorial", "how to", "basics"],
        "hook_overrides": [
            "THIS ACTUALLY HAPPENED",
            "THE NUMBERS DON'T LIE",
            "HE SAID WHAT HE SAID",
        ],
        # Style: clean understated finance — Arial Black, dark semi-transparent box, amber highlight
        "style_preset": "finance",
        "style_overrides": {
            "caption": {
                "margin_v": 900,
                "words_per_line": 5,
                "word_highlight_color": "&H0000AAFF",  # amber
                "outline_size": 2,
            },
            "overlay": {
                "hook_fontsize": 78,
                "hook_y": "h/4",
            },
        },
    },

    "wallstreetmillennial": {
        "display_name": "WallSt Millennial",
        "channel": "market_meltdowns",
        "crop_anchor": "top",
        "content_types": ["educational", "reaction"],
        "hook_style": "question",
        "min_views": 0,
        "llm_context": "Wall Street Millennial makes documentary-style explainers about corporate collapses, scams, and market events. Titles should be curiosity-driven and reference the company or event by name.",
        "prefer_keywords": ["collapse", "bankrupt", "fraud", "scam", "billion", "lost", "failed", "disaster"],
        "avoid_keywords": ["investing basics", "how to invest"],
        "hook_overrides": [
            "HOW DID THIS HAPPEN",
            "BILLIONS GONE",
            "THE REAL STORY",
        ],
        # Style: documentary — clean white, minimal, dark box
        "style_preset": "finance",
        "style_overrides": {
            "caption": {
                "margin_v": 850,
                "words_per_line": 5,
                "word_highlight_color": "&H00FFFFFF",  # plain white (very clean)
                "outline_size": 3,
            },
            "overlay": {
                "hook_fontsize": 80,
                "hook_y": "h/4",
            },
        },
    },

    "coffeezilla": {
        "display_name": "Coffeezilla",
        "channel": "market_meltdowns",
        "crop_anchor": "top",
        "content_types": ["reaction", "educational", "funny"],
        "hook_style": "statement",
        "min_views": 0,
        "llm_context": "Coffeezilla exposes internet scams, crypto frauds, and fake gurus with investigative journalism style. His best moments are dramatic reveals and calling people out. Titles should feel like receipts being dropped.",
        "prefer_keywords": ["scam", "fraud", "exposed", "fake", "caught", "lie", "rug pull", "millions"],
        "avoid_keywords": [],
        "hook_overrides": [
            "HE GOT CAUGHT",
            "THE RECEIPTS ARE HERE",
            "THEY REALLY THOUGHT",
            "THIS IS A SCAM",
        ],
        # Style: investigative — darker, red accent, dramatic
        "style_preset": "finance",
        "style_overrides": {
            "caption": {
                "back_color": "&HBB000000",  # very dark box
                "word_highlight_color": "&H002222DD",  # red
                "margin_v": 950,
                "words_per_line": 4,
                "outline_size": 3,
            },
            "overlay": {
                "hook_fontsize": 86,
                "hook_y": "h/5",
                "bordercolor": "black@1.0",
            },
        },
    },

    "rareliquid": {
        "display_name": "Rare Liquid",
        "channel": "market_meltdowns",
        "crop_anchor": "top",
        "content_types": ["educational", "reaction"],
        "hook_style": "question",
        "min_views": 0,
        "llm_context": "Rare Liquid covers stock market events, investing, and financial news in a direct, no-BS style. Titles should be punchy and reference specific numbers or events.",
        "prefer_keywords": ["crash", "pump", "dump", "market", "stocks", "billion", "record"],
        "avoid_keywords": [],
        "hook_overrides": [
            "THE MARKET IS WILD",
            "THIS CHANGED EVERYTHING",
        ],
        # Style: punchy finance — slightly larger, gold accent
        "style_preset": "finance",
        "style_overrides": {
            "caption": {
                "word_highlight_color": "&H0000CCFF",  # gold
                "margin_v": 900,
                "words_per_line": 4,
            },
            "overlay": {
                "hook_fontsize": 84,
                "hook_y": "h/4",
            },
        },
    },

    "plainbagel": {
        "display_name": "The Plain Bagel",
        "channel": "market_meltdowns",
        "crop_anchor": "top",
        "content_types": ["educational", "funny"],
        "hook_style": "question",
        "min_views": 0,
        "llm_context": "The Plain Bagel explains financial concepts and news in a calm, accessible way with occasional dry humor. Titles should be approachable but highlight the most surprising or counterintuitive point.",
        "prefer_keywords": ["actually", "truth", "mistake", "wrong", "surprising", "real"],
        "avoid_keywords": [],
        "hook_overrides": [],
        # Style: clean minimal finance
        "style_preset": "finance",
        "style_overrides": {
            "caption": {
                "word_highlight_color": "&H0000D4FF",  # soft gold
                "margin_v": 880,
                "words_per_line": 5,
                "outline_size": 2,
            },
            "overlay": {
                "hook_fontsize": 76,
                "hook_y": "h/4",
            },
        },
    },
}


def get_profile(creator: str) -> dict:
    """Return creator profile by username (case-insensitive). Returns empty dict if unknown."""
    return CREATOR_PROFILES.get(creator.lower(), {})


def get_crop_anchor(creator: str, fallback: str = "center") -> str:
    """Get the crop anchor for a creator."""
    return get_profile(creator).get("crop_anchor", fallback)


def get_hook_overrides(creator: str) -> list[str]:
    """Get creator-specific hook text options."""
    return get_profile(creator).get("hook_overrides", [])


def get_llm_context(creator: str) -> str:
    """Get the LLM context hint for title generation."""
    return get_profile(creator).get("llm_context", "")


def get_content_types(creator: str) -> list[str]:
    """Get ordered list of content types this creator is known for."""
    return get_profile(creator).get("content_types", ["clutch"])


def get_creator_style(creator: str) -> dict | None:
    """Return the full merged style dict for a creator (preset + overrides).
    Returns None if no profile found — caller should fall back to channel style.
    """
    import copy
    from engine.config.styles import STYLE_PRESETS

    profile = get_profile(creator)
    if not profile:
        return None

    preset_key = profile.get("style_preset", "gaming")
    base = copy.deepcopy(STYLE_PRESETS.get(preset_key, STYLE_PRESETS["gaming"]))

    overrides = profile.get("style_overrides", {})
    for section in ("caption", "overlay"):
        if section in overrides:
            base[section].update(overrides[section])

    return base
