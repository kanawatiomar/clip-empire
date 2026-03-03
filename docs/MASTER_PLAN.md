# Clip Empire — Master Plan

## North Star
Build a scalable, largely hands-off content operation that can run **50+ YouTube channels** and publish **10 shorts/day/channel** (**500 uploads/day**) while continuously improving content quality via automated feedback loops.

### Core constraints
- **No YouTube Data API dependency** for uploads (browser-based uploads to avoid quota ceilings).
- **NVIDIA GPU required** (CUDA for Whisper/local captioning; NVENC for fast encode).
- **Per-channel Chrome profiles** (persistent login, isolation).
- **Credentials stored locally** (AES-256 via Fernet). Never exfiltrate.

---

## Platform strategy
### Phase 1 (0–90 days): YouTube-first + Collector cross-posting
- **YouTube:** full channel footprint (target 50)
- **TikTok:** **collector accounts** first (recommended: ~10) to reduce ops risk
- **Instagram:** **collector accounts** first (recommended: ~5–8)

**Why collector accounts first:** creating and maintaining 150 accounts (50×3) causes verification/captcha overhead and accelerates bans. Collector accounts let us find winners, then spin out 1:1 accounts later.

### Phase 2 (90–180 days): Graduate winners to 1:1 mapping
When a category/account proves performance (median views, retention, recurring 50k+ hits), create dedicated TikTok/IG identities for those winners.

---

## Output mix (empire-wide)
Daily total = 500 uploads/day.

**60 / 25 / 15 content mix:**
- **60% Clipped** (fast volume): 300/day
- **25% Remixed/Structured** (transformative packaging): 125/day
- **15% Original** (highest long-term moat): 75/day

This mix is enforced by the scheduler/bot-manager, not manually.

---

## Category map (initial 50)
We scale with category-specific format packs (3–5 templates per category) rather than 50 unique aesthetics.

Recommended allocation:
- Finance: 12
- Business: 8
- Tech/AI: 8
- True Crime: 8
- Fitness: 6
- Food: 5
- Experimental: 3

### Proposed 50-channel roster
**Finance (12)**
- Market Meltdowns
- Crypto Confessions
- Rich or Ruined
- Candles & Chaos
- Red Day Reactions
- Margin Call Moments
- Chart Crimes
- Bag Fumbled
- Panic Sell Theater
- Alpha or Delusion
- Degenerate Dividends
- Wall Street Whiplash

**Business (8)**
- Startup Graveyard
- Self Made Clips
- Founder Fails
- Boardroom Breakdown
- Pitch Deck Problems
- Hustle Reality Check
- Business Model Roast
- Deal or Disaster

**Tech/AI (8)**
- AI Did What
- Prompt Panic
- Silicon Slipups
- Robot Reality
- Demo Gone Wrong
- Future Shock Files
- Tech Support Nightmares
- Glitch in the Matrix

**True Crime (8)**
- Cases Unsolved
- Cold Case Countdown
- Missing in Minutes
- Evidence Locker
- 60-Second Casefile
- Unsolved & Unseen
- The Last Known
- Crime Scene Clips

**Fitness (6)**
- Gym Moments
- PR or ER
- Lift Fail Legends
- Built Different Daily
- Trenches of Training
- Swole or Stalled

**Food (5)**
- Kitchen Chaos
- Plate or Pass
- Chef Rage Clips
- Street Food Shock
- Cooked & Confused

**Experimental (3)**
- Unfiltered Clips
- Internet Oddities
- Clip Laboratory

---

## Publishing policy (what the bot enforces)
### Ramp policy (algorithm-friendly)
- **New channels** start at **3/day** for 7–14 days.
- If retention proxies exceed thresholds, ramp to **5/day**, then **10/day**.
- “Dead channels” auto-throttle (don’t waste slots).

### Cross-posting scheduling
Avoid posting the identical clip simultaneously everywhere.
- YouTube: publish first
- TikTok: +2–6 hours
- Instagram: next day

Slight per-platform variation:
- First-frame hook text
- Caption text (1–2 lines)
- Hashtags

---

## Risk controls (must-have at scale)
- **Reused content suppression**: require a minimum transform score for clipped content (overlays, pacing edits, kinetic captions, framing).
- **Creator diversity**: don’t over-farm a single creator across many channels.
- **Per-channel identity**: recurring series names + consistent templates.
- **QA sampling**: auto-check 1–2 clips/channel/day for audio loudness, captions, black frames, glitch cuts.

---

## Next build steps
1. Finalize account creation flow (manual signup + automated lockdown + profile persistence)
2. Implement clip packaging pipeline (encode + captions + overlays)
3. Implement browser upload workers (YouTube first)
4. Add TikTok/IG publishing workers (collector accounts first)
5. Add bot-manager feedback loop (daily analytics → template/mix adjustments)

See: `docs/ARCHITECTURE.md` and `docs/OPS_RUNBOOK.md`.
