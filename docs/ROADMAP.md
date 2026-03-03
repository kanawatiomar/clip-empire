# Clip Empire — Roadmap

## Phase 0 (now): Foundations
- [x] Account DB + encryption + setup wizard
- [x] Lockdown automation scaffold
- [x] Master plan + architecture docs

## Phase 1: Packaging pipeline (production)
- [ ] Standard clip object + metadata schema (`ClipAsset`)
- [ ] Render pipeline (NVENC) + audio chain presets
- [ ] Tiered captioning (fast default, best for high-score)
- [ ] Category format packs (3–5 templates/category)
- [ ] QA checks (black frames, loudness, caption margins)

## Phase 2: YouTube publish automation
- [ ] `publish_queue` (SQLite first)
- [ ] YouTube Studio uploader worker (per-profile)
- [ ] Concurrency governor + retries/backoff
- [ ] Upload verification (processed/scheduled/public)

## Phase 3: Cross-posting (collector accounts)
- [ ] TikTok uploader worker (10 collectors)
- [ ] Instagram Reels uploader worker (5–8 collectors)
- [ ] Stagger schedule + per-platform variants

## Phase 4: Bot Manager (optimization loop)
- [ ] Daily analytics ingestion (browser scrape/export until API path)
- [ ] Auto ramp policy (3/day → 5/day → 10/day)
- [ ] Template weighting adjustments based on KPIs
- [ ] Dead-channel throttling + slot reallocation

## Phase 5: Scale-out
- [ ] Move queues/state to Redis/Postgres
- [ ] Multi-machine workers
- [ ] Central dashboard + alerting
