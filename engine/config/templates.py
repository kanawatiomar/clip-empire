"""Niche-specific text templates for overlays and captions.

HOOKS:     First 3 seconds - pattern interrupt text to stop the scroll.
CTAS:      Last 3 seconds - call to action.
HASHTAGS:  Base hashtags per channel (merged with per-job hashtags from channel_definitions).
CAPTIONS:  Auto-generated YouTube video title templates.
"""

from accounts.channel_definitions import CHANNELS
from pathlib import Path
import json
import random

# ── HOOK DEDUPLICATION ────────────────────────────────────────────────────────

_USED_HOOKS_PATH = Path("data/used_hooks.json")
_HOOK_MEMORY = 12  # avoid repeating the last N hooks per channel

# ── TITLE DEDUPLICATION ───────────────────────────────────────────────────────

_USED_TITLES_PATH = Path("data/used_titles_per_channel.json")
_TITLE_MEMORY = 20  # avoid repeating the last N titles per channel


def _load_used_titles_for_channel(channel_name: str) -> list[str]:
    try:
        if _USED_TITLES_PATH.exists():
            data = json.loads(_USED_TITLES_PATH.read_text(encoding="utf-8"))
            return data.get(channel_name, [])
    except Exception:
        pass
    return []


def _save_used_title_for_channel(channel_name: str, title: str) -> None:
    try:
        data: dict = {}
        if _USED_TITLES_PATH.exists():
            data = json.loads(_USED_TITLES_PATH.read_text(encoding="utf-8"))
        history = data.get(channel_name, [])
        history.append(title)
        data[channel_name] = history[-_TITLE_MEMORY:]
        _USED_TITLES_PATH.parent.mkdir(parents=True, exist_ok=True)
        _USED_TITLES_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _load_used_hooks(channel_name: str) -> list[str]:
    try:
        if _USED_HOOKS_PATH.exists():
            data = json.loads(_USED_HOOKS_PATH.read_text(encoding="utf-8"))
            return data.get(channel_name, [])
    except Exception:
        pass
    return []


def _save_used_hook(channel_name: str, hook: str) -> None:
    try:
        data: dict = {}
        if _USED_HOOKS_PATH.exists():
            data = json.loads(_USED_HOOKS_PATH.read_text(encoding="utf-8"))
        history = data.get(channel_name, [])
        history.append(hook)
        data[channel_name] = history[-_HOOK_MEMORY:]
        _USED_HOOKS_PATH.parent.mkdir(parents=True, exist_ok=True)
        _USED_HOOKS_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def _pick_fresh(options: list[str], used: list[str]) -> str:
    """Pick an option not in the recent used list. Falls back to full pool if all used."""
    fresh = [o for o in options if o not in used]
    pool = fresh if fresh else options
    return random.choice(pool)

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
        "THIS CLIP BROKE TWITCH",
        "CHAT FROZE WATCHING THIS",
        "NOT A SINGLE PERSON EXPECTED THIS",
        "{creator} SAID NOTHING AND DID EVERYTHING",
        "THE AUDACITY 💀",
        "HOW IS THIS EVEN LEGAL",
        "{creator} ATE AND LEFT NO CRUMBS",
        "WHATEVER YOU DO, WATCH THIS",
        "CLIP IT. SAVE IT. SHARE IT.",
        "THIS IS WHAT PEAK GAMING LOOKS LIKE",
        "VIEWERS LOST THEIR MINDS",
        "{creator} WENT OFF",
        "RARE {creator} MOMENT",
        "I HAVE NO WORDS 😤",
        "TELL ME YOU'RE CRACKED WITHOUT TELLING ME",
        "THE LOBBY WAS NOT READY",
        "ZERO HESITATION",
        "{creator} COOKED",
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
        "This is why your money is disappearing",
        "The financial truth Wall Street hides 💀",
        "Nobody explains this part of investing",
        "The collapse nobody saw coming",
        "What the banks don't want you to know",
        "This changed how I think about money",
        "The number that explains everything right now",
        "Why the market is doing this — explained",
        "This is what a bubble actually looks like",
        "Most people get this completely wrong",
        "The financial move nobody is talking about",
        "Why your savings are losing value right now",
        "The trade that made millions — and then didn't",
        "This is the moment it all fell apart",
        "What happened when they ran out of money",
        "The warning sign everyone ignored",
        "This is how markets actually work 📉",
        "The quiet crisis nobody is covering",
        "How one decision wiped out everything",
        "The thing Wall Street hopes you never learn",
        "This is why timing the market doesn't work",
        "The financial truth that changes everything",
        "What happened after they bet it all",
        "Nobody saw this market move coming",
        "This is what a real financial meltdown looks like",
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
        "The moment {creator}'s chat went silent 😤",
        "This is why {creator} has millions of viewers",
        "{creator} made it look too easy 🎮",
        "Zero thought. Perfect execution.",
        "The lobby had no answer for this",
        "I've watched this 10 times and still don't understand",
        "{creator} casually does the impossible",
        "This is the clip everyone's talking about",
        "Chat was not ready for this",
        "{creator} woke up and chose violence 💀",
        "This is what separates {creator} from everyone else",
        "The play that left chat speechless",
        "When {creator} locks in 🎮",
        "Nobody in the lobby stood a chance",
        "If you blink you'll miss it",
        "Somehow {creator} made it out",
        "The reaction says it all",
        "This one got clipped for a reason",
        "That's not a skill gap — that's a skill canyon",
        "{creator} really said 'watch this' 💀",
    ],
}


def get_hook(channel_name: str, creator: str = None) -> str:
    niche = CHANNELS.get(channel_name, {}).get("niche", "Experimental")
    used = _load_used_hooks(channel_name)

    # Build candidate pool: merge niche hooks + creator overrides if available
    niche_hooks = NICHE_HOOKS.get(niche, NICHE_HOOKS["Experimental"])
    all_candidates = list(niche_hooks)

    if creator:
        try:
            from engine.config.creator_profiles import get_hook_overrides
            overrides = get_hook_overrides(creator)
            if overrides:
                all_candidates = all_candidates + overrides
        except Exception:
            pass

    hook = _pick_fresh(all_candidates, used)

    # Substitute {creator} placeholder with actual streamer name if known
    if creator and "{creator}" in hook:
        hook = hook.replace("{creator}", creator.upper())

    _save_used_hook(channel_name, hook)
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
    templates = NICHE_TITLE_TEMPLATES.get(niche, NICHE_TITLE_TEMPLATES["Experimental"])

    # Build resolved candidates (with {creator} substituted so dedup compares final text)
    def resolve(t: str) -> str:
        if creator and "{creator}" in t:
            return t.replace("{creator}", creator.capitalize())
        return t

    resolved_candidates = [resolve(t) for t in templates]
    used = _load_used_titles_for_channel(channel_name)
    title = _pick_fresh(resolved_candidates, used)
    _save_used_title_for_channel(channel_name, title)
    return title
