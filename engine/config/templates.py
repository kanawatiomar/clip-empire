"""Niche-specific text templates for overlays and captions.

HOOKS:     First 3 seconds - pattern interrupt text to stop the scroll.
CTAS:      Last 3 seconds - call to action.
HASHTAGS:  Base hashtags per channel (merged with per-job hashtags from channel_definitions).
CAPTIONS:  Auto-generated YouTube video title templates.
"""

from accounts.channel_definitions import CHANNELS
import random

# ── HOOK TEXT (shown at video start, 0-3s) ──────────────────────────────────

NICHE_HOOKS: dict = {
    "Finance": [
        "WAIT FOR IT 💰",
        "THIS IS INSANE 📉",
        "THEY LOST EVERYTHING",
        "HOW DID THIS HAPPEN?",
        "$1M GONE IN SECONDS",
        "THE MARKET IS BROKEN",
        "NO ONE TALKS ABOUT THIS",
        "THEY TOLD YOU WRONG",
    ],
    "Business": [
        "BRUTAL TRUTH 💀",
        "THIS DESTROYED HIM",
        "BILLION DOLLAR MISTAKE",
        "NOBODY SAW THIS COMING",
        "HE SAID WHAT?!",
        "EVERY FOUNDER NEEDS THIS",
        "HARSH REALITY CHECK",
    ],
    "Tech/AI": [
        "AI JUST DID THIS 🤖",
        "THIS SHOULDN'T BE POSSIBLE",
        "THE FUTURE IS HERE",
        "THEY BUILT WHAT?!",
        "SCARY OR AMAZING?",
        "WAIT TILL YOU SEE THIS",
        "THIS CHANGES EVERYTHING",
    ],
    "Fitness": [
        "WATCH TILL THE END 💪",
        "HE ACTUALLY DID THAT",
        "FORM CHECK: DISASTER",
        "NEW WORLD RECORD?!",
        "GYM FAIL INCOMING 💀",
        "THIS TAKES DEDICATION",
        "MOST PEOPLE QUIT HERE",
    ],
    "Food": [
        "GORDON IS FURIOUS 🍳",
        "THIS IS NOT FOOD",
        "WORST KITCHEN EVER",
        "HOW IS THIS EDIBLE?",
        "3 STAR CHEF REACTION",
        "THEY RUINED IT",
        "WATCH THIS DISASTER",
    ],
    "True Crime": [
        "THIS CASE IS CHILLING",
        "POLICE NEVER SOLVED IT",
        "THE EVIDENCE VANISHED",
        "HE LIVED NEXT DOOR",
        "COLD CASE REOPENED",
        "NOBODY BELIEVED HER",
        "THE CLUES WERE THERE",
    ],
    "Experimental": [
        "WHAT IS THIS?! 😳",
        "ODDLY SATISFYING",
        "YOU NEED TO SEE THIS",
        "HOW?!",
        "UNEXPECTED ENDING",
        "WATCH THE WHOLE THING",
    ],
}

# ── CTA TEXT (shown at video end, last 3s) ───────────────────────────────────

NICHE_CTAS: dict = {
    "Finance":       ["Follow for more 💰", "Like if you're shocked", "Save this one"],
    "Business":      ["Follow for real talk", "Like if this hit different", "Save for later"],
    "Tech/AI":       ["Follow for AI updates 🤖", "Like if this blew your mind", "Share this"],
    "Fitness":       ["Follow for gym content 💪", "Like if you've seen this", "Drop a comment"],
    "Food":          ["Follow for more chaos 🍳", "Like if Gordon was right", "Comment your take"],
    "True Crime":    ["Follow for more cases", "Like if this shocked you", "Share this case"],
    "Experimental":  ["Follow for more 😳", "Like if this was satisfying", "Save this"],
}

# ── HASHTAGS ─────────────────────────────────────────────────────────────────

NICHE_HASHTAGS: dict = {
    "Finance":       ["finance", "money", "investing", "stocks", "wallstreet", "wealth"],
    "Business":      ["business", "entrepreneur", "startup", "success", "founder", "hustle"],
    "Tech/AI":       ["ai", "tech", "artificialintelligence", "chatgpt", "technology", "future"],
    "Fitness":       ["gym", "fitness", "workout", "bodybuilding", "gains", "gymlife"],
    "Food":          ["food", "cooking", "chef", "kitchen", "foodie", "gordonramsay"],
    "True Crime":    ["truecrime", "crime", "mystery", "coldcase", "unsolved", "detective"],
    "Experimental":  ["viral", "satisfying", "unexpected", "clips", "moments", "trending"],
}

# ── TITLE TEMPLATES ───────────────────────────────────────────────────────────
# Use {creator} and {topic} as placeholders if available.

NICHE_TITLE_TEMPLATES: dict = {
    "Finance": [
        "This trader lost everything in SECONDS 📉",
        "The market did WHAT?! 💀",
        "Nobody talks about this financial truth",
        "How they turned $1k into $1M (then lost it)",
        "Wall Street moment nobody expected",
    ],
    "Business": [
        "The startup mistake that cost $10M",
        "Shark Tank's most brutal rejection ever",
        "This entrepreneur's hard truth will hit different",
        "He built it from nothing — then it collapsed",
        "The business advice nobody wants to hear",
    ],
    "Tech/AI": [
        "This AI just did the impossible 🤖",
        "Tech demo that broke the internet",
        "Nobody expected this from AI in 2025",
        "The scariest AI moment you'll see today",
        "This changes everything about technology",
    ],
    "Fitness": [
        "Gym fail of the year 💀",
        "Nobody expected this lift",
        "The transformation took 1 year",
        "Gym etiquette violation of the century",
        "World's most insane gym moment",
    ],
    "Food": [
        "Gordon Ramsay's most brutal kitchen moment",
        "This cooking disaster was real",
        "The worst food I've ever seen 🍳",
        "Chef reaction to this crime against food",
        "Kitchen nightmare that went viral",
    ],
    "True Crime": [
        "The case that was never solved",
        "Evidence disappeared — nobody knows why",
        "Cold case that haunts investigators",
        "He lived next door for 10 years",
        "The clue everyone missed for decades",
    ],
    "Experimental": [
        "This was NOT supposed to happen 😳",
        "Oddly satisfying and I can't explain why",
        "The most unexpected moment of the day",
        "How is this even real?",
        "This will make your brain feel good",
    ],
}


def get_hook(channel_name: str) -> str:
    niche = CHANNELS.get(channel_name, {}).get("niche", "Experimental")
    hooks = NICHE_HOOKS.get(niche, NICHE_HOOKS["Experimental"])
    return random.choice(hooks)


def get_cta(channel_name: str) -> str:
    niche = CHANNELS.get(channel_name, {}).get("niche", "Experimental")
    ctas = NICHE_CTAS.get(niche, NICHE_CTAS["Experimental"])
    return random.choice(ctas)


def get_hashtags(channel_name: str) -> list:
    niche = CHANNELS.get(channel_name, {}).get("niche", "Experimental")
    base = NICHE_HASHTAGS.get(niche, [])
    channel_tags = CHANNELS.get(channel_name, {}).get("tags", [])
    # Combine, deduplicate, cap at 8
    combined = list(dict.fromkeys(base + channel_tags))
    return combined[:8]


def get_title(channel_name: str) -> str:
    niche = CHANNELS.get(channel_name, {}).get("niche", "Experimental")
    titles = NICHE_TITLE_TEMPLATES.get(niche, NICHE_TITLE_TEMPLATES["Experimental"])
    return random.choice(titles)
