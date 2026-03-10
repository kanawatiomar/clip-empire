"""Creator Profiles — per-streamer configuration for the engine.

Each creator has unique characteristics that should influence how we:
- Crop their content (webcam position)
- Select clips (what moments perform well for them)
- Generate hooks and titles (match their content personality)
- Score clips (what hype words are relevant per creator)

This is the authoritative source. Sources.py crop_anchor values should
always match the profile here.
"""

from __future__ import annotations
from typing import Optional

# ── CREATOR PROFILE SCHEMA ───────────────────────────────────────────────────
# crop_anchor:    "left" | "right" | "center" — where webcam sits in frame
# content_types:  ordered list of what performs best — first = most common
#                 options: "clutch", "rage", "funny", "educational", "reaction"
# hook_style:     how the hook text should feel for this creator
#                 options: "hype", "reaction", "question", "statement"
# llm_context:    extra context hint for GPT-4o-mini title generation
# min_views:      minimum Twitch clip views before we consider it
# avoid_keywords: title keywords that suggest bad clips for this creator
# prefer_keywords: title keywords that suggest good clips for this creator

CREATOR_PROFILES: dict[str, dict] = {

    # ── ARC HIGHLIGHTZ CREATORS ───────────────────────────────────────────────

    "tfue": {
        "display_name": "Tfue",
        "channel": "arc_highlightz",
        "crop_anchor": "right",         # webcam top-right, gameplay left
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
        ],
    },

    "cloakzy": {
        "display_name": "Cloakzy",
        "channel": "arc_highlightz",
        "crop_anchor": "left",          # webcam top-left
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
        ],
    },

    # ── FOMO HIGHLIGHTS CREATORS ──────────────────────────────────────────────

    "shroud": {
        "display_name": "Shroud",
        "channel": "fomo_highlights",
        "crop_anchor": "right",         # webcam bottom-left → keep gameplay on right
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
    },

    "nickmercs": {
        "display_name": "NICKMERCS",
        "channel": "fomo_highlights",
        "crop_anchor": "left",          # webcam bottom-right → anchor left
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
    },

    "timthetatman": {
        "display_name": "TimTheTatman",
        "channel": "fomo_highlights",
        "crop_anchor": "right",         # webcam bottom-left → anchor right
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
    },

    # ── VIRAL RECAPS CREATORS ─────────────────────────────────────────────────

    "moistcr1tikal": {
        "display_name": "Moistcr1tikal",
        "channel": "viral_recaps",
        "crop_anchor": "center",        # centered face-cam, minimal gameplay
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
    },

    "hasanabi": {
        "display_name": "HasanAbi",
        "channel": "viral_recaps",
        "crop_anchor": "right",         # cam on left → keep content right
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
    },
}


    # ── MARKET MELTDOWNS CREATORS ─────────────────────────────────────────────

    "patrickboyle": {
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
    },

    "wallstreetmillennial": {
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
    },

    "coffeezilla": {
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
    },

    "rareliquid": {
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
    },

    "plainbagel": {
        "channel": "market_meltdowns",
        "crop_anchor": "top",
        "content_types": ["educational", "funny"],
        "hook_style": "question",
        "min_views": 0,
        "llm_context": "The Plain Bagel explains financial concepts and news in a calm, accessible way with occasional dry humor. Titles should be approachable but highlight the most surprising or counterintuitive point.",
        "prefer_keywords": ["actually", "truth", "mistake", "wrong", "surprising", "real"],
        "avoid_keywords": [],
        "hook_overrides": [],
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
