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
        "THIS SHOULD BE ILLEGAL",
        "THE NUMBER DOESN'T LIE",
        "NOBODY EXPLAINS THIS",
        "IT ALL COLLAPSED",
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
    "Gaming": [
        "HE ACTUALLY DID THAT 🎮",
        "INSANE CLIP 😤",
        "NO WAY THIS HAPPENED",
        "{creator} IS BUILT DIFFERENT",
        "CLUTCH OR DELETE",
        "BEST PLAY OF THE YEAR?",
        "THEY COULDN'T BELIEVE IT",
        "THIS IS ILLEGAL 💀",
        "NOBODY PLAYS LIKE THIS",
        "{creator} DID WHAT?!",
        "CHAT WAS GOING INSANE",
        "WATCH THIS BEFORE SCROLLING",
        "{creator} REALLY JUST DID THAT",
    ],
}

# ── CTA TEXT (shown at video end, last 3s) ───────────────────────────────────

NICHE_CTAS: dict = {
    "Finance":       ["Follow for more", "Like if you're shocked", "Save this one", "Comment your take"],
    "Business":      ["Follow for real talk", "Like if this hit different", "Save for later"],
    "Tech/AI":       ["Follow for AI updates", "Like if this blew your mind", "Share this"],
    "Fitness":       ["Follow for gym content", "Like if you've seen this", "Drop a comment"],
    "Food":          ["Follow for more chaos", "Like if Gordon was right", "Comment your take"],
    "True Crime":    ["Follow for more cases", "Like if this shocked you", "Share this case"],
    "Experimental":  ["Follow for more", "Like if this was satisfying", "Save this", "Comment FIRE if you agree"],
    "Gaming":        ["Follow for more clips", "Like if this was insane", "Comment FIRE if you agree", "Drop a comment below", "Follow for daily clips"],
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
    "Gaming":        ["gaming", "twitch", "highlights", "clips", "gamingclips", "twitchclips", "clutch"],
}

# ── TITLE TEMPLATES ───────────────────────────────────────────────────────────
# Use {creator} and {topic} as placeholders if available.

NICHE_TITLE_TEMPLATES: dict = {
    "Finance": [
        "{creator} just exposed how this really works 📉",
        "The number {creator} revealed will shock you",
        "Why {creator} says the market is broken",
        "Nobody talks about what {creator} just said",
        "The financial truth Wall Street hides 💀",
        "{creator} breaks down exactly how they lost it all",
        "This is why your money is disappearing",
        "{creator} called this 6 months ago",
        "The collapse nobody saw coming — {creator} explains",
        "What {creator} said that changes everything",
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
    "Gaming": [
        "Watch this before scrolling: Nobody plays like this 🎮",
        "The most insane clip you'll see today",
        "This clip broke Twitch chat",
        "{creator} goes crazy after this play 🎮",
        "Best gaming moment of the week",
        "This play was absolutely filthy 🎮",
        "Chat couldn't believe what {creator} just did",
        "The clutch that nobody saw coming",
        "{creator} just broke the game 🎮",
        "Nobody expected {creator} to do this",
    ],
}


def get_hook(channel_name: str, creator: str = None) -> str:
    niche = CHANNELS.get(channel_name, {}).get("niche", "Experimental")

    # Use creator-specific hook overrides if available (50% of the time for variety)
    if creator:
        try:
            from engine.config.creator_profiles import get_hook_overrides
            overrides = get_hook_overrides(creator)
            if overrides and random.random() < 0.5:
                return random.choice(overrides)
        except Exception:
            pass

    hooks = NICHE_HOOKS.get(niche, NICHE_HOOKS["Experimental"])
    hook = random.choice(hooks)
    # Substitute {creator} placeholder with actual streamer name if known
    if creator and "{creator}" in hook:
        hook = hook.replace("{creator}", creator.upper())
    return hook


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


def get_title(channel_name: str, creator: str = None) -> str:
    niche = CHANNELS.get(channel_name, {}).get("niche", "Experimental")
    titles = NICHE_TITLE_TEMPLATES.get(niche, NICHE_TITLE_TEMPLATES["Experimental"])
    title = random.choice(titles)
    # Substitute {creator} placeholder with actual streamer name if known
    if creator and "{creator}" in title:
        title = title.replace("{creator}", creator.capitalize())
    return title
