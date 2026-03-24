"""Source configuration for all Clip Empire channels.

Each channel entry maps to a list of source objects:

  - platform:  "youtube" | "tiktok" | "twitch" | "reddit"
  - url:        full URL to channel/profile/subreddit/clips page
  - type:       "channel" | "profile" | "subreddit" | "search" | "longform"
  - priority:   1 (high) → 3 (low) — sources are tried in priority order
  - max_age_days: skip clips older than this

── COPYRIGHT POLICY ──────────────────────────────────────────────────────────
✅ SAFE:   type="longform" — downloads full video, extracts our own highlight
           (transformative fair use; we pick the moment, add overlays + captions)
✅ SAFE:   Twitch clips — fan-created clips from a different platform
❌ RISKY:  Reposting existing YouTube Shorts verbatim (not transformative)
❌ RISKY:  type="channel" pointing to YouTube /shorts tab = repost risk

RULE: For YouTube sources, always use type="longform" (extract from full videos).
      Never use type="channel" for YouTube unless it's a search or playlist of
      third-party compilations. Gaming uses Twitch clips — no YouTube needed.
──────────────────────────────────────────────────────────────────────────────

  - min_dur_s / max_dur_s: clip duration window (15-180 defaults)



Add / swap sources at any time. The engine respects these at runtime.

"""



SOURCE_DEFAULTS = {

    "min_dur_s": 15,

    "max_dur_s": 180,

    "max_age_days": 30,

    "max_per_run": 5,   # clips to download per source per engine run

}



