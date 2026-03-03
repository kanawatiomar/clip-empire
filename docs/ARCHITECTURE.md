# Clip Empire — Architecture

## Design principles
- **Accounts are data, workers are dumb:** DB is source of truth; workers are stateless.
- **Isolation:** 1 Chrome profile per channel/account.
- **Low concurrency, high throughput:** never run 50 browsers; run 2–6 workers.
- **Feedback loop:** analytics drives creative changes automatically.

---

## Main components
### 1) Account system (already built)
Location: `accounts/`
- `channel_definitions.py` — canonical channel list + metadata
- `schema.py` — Account dataclass/schema
- `db.py` — SQLite + encryption
- `manager.py` — CLI to list/update/export
- `setup_wizard.py` — saves credentials + creates profile folder
- `lockdown.py` — post-login 2FA + backup codes automation

Data:
- `accounts/.master_key` — Fernet master key (BACK UP)
- `accounts/accounts.db` — encrypted credential store
- `profiles/<channel_name>/` — Chrome user-data dirs (not committed)

### 2) Clip pipeline (to implement)
Stages:
1. **Ingest** (download VOD/clip/source)
2. **Detect** (candidate segments scored)
3. **Cut** (trim + silence removal)
4. **Caption** (Whisper tiered models)
5. **Edit** (template pack: overlays + pattern interrupts)
6. **Render** (NVENC)
7. **Package** (platform variants: YT/TikTok/IG)

### 3) Publish system (to implement)
Queue-based publishing:
- `publish_queue` rows include: `channel`, `platform`, `asset_path`, `caption`, `hashtags`, `schedule_time`, `template_version`, `retry_count`.

Workers:
- `upload_worker_youtube.py` (browser automation)
- `upload_worker_tiktok.py` (collector accounts first)
- `upload_worker_instagram.py` (collector accounts first)

### 4) Bot Manager (to implement)
Daily job:
- Pull metrics (manual export or browser scrape until API path exists)
- Compute KPIs (median views, completion proxies)
- Adjust:
  - post volume per channel (ramp up/down)
  - template selection probabilities
  - length targets per category
  - clip scoring thresholds

---

## Concurrency governor
Hard caps to avoid bans + resource exhaustion:
- Max open browsers: 2–6 (config)
- Max simultaneous renders: 1–2
- Max simultaneous Whisper jobs: 1–2 (depends on VRAM)

---

## Cross-platform strategy: collector accounts
Instead of 50 TikTok + 50 IG on day 1:
- TikTok: ~10 collector accounts
- IG: ~5–8 collector accounts

Later: graduate winners to 1:1 mapping.

---

## Storage layout (canonical)
Repo root: `ventures/clip_empire/`
- `accounts/`
- `profiles/` (local only)
- `docs/`
- `data/` (queues, state)
- `assets/` (template assets: fonts, overlays)
- `renders/` (final outputs)
- `logs/`

---

## What changes in the future (plan for it)
- UI selectors on YouTube/TikTok/IG will break → isolate selectors per platform module.
- Add a second machine (scale-out) → queues become shared (Redis/Postgres) and workers become distributed.
- Monetization rules shift → bot-manager thresholds and identity strategy adapt.
