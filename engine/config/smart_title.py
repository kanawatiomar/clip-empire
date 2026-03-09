"""smart_title.py - LLM-powered title generation + clip quality scoring.

For Twitch clips we don't have audio transcripts, so we:
1. Score clips on hype keywords in the clip TITLE (from the Twitch clip metadata)
2. Generate curiosity-bait YouTube titles via GPT-4o-mini
3. Filter out boring/low-quality clips before rendering

Adapted from the Arc Highlightz smart_scorer.py.
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
from pathlib import Path
from typing import Optional

logger = logging.getLogger("clip_empire.smart_title")

# ── HYPE SCORING ─────────────────────────────────────────────────────────────
# Keywords in Twitch clip titles that indicate high entertainment value.
# Score boosts sum up; cap at 1.0.

HYPE_KEYWORDS: dict[str, float] = {
    # High excitement
    "insane": 0.30, "no way": 0.30, "holy": 0.25, "wtf": 0.25,
    "what the": 0.20, "are you kidding": 0.30, "can't believe": 0.25,
    "omg": 0.20, "oh my god": 0.30, "unbelievable": 0.25,
    "clutch": 0.30, "goat": 0.25, "cracked": 0.25, "godlike": 0.30,
    "rage": 0.25, "loses it": 0.30, "freaks out": 0.30,
    "screaming": 0.25, "yelling": 0.25, "crying": 0.20,
    "funny": 0.20, "lmao": 0.20, "lol": 0.15, "hilarious": 0.20,
    "wild": 0.20, "crazy": 0.20, "chaos": 0.25,
    "cheating": 0.25, "hacker": 0.25, "broken": 0.20,
    "1v5": 0.35, "1v4": 0.30, "1v3": 0.25, "last guy": 0.25,
    "win": 0.15, "victory": 0.20, "champion": 0.20,
    "fail": 0.20, "died": 0.15, "rip": 0.10,
    "clip it": 0.40, "clip that": 0.40,  # streamer asked to clip = guaranteed hype
    "let's go": 0.25, "lets go": 0.25,
}

# Keywords that indicate boring/skip-worthy content
BORING_KEYWORDS: list[str] = [
    "commercial", "break", "brb", "be right back",
    "just chatting", "irl", "donation", "sub goal",
    "ad break", "intermission",
    "tutorial", "guide", "tips", "how to",
    "eating", "cooking" "react",  # non-gaming streams
]

# Minimum hype score to proceed with rendering (clips below this are skipped)
MIN_HYPE_SCORE = 0.10  # Low bar — only skip genuinely dead clips


def score_clip_title(title: str) -> float:
    """Score a clip title for entertainment value. Returns 0.0-1.0.
    Returns 0.5 (neutral) for titles with no recognizable keywords — proceed anyway.
    Returns 0.0 only for clips with explicit BORING_KEYWORDS (definitive skip).
    """
    if not title:
        return 0.5  # Unknown quality — proceed anyway

    title_lower = title.lower()

    # Check boring keywords — explicit disqualify only
    for boring in BORING_KEYWORDS:
        if boring in title_lower:
            logger.debug("Boring keyword '%s' in title: %s", boring, title[:60])
            return 0.0

    score = 0.0
    for phrase, boost in HYPE_KEYWORDS.items():
        if phrase in title_lower:
            score += boost

    # Cap at 1.0; if no hype keywords found, return neutral 0.5 (not skip)
    if score == 0.0:
        return 0.5  # Neutral — undescriptive title, but not boring
    return min(1.0, score)


def is_boring_clip(title: str) -> bool:
    """Return True ONLY if clip has explicit boring/dead keywords (ad break, brb, etc).
    Clips with undescriptive titles are NOT skipped — just given neutral score.
    """
    if not title:
        return False
    title_lower = title.lower()
    return any(boring in title_lower for boring in BORING_KEYWORDS)


# ── LLM TITLE GENERATION ─────────────────────────────────────────────────────

_USED_TITLES_PATH = Path("data/used_titles.json")


def _load_used_titles() -> list[str]:
    try:
        if _USED_TITLES_PATH.exists():
            return json.loads(_USED_TITLES_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def _save_used_title(title: str) -> None:
    titles = _load_used_titles()
    titles.append(title)
    try:
        _USED_TITLES_PATH.parent.mkdir(parents=True, exist_ok=True)
        _USED_TITLES_PATH.write_text(json.dumps(titles[-50:], ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def generate_llm_title(
    creator: str,
    clip_title: str,
    channel_name: str,
    niche: str = "Gaming",
    openai_api_key: Optional[str] = None,
) -> Optional[str]:
    """Generate a curiosity-bait YouTube Shorts title via GPT-4o-mini.

    Returns the title string, or None if API unavailable/fails.
    Falls back gracefully so the series title is used instead.
    """
    api_key = openai_api_key or os.environ.get("OPENAI_API_KEY") or _read_env_key()
    if not api_key:
        logger.debug("No OpenAI API key — skipping LLM title generation")
        return None

    if not creator or not clip_title:
        return None

    # Build avoid block from recent titles
    recent = _load_used_titles()[-10:]
    avoid_block = ""
    if recent:
        avoid_block = "\n\nAVOID — these patterns have been used recently:\n" + "\n".join(f'- "{t}"' for t in recent)

    # Shuffle style examples each call for variety
    style_examples = [
        f'"{creator.capitalize()} had NO idea this was coming"',
        f'"How did {creator.capitalize()} just do that"',
        f'"{creator.capitalize()} wasn\'t supposed to survive this"',
        f'"Nobody expected {creator.capitalize()} to pull THIS off"',
        f'"The moment {creator.capitalize()} completely lost it"',
        f'"{creator.capitalize()} said the quiet part out loud"',
        f'"This is why people watch {creator.capitalize()}"',
        f'"{creator.capitalize()} could not believe what just happened"',
        f'"Only {creator.capitalize()} could make this look easy"',
    ]
    random.shuffle(style_examples)
    styles = "\n".join(f"- {s}" for s in style_examples[:4])

    prompt = f"""You write titles for viral YouTube Shorts on a {niche} channel called "{channel_name}".

