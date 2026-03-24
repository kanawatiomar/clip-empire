"""Per-channel series system.

Each creator can have multiple named series based on clip theme.
Counters are stored in the `series_counters` DB table.

Series title format:  "{Creator} {Series} #{N}"
Example:              "Shroud Best Plays #12"
                      "Tfue Rage Moments #3"
                      "Moistcr1tikal Funny Moments #7"
"""

from __future__ import annotations

import re
import sqlite3
from typing import Optional

DATABASE_PATH = "data/clip_empire.db"

# ── THEME KEYWORDS ──────────────────────────────────────────────────────────
# Matched against the raw clip title (lowercase). First match wins.

GAMING_THEMES: list[tuple[str, list[str]]] = [
    ("Rage Moments",  ["rage", "mad", "tilt", "tilted", "angry", "furious", "loses it", "freaks out"]),
    ("Funny Moments", ["funny", "lol", "lmao", "rofl", "haha", "humor", "hilarious", "cringe", "awkward"]),
    ("Best Plays",    ["clutch", "insane", "insane play", "no way", "impossible", "cracked", "goated", "best", "highlight", "sick play", "godly"]),
    ("Fails",         ["fail", "died", "rip ", "oof", "trolled", "griefed", "unlucky", "terrible", "awful"]),
    ("Moments",       []),   # default / catch-all
]

FINANCE_THEMES: list[tuple[str, list[str]]] = [
    ("Market Crashes", ["crash", "dump", "collapse", "bubble", "recession", "crisis", "lost everything"]),
    ("Big Wins",       ["bull", "moon", "ath", "profit", "gained", "win", "rich", "millionaire"]),
    ("Hot Takes",      ["wrong", "controversial", "nobody talks", "truth", "unpopular", "exposed"]),
    ("Moments",        []),
]

NICHE_THEMES: dict[str, list[tuple[str, list[str]]]] = {
    "Gaming":      GAMING_THEMES,
    "Finance":     FINANCE_THEMES,
    "Business":    GAMING_THEMES,   # reuse gaming structure for now
    "Tech/AI":     GAMING_THEMES,
    "Fitness":     GAMING_THEMES,
    "Food":        GAMING_THEMES,
    "True Crime":  GAMING_THEMES,
    "Experimental": GAMING_THEMES,
}


# ── PER-CHANNEL LOCKED THEMES ────────────────────────────────────────────────
# If a channel is listed here, ALL clips for that channel use the fixed theme
# regardless of clip title. Prevents random sub-series spawning (e.g., "Funny
# Moments #1" appearing on a channel that should only have "Moments").

CHANNEL_LOCKED_THEME: dict[str, str] = {
    "arc_highlightz":  "Moments",
    "fomo_highlights": "Moments",
    "viral_recaps":    "Moments",
}


# ── THEME CLASSIFIER ─────────────────────────────────────────────────────────

def classify_theme(clip_title: str, niche: str = "Gaming", channel_name: str = "") -> str:
    """Return the series theme name for a given clip title.
    
    If channel_name is in CHANNEL_LOCKED_THEME, always returns the locked value
    so the channel stays on a single consistent series (e.g. 'Moments' only).
    """
    if channel_name and channel_name in CHANNEL_LOCKED_THEME:
        return CHANNEL_LOCKED_THEME[channel_name]
    title_lower = (clip_title or "").lower()
    themes = NICHE_THEMES.get(niche, GAMING_THEMES)
    for theme_name, keywords in themes:
        if not keywords:        # catch-all
            return theme_name
        if any(kw in title_lower for kw in keywords):
            return theme_name
    return "Moments"            # absolute fallback


# ── DB SETUP ─────────────────────────────────────────────────────────────────

def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS series_counters (
            channel_name  TEXT NOT NULL,
            creator       TEXT NOT NULL,
            series_name   TEXT NOT NULL,
            count         INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (channel_name, creator, series_name)
        )
    """)
    conn.commit()


# ── COUNTER ───────────────────────────────────────────────────────────────────

def next_episode(
    channel_name: str,
    creator: str,
    series_name: str,
    db_path: str = DATABASE_PATH,
) -> int:
    """Increment and return the next episode number for this series."""
    conn = sqlite3.connect(db_path)
    _ensure_table(conn)
    conn.execute("""
        INSERT INTO series_counters (channel_name, creator, series_name, count)
        VALUES (?, ?, ?, 1)
        ON CONFLICT(channel_name, creator, series_name)
        DO UPDATE SET count = count + 1
    """, (channel_name, creator, series_name))
    conn.commit()
    row = conn.execute(
        "SELECT count FROM series_counters WHERE channel_name=? AND creator=? AND series_name=?",
        (channel_name, creator, series_name),
    ).fetchone()
    conn.close()
    return row[0] if row else 1


# ── TITLE BUILDER ─────────────────────────────────────────────────────────────

def build_series_title(
    channel_name: str,
    creator: str,
    clip_title: str,
    niche: str = "Gaming",
    db_path: str = DATABASE_PATH,
) -> str:
    """Return a numbered series title like 'Shroud Best Plays #12'."""
    theme = classify_theme(clip_title, niche, channel_name=channel_name)
    n = next_episode(channel_name, creator, theme, db_path)
    # Use display_name from creator profile if available (e.g. "Shinya" for shinyatheninja)
    from engine.config.creator_profiles import get_profile
    profile = get_profile(creator)
    display_creator = profile.get("display_name") or creator.capitalize()
    return f"{display_creator} {theme} #{n}"
