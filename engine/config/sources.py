"""Source configuration for all 10 Clip Empire channels.

Each channel entry maps to a list of source objects:
  - platform:  "youtube" | "tiktok" | "reddit" | "twitter"
  - url:        full URL to channel/profile/subreddit
  - type:       "channel" | "profile" | "subreddit" | "playlist" | "search"
  - priority:   1 (high) → 3 (low) — used to sort sources when multiple available
  - max_age_days: skip clips older than this (keep content fresh)
  - min_dur_s / max_dur_s: clip duration window (15-180 defaults)

Add / swap sources at any time. The engine respects these at runtime.
"""

SOURCE_DEFAULTS = {
    "min_dur_s": 15,
    "max_dur_s": 180,
    "max_age_days": 30,
    "max_per_run": 5,   # clips to download per source per engine run
}

CHANNEL_SOURCES: dict = {

    # ── FINANCE ─────────────────────────────────────────────────────────────

    "market_meltdowns": [
        {"platform": "youtube", "url": "https://www.youtube.com/@GrahamStephan",
         "type": "channel", "priority": 1, "max_age_days": 14},
        {"platform": "youtube", "url": "https://www.youtube.com/@AndreiJikh",
         "type": "channel", "priority": 1},
        {"platform": "youtube", "url": "https://www.youtube.com/@MeetKevin",
         "type": "channel", "priority": 2},
        {"platform": "tiktok", "url": "https://www.tiktok.com/@markdice",
         "type": "profile", "priority": 2},
        {"platform": "youtube", "url": "https://www.youtube.com/@theplainbagel",
         "type": "channel", "priority": 2},
        # Search fallback for fresh crash/meltdown content
        {"platform": "youtube",
         "url": "https://www.youtube.com/results?search_query=stock+market+crash+2025+shorts",
         "type": "search", "priority": 3, "max_age_days": 7},
    ],

    "crypto_confessions": [
        {"platform": "youtube", "url": "https://www.youtube.com/@CoinBureau",
         "type": "channel", "priority": 1},
        {"platform": "youtube", "url": "https://www.youtube.com/@BenArmstrong",
         "type": "channel", "priority": 1},
        {"platform": "tiktok", "url": "https://www.tiktok.com/@cryptogirly_",
         "type": "profile", "priority": 2},
        {"platform": "youtube",
         "url": "https://www.youtube.com/results?search_query=crypto+loss+confession+shorts",
         "type": "search", "priority": 3, "max_age_days": 14},
        {"platform": "reddit", "url": "https://www.reddit.com/r/CryptoCurrency/top/?t=week",
         "type": "subreddit", "priority": 2},
    ],

    "rich_or_ruined": [
        {"platform": "youtube", "url": "https://www.youtube.com/@alexhormozi",
         "type": "channel", "priority": 1, "max_age_days": 60},
        {"platform": "youtube", "url": "https://www.youtube.com/@GaryVee",
         "type": "channel", "priority": 1},
        {"platform": "youtube",
         "url": "https://www.youtube.com/results?search_query=millionaire+went+broke+story+shorts",
         "type": "search", "priority": 2, "max_age_days": 30},
        {"platform": "tiktok", "url": "https://www.tiktok.com/@hramsey",
         "type": "profile", "priority": 2},
    ],

    # ── BUSINESS ────────────────────────────────────────────────────────────

    "startup_graveyard": [
        {"platform": "youtube", "url": "https://www.youtube.com/playlist?list=PLF596A4DFAF3E0FAB",
         "type": "playlist", "priority": 1,
         "label": "Shark Tank Season Mix"},  # official Shark Tank
        {"platform": "youtube", "url": "https://www.youtube.com/@coffeezilla",
         "type": "channel", "priority": 1},
        {"platform": "youtube",
         "url": "https://www.youtube.com/results?search_query=startup+failure+story+shorts",
         "type": "search", "priority": 2, "max_age_days": 30},
        {"platform": "reddit", "url": "https://www.reddit.com/r/Entrepreneur/top/?t=week",
         "type": "subreddit", "priority": 3},
    ],

    "self_made_clips": [
        {"platform": "youtube", "url": "https://www.youtube.com/@alexhormozi",
         "type": "channel", "priority": 1},
        {"platform": "tiktok", "url": "https://www.tiktok.com/@alexhormozi",
         "type": "profile", "priority": 1},
        {"platform": "youtube", "url": "https://www.youtube.com/@GaryVee",
         "type": "channel", "priority": 1},
        {"platform": "tiktok", "url": "https://www.tiktok.com/@garyvee",
         "type": "profile", "priority": 2},
        {"platform": "youtube",
         "url": "https://www.youtube.com/results?search_query=entrepreneur+motivation+hard+truth+shorts",
         "type": "search", "priority": 2, "max_age_days": 14},
    ],

    # ── TECH / AI ────────────────────────────────────────────────────────────

    "ai_did_what": [
        {"platform": "youtube", "url": "https://www.youtube.com/@linustechtips",
         "type": "channel", "priority": 2, "max_age_days": 14},
        {"platform": "youtube", "url": "https://www.youtube.com/@mkbhd",
         "type": "channel", "priority": 1},
        {"platform": "youtube", "url": "https://www.youtube.com/@TwoMinutePapers",
         "type": "channel", "priority": 1},
        {"platform": "tiktok", "url": "https://www.tiktok.com/@ai.explained",
         "type": "profile", "priority": 1},
        {"platform": "youtube",
         "url": "https://www.youtube.com/results?search_query=ai+shocking+demo+2025+shorts",
         "type": "search", "priority": 2, "max_age_days": 7},
    ],

    # ── FITNESS ──────────────────────────────────────────────────────────────

    "gym_moments": [
        {"platform": "youtube", "url": "https://www.youtube.com/@jeffnippard",
         "type": "channel", "priority": 1},
        {"platform": "tiktok", "url": "https://www.tiktok.com/@cbum",
         "type": "profile", "priority": 1},
        {"platform": "tiktok", "url": "https://www.tiktok.com/@gymfails",
         "type": "profile", "priority": 2},
        {"platform": "youtube",
         "url": "https://www.youtube.com/results?search_query=gym+fail+compilation+shorts",
         "type": "search", "priority": 2, "max_age_days": 14},
        {"platform": "reddit", "url": "https://www.reddit.com/r/gym/top/?t=week",
         "type": "subreddit", "priority": 3},
    ],

    # ── FOOD ─────────────────────────────────────────────────────────────────

    "kitchen_chaos": [
        {"platform": "youtube", "url": "https://www.youtube.com/@gordonramsay",
         "type": "channel", "priority": 1},
        {"platform": "tiktok", "url": "https://www.tiktok.com/@gordonramsayofficial",
         "type": "profile", "priority": 1},
        {"platform": "youtube",
         "url": "https://www.youtube.com/results?search_query=cooking+disaster+fail+shorts",
         "type": "search", "priority": 2, "max_age_days": 14},
        {"platform": "reddit", "url": "https://www.reddit.com/r/KitchenConfidential/top/?t=week",
         "type": "subreddit", "priority": 3},
    ],

    # ── TRUE CRIME ────────────────────────────────────────────────────────────

    "cases_unsolved": [
        {"platform": "youtube", "url": "https://www.youtube.com/@CriminallyListed",
         "type": "channel", "priority": 1},
        {"platform": "youtube", "url": "https://www.youtube.com/@ColdCaseCrimes",
         "type": "channel", "priority": 1},
        {"platform": "tiktok", "url": "https://www.tiktok.com/@truecrimetok",
         "type": "profile", "priority": 2},
        {"platform": "youtube",
         "url": "https://www.youtube.com/results?search_query=unsolved+cold+case+60+seconds+shorts",
         "type": "search", "priority": 2, "max_age_days": 60},
    ],

    # ── EXPERIMENTAL ─────────────────────────────────────────────────────────

    "unfiltered_clips": [
        {"platform": "reddit", "url": "https://www.reddit.com/r/oddlysatisfying/top/?t=day",
         "type": "subreddit", "priority": 1, "max_age_days": 3},
        {"platform": "reddit", "url": "https://www.reddit.com/r/nextfuckinglevel/top/?t=day",
         "type": "subreddit", "priority": 1, "max_age_days": 3},
        {"platform": "reddit", "url": "https://www.reddit.com/r/interestingasfuck/top/?t=day",
         "type": "subreddit", "priority": 2, "max_age_days": 3},
        {"platform": "youtube",
         "url": "https://www.youtube.com/results?search_query=satisfying+unexpected+viral+shorts",
         "type": "search", "priority": 3, "max_age_days": 7},
    ],
}