Streamer: {creator.capitalize()}
Clip context: "{clip_title}"{avoid_block}

Write ONE title. Rules:
- Max 60 characters
- 1 emoji max, at the end (use Unicode e.g. 🎮 😤 💀 😂)
- Include streamer's name
- Create CURIOSITY — make viewers need to see what happened
- NO profanity or swearing
- NO words: INSANE, EPIC, HILARIOUS, AMAZING, UNREAL, INCREDIBLE
- NO multiple exclamation marks
- NO hashtags

Style examples (study these):
{styles}

Return ONLY the title, nothing else."""

    try:
        import urllib.request
        payload = json.dumps({
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 60,
            "temperature": 0.9,
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
        title = data["choices"][0]["message"]["content"].strip().strip('"').strip("'")
        if len(title) > 100:
            title = title[:97] + "..."
        logger.info("LLM title: '%s'", title)
        _save_used_title(title)
        return title
    except Exception as e:
        logger.warning("LLM title generation failed: %s", e)
        return None


def _read_env_key() -> Optional[str]:
    """Read OPENAI_API_KEY from clip_empire .env file."""
    env_path = Path("clip_empire/.env") if not Path(".env").exists() else Path(".env")
    # Try the known path
    for candidate in [Path(".env"), Path("clip_empire/.env"), Path(__file__).parents[2] / ".env"]:
        if candidate.exists():
            for line in candidate.read_text().splitlines():
                if line.startswith("OPENAI_API_KEY="):
                    return line.split("=", 1)[1].strip()
    return None


# ── CENSOR INTEGRATION ────────────────────────────────────────────────────────

def clean_title(title: str) -> str:
    """Apply profanity filter to a title before publishing."""
    try:
        from engine.utils.censor import censor_text
        return censor_text(title)
    except ImportError:
        return title