SOURCES: dict  # forward reference — assigned below
CHANNEL_SOURCES: dict = {



    # ── FINANCE ─────────────────────────────────────────────────────────────



    "market_meltdowns": [
        # Mid-tier finance creators — original commentary, no ContentID.
        # Avoid mega-creators (Graham Stephan, Meet Kevin) — ContentID risk.
        # All use type="longform" — we extract peak audio moments ourselves (transformative).
        {"platform": "youtube", "url": "https://www.youtube.com/@PatrickBoyleOnFinance/videos",
         "type": "longform", "priority": 1, "max_age_days": 30, "target_dur_s": 45,
         "creator": "patrickboyle", "crop_anchor": "top"},
        {"platform": "youtube", "url": "https://www.youtube.com/@WallStreetMillennial/videos",
         "type": "longform", "priority": 1, "max_age_days": 30, "target_dur_s": 45,
         "creator": "wallstreetmillennial", "crop_anchor": "top"},
        {"platform": "youtube", "url": "https://www.youtube.com/@coffeeziIIa/videos",
         "type": "longform", "priority": 1, "max_age_days": 14, "target_dur_s": 40,
         "creator": "coffeezilla", "crop_anchor": "top"},
        {"platform": "youtube", "url": "https://www.youtube.com/@RareLiquid/videos",
         "type": "longform", "priority": 2, "max_age_days": 14, "target_dur_s": 40,
         "creator": "rareliquid", "crop_anchor": "top"},
        {"platform": "youtube", "url": "https://www.youtube.com/@theplainbagel/videos",
         "type": "longform", "priority": 2, "max_age_days": 30, "target_dur_s": 40,
         "creator": "plainbagel", "crop_anchor": "top"},
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



    # ── FEMALE STREAMERS ─────────────────────────────────────────────────────

    "stream_sirens": [
        # Hot-tub / suggestive era streamers — pull Twitch clips (reactions, drama, viral moments)
        # Strategy: funny/viral moments only, avoid explicit content — stays YouTube-safe
        {"platform": "twitch", "url": "https://www.twitch.tv/amouranth/clips",
         "type": "channel", "priority": 1, "max_age_days": 7,
         "min_dur_s": 15, "max_dur_s": 60, "max_per_run": 6,
         "crop_anchor": "center", "min_views": 5000},
        {"platform": "twitch", "url": "https://www.twitch.tv/alinity/clips",
         "type": "channel", "priority": 1, "max_age_days": 7,
         "min_dur_s": 15, "max_dur_s": 60, "max_per_run": 5,
         "crop_anchor": "center", "min_views": 3000},
        {"platform": "twitch", "url": "https://www.twitch.tv/morgpie/clips",
         "type": "channel", "priority": 2, "max_age_days": 7,
         "min_dur_s": 15, "max_dur_s": 60, "max_per_run": 4,
         "crop_anchor": "center", "min_views": 2000},
        {"platform": "twitch", "url": "https://www.twitch.tv/indiefoxx/clips",
         "type": "channel", "priority": 2, "max_age_days": 30,
         "min_dur_s": 15, "max_dur_s": 60, "max_per_run": 4,
         "crop_anchor": "center", "min_views": 1000},
        # YouTube fallback — drama/reaction compilations
        {"platform": "youtube",
         "url": "https://www.youtube.com/results?search_query=amouranth+funny+moments+twitch+clips+2025",
         "type": "search", "priority": 3, "max_age_days": 14,
         "min_dur_s": 15, "max_dur_s": 60, "crop_anchor": "center"},
    ],

    "stream_queens": [
        # Top female streamers — gaming, variety, wholesome/funny/viral moments
        {"platform": "twitch", "url": "https://www.twitch.tv/pokimane/clips",
         "type": "channel", "priority": 1, "max_age_days": 7,
         "min_dur_s": 15, "max_dur_s": 60, "max_per_run": 6,
         "crop_anchor": "center", "min_views": 5000},
        {"platform": "twitch", "url": "https://www.twitch.tv/emiru/clips",
         "type": "channel", "priority": 1, "max_age_days": 7,
         "min_dur_s": 15, "max_dur_s": 60, "max_per_run": 6,
         "crop_anchor": "center", "min_views": 3000},
        {"platform": "twitch", "url": "https://www.twitch.tv/ironmouse/clips",
         "type": "channel", "priority": 1, "max_age_days": 7,
         "min_dur_s": 15, "max_dur_s": 60, "max_per_run": 5,
         "crop_anchor": "center", "min_views": 3000},
        {"platform": "twitch", "url": "https://www.twitch.tv/extraemily/clips",
         "type": "channel", "priority": 2, "max_age_days": 7,
         "min_dur_s": 15, "max_dur_s": 60, "max_per_run": 5,
         "crop_anchor": "center", "min_views": 2000},
        {"platform": "twitch", "url": "https://www.twitch.tv/valkyrae/clips",
         "type": "channel", "priority": 2, "max_age_days": 7,
         "min_dur_s": 15, "max_dur_s": 60, "max_per_run": 5,
         "crop_anchor": "center", "min_views": 2000},
        # YouTube fallback
        {"platform": "youtube",
         "url": "https://www.youtube.com/results?search_query=pokimane+funny+moments+twitch+clips+2025",
         "type": "search", "priority": 3, "max_age_days": 14,
         "min_dur_s": 15, "max_dur_s": 60, "crop_anchor": "center"},
        {"platform": "youtube",
         "url": "https://www.youtube.com/results?search_query=emiru+best+clips+twitch+2025",
         "type": "search", "priority": 3, "max_age_days": 14,
         "min_dur_s": 15, "max_dur_s": 60, "crop_anchor": "center"},
    ],

    # -- GAMING ----------------------------------------------------------------

    "arc_highlightz": [
        # crop_anchor: where the streamer face/webcam sits in the frame
        #   left   -> crop window shifts left  (webcam bottom-left, action right)
        #   right  -> crop window shifts right (webcam bottom-right, action left)
        #   center -> standard center crop
        # min_views: only take clips with this many views (quality filter)
        # max_age_days: 30 — wide window so engine doesn't starve when streamers
        #   take breaks or top clips from recent days are already used.
        # range=30d → Twitch serves clips sorted by recent popularity (not all-time top)
        # max_per_run=15 → fetch more per run to build a larger unused pool
        # min_views=500 — 2000 threshold exhausted entire 30d pool; 500 still filters junk
        # Added Myth, Bugha, Benjyfishy as additional Fortnite creators for supply depth
        {"platform": "twitch", "url": "https://www.twitch.tv/tfue/clips?filter=clips&range=30d",
         "type": "channel", "priority": 1, "max_age_days": 30,
         "min_dur_s": 20, "max_dur_s": 60, "max_per_run": 40,
         "crop_anchor": "right", "min_views": 500},
        {"platform": "twitch", "url": "https://www.twitch.tv/cloakzy/clips?filter=clips&range=30d",
         "type": "channel", "priority": 1, "max_age_days": 30,
         "min_dur_s": 20, "max_dur_s": 60, "max_per_run": 40,
         "crop_anchor": "left", "min_views": 500},
        {"platform": "twitch", "url": "https://www.twitch.tv/myth/clips?filter=clips&range=30d",
         "type": "channel", "priority": 2, "max_age_days": 30,
         "min_dur_s": 20, "max_dur_s": 60, "max_per_run": 20,
         "crop_anchor": "right", "min_views": 500},
        {"platform": "twitch", "url": "https://www.twitch.tv/bugha/clips?filter=clips&range=30d",
         "type": "channel", "priority": 2, "max_age_days": 30,
         "min_dur_s": 20, "max_dur_s": 60, "max_per_run": 20,
         "crop_anchor": "right", "min_views": 500},
        {"platform": "youtube",
         "url": "https://www.youtube.com/results?search_query=tfue+highlights+2025+shorts",
         "type": "search", "priority": 3, "max_age_days": 7,
         "min_dur_s": 20, "max_dur_s": 60, "crop_anchor": "center"},
        {"platform": "youtube",
         "url": "https://www.youtube.com/results?search_query=cloakzy+best+moments+2025+shorts",
         "type": "search", "priority": 3, "max_age_days": 7,
         "min_dur_s": 20, "max_dur_s": 60, "crop_anchor": "center"},
    ],

    "viral_recaps": [
        # ── PRIORITY 1: Transcript-LLM extraction from YouTube VODs ──────────
        # LLM reads transcript, picks the best self-contained funny/engaging moment.
        # Same-day content — no dependency on fan clip view counts.
        {"platform": "youtube", "url": "https://www.youtube.com/@penguinz0/videos",
         "type": "transcript", "priority": 1, "max_age_days": 3,
         "target_dur_s": 45, "max_per_run": 2,
         "crop_anchor": "center", "creator": "moistcr1tikal"},
        {"platform": "youtube", "url": "https://www.youtube.com/@HasanAbi/videos",
         "type": "transcript", "priority": 1, "max_age_days": 3,
         "target_dur_s": 45, "max_per_run": 2,
         "crop_anchor": "right", "creator": "hasanabi"},
        {"platform": "youtube", "url": "https://www.youtube.com/@Ludwig/videos",
         "type": "transcript", "priority": 1, "max_age_days": 3,
         "target_dur_s": 45, "max_per_run": 2,
         "crop_anchor": "center", "creator": "ludwig"},

        # ── PRIORITY 2: Twitch fan clips (fallback when no YT video today) ───
        # min_views lowered to realistic thresholds — clips take hours to accumulate views
        {"platform": "twitch", "url": "https://www.twitch.tv/moistcr1tikal/clips",
         "type": "channel", "priority": 2, "max_age_days": 3,
         "min_dur_s": 20, "max_dur_s": 60, "max_per_run": 4,
         "crop_anchor": "center", "min_views": 200},
        {"platform": "twitch", "url": "https://www.twitch.tv/hasanabi/clips",
         "type": "channel", "priority": 2, "max_age_days": 3,
         "min_dur_s": 20, "max_dur_s": 60, "max_per_run": 4,
         "crop_anchor": "right", "min_views": 500},
        {"platform": "twitch", "url": "https://www.twitch.tv/ludwig/clips",
         "type": "channel", "priority": 2, "max_age_days": 3,
         "min_dur_s": 20, "max_dur_s": 60, "max_per_run": 4,
         "crop_anchor": "center"},
    ],

    "fomo_highlights": [
        # Shroud: cam bottom-left -> anchor right to keep gameplay on right side
        # min_views raised to 5000 — higher view clips = more likely to be exciting plays, not boring scope/idle moments
        {"platform": "twitch", "url": "https://www.twitch.tv/shroud/clips",
         "type": "channel", "priority": 1, "max_age_days": 7,
         "min_dur_s": 20, "max_dur_s": 45, "max_per_run": 6,
         "crop_anchor": "right", "min_views": 5000},
        # Nickmercs: cam bottom-right -> anchor left to keep gameplay on left side
        {"platform": "twitch", "url": "https://www.twitch.tv/nickmercs/clips",
         "type": "channel", "priority": 1, "max_age_days": 7,
         "min_dur_s": 20, "max_dur_s": 45, "max_per_run": 6,
         "crop_anchor": "left", "min_views": 5000},
        # TimTheTatman: cam bottom-left -> anchor right
        {"platform": "twitch", "url": "https://www.twitch.tv/timthetatman/clips",
         "type": "channel", "priority": 1, "max_age_days": 7,
         "min_dur_s": 20, "max_dur_s": 45, "max_per_run": 6,
         "crop_anchor": "right", "min_views": 5000},
        # YouTube fallbacks
        {"platform": "youtube",
         "url": "https://www.youtube.com/results?search_query=shroud+best+clips+shorts+2025",
         "type": "search", "priority": 3, "max_age_days": 7,
         "min_dur_s": 20, "max_dur_s": 60, "crop_anchor": "center"},
        {"platform": "youtube",
         "url": "https://www.youtube.com/results?search_query=nickmercs+highlights+shorts+2025",
         "type": "search", "priority": 3, "max_age_days": 7,
         "min_dur_s": 20, "max_dur_s": 60, "crop_anchor": "center"},
    ],
}

# Alias so imports can use either name
SOURCES = CHANNEL_SOURCES
