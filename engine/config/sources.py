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
        # longform: we download their full videos and extract our own highlight
        # (transformative — we pick the peak energy moment, add overlays + captions)
        {"platform": "youtube", "url": "https://www.youtube.com/@GrahamStephan/videos",
         "type": "longform", "priority": 1, "max_age_days": 14,
         "target_dur_s": 40},
        {"platform": "youtube", "url": "https://www.youtube.com/@MeetKevin/videos",
         "type": "longform", "priority": 1, "max_age_days": 7,
         "target_dur_s": 40},
        {"platform": "youtube", "url": "https://www.youtube.com/@AndreiJikh/videos",
         "type": "longform", "priority": 2, "max_age_days": 14,
         "target_dur_s": 40},
        {"platform": "youtube", "url": "https://www.youtube.com/@theplainbagel/videos",
         "type": "longform", "priority": 2, "max_age_days": 14,
         "target_dur_s": 40},
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



    # -- GAMING ----------------------------------------------------------------

    "arc_highlightz": [
        # crop_anchor: where the streamer face/webcam sits in the frame
        #   left   -> crop window shifts left  (webcam bottom-left, action right)
        #   right  -> crop window shifts right (webcam bottom-right, action left)
        #   center -> standard center crop
        {"platform": "twitch", "url": "https://www.twitch.tv/tfue/clips",
         "type": "channel", "priority": 1, "max_age_days": 3,
         "min_dur_s": 20, "max_dur_s": 60, "max_per_run": 8,
         "crop_anchor": "right"},
        {"platform": "twitch", "url": "https://www.twitch.tv/cloakzy/clips",
         "type": "channel", "priority": 1, "max_age_days": 3,
         "min_dur_s": 20, "max_dur_s": 60, "max_per_run": 8,
         "crop_anchor": "left"},
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
        # Moistcr1tikal / penguinz0: usually centered cam, reaction-heavy
        {"platform": "twitch", "url": "https://www.twitch.tv/moistcr1tikal/clips",
         "type": "channel", "priority": 1, "max_age_days": 3,
         "min_dur_s": 20, "max_dur_s": 60, "max_per_run": 6,
         "crop_anchor": "center"},
        # HasanAbi: cam on left side -> anchor right
        {"platform": "twitch", "url": "https://www.twitch.tv/hasanabi/clips",
         "type": "channel", "priority": 1, "max_age_days": 3,
         "min_dur_s": 20, "max_dur_s": 60, "max_per_run": 6,
         "crop_anchor": "right"},
        # Ludwig: usually centered
        {"platform": "twitch", "url": "https://www.twitch.tv/ludwig/clips",
         "type": "channel", "priority": 1, "max_age_days": 3,
         "min_dur_s": 20, "max_dur_s": 60, "max_per_run": 6,
         "crop_anchor": "center"},
        # YouTube fallbacks
        {"platform": "youtube",
         "url": "https://www.youtube.com/results?search_query=penguinz0+funniest+moments+shorts+2025",
         "type": "search", "priority": 3, "max_age_days": 7,
         "min_dur_s": 20, "max_dur_s": 60, "crop_anchor": "center"},
        {"platform": "youtube",
         "url": "https://www.youtube.com/results?search_query=hasanabi+funny+clips+shorts+2025",
         "type": "search", "priority": 3, "max_age_days": 7,
         "min_dur_s": 20, "max_dur_s": 60, "crop_anchor": "center"},
    ],

    "fomo_highlights": [
        # Shroud: cam bottom-left -> anchor right to keep gameplay on right side
        {"platform": "twitch", "url": "https://www.twitch.tv/shroud/clips",
         "type": "channel", "priority": 1, "max_age_days": 3,
         "min_dur_s": 20, "max_dur_s": 60, "max_per_run": 6,
         "crop_anchor": "right"},
        # Nickmercs: cam bottom-right -> anchor left to keep gameplay on left side
        {"platform": "twitch", "url": "https://www.twitch.tv/nickmercs/clips",
         "type": "channel", "priority": 1, "max_age_days": 3,
         "min_dur_s": 20, "max_dur_s": 60, "max_per_run": 6,
         "crop_anchor": "left"},
        # TimTheTatman: cam bottom-left -> anchor right
        {"platform": "twitch", "url": "https://www.twitch.tv/timthetatman/clips",
         "type": "channel", "priority": 1, "max_age_days": 3,
         "min_dur_s": 20, "max_dur_s": 60, "max_per_run": 6,
         "crop_anchor": "right"},
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
