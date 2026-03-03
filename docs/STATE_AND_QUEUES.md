# Clip Empire — State & Queues (Canonical Schemas)

This doc defines the *source-of-truth* schemas for how the system stores state and moves work between stages.

## Principles
- **Queues are append-only + idempotent.** Workers must be safe to restart.
- **DB is truth.** Queue items reference DB ids/paths; workers write results back.
- **Retry is explicit.** Every failure increments retry + backoff.

---

## Storage options
### Phase 1 (single machine)
- SQLite (same pattern as `accounts/accounts.db` but separate file recommended): `data/clip_empire.db`

### Phase 2 (multi-machine)
- Postgres for state + Redis for queues (or Postgres-only with SKIP LOCKED)

---

## Directory layout (runtime)
- `data/` — sqlite + queue exports + state snapshots
- `ingest/` — raw downloads (vods, source clips)
- `work/` — intermediates
- `renders/` — final platform-ready files
- `logs/` — worker logs

---

## Entities (tables)
Below is the recommended SQLite schema (conceptual). Exact DDL can be generated later.

### 1) `channels`
Represents a publishing identity (YouTube channel), linked to an `accounts` entry.

Fields:
- `channel_name` (PK) — slug, e.g. `market_meltdowns`
- `category` — finance/business/tech/truecrime/fitness/food/experimental
- `status` — active|ramping|paused|dead
- `daily_target` — int (3/5/10)
- `format_pack_version` — string (e.g. `finance_v1`)
- `created_at`, `updated_at`

### 2) `sources`
Tracks input content sources.

Fields:
- `source_id` (PK)
- `type` — streamer_vod|youtube_video|original
- `url` — canonical URL if applicable
- `creator` — string
- `title` — string
- `download_path` — file path
- `duration_s` — number
- `ingested_at`
- `notes`

### 3) `segments`
Candidate segments cut/scored from sources.

Fields:
- `segment_id` (PK)
- `source_id` (FK)
- `start_ms`, `end_ms`
- `hook_score` (0-1)
- `story_score` (0-1)
- `novelty_score` (0-1)
- `category_fit_score` (0-1)
- `overall_score` (0-1)
- `language` (optional)
- `transcript_path` (optional)
- `created_at`

### 4) `clip_assets`
A “master clip” produced from a segment (before platform variants).

Fields:
- `clip_id` (PK)
- `segment_id` (FK)
- `channel_name` (FK) — intended channel
- `clip_type` — clipped|remixed|original
- `template_id` — e.g. `finance_pnl_shock`
- `template_version` — e.g. `finance_v1`
- `target_length_s`
- `master_render_path`
- `audio_lufs` (optional)
- `qa_status` — pass|fail|unknown
- `created_at`

### 5) `platform_variants`
Platform-specific render outputs derived from `clip_assets`.

Fields:
- `variant_id` (PK)
- `clip_id` (FK)
- `platform` — youtube|tiktok|instagram
- `render_path`
- `caption_text`
- `hashtags` (string or JSON)
- `first_frame_hook` (optional)
- `created_at`

### 6) `publish_jobs`
The canonical queue for publishing.

Fields:
- `job_id` (PK)
- `variant_id` (FK)
- `platform`
- `channel_name` (FK) — for youtube identity; for TikTok/IG may map to collector account id
- `publisher_account` — string (e.g. `tiktok_collector_finance_01`)
- `schedule_at` (datetime)
- `status` — queued|running|succeeded|failed|paused
- `attempts` — int
- `last_error` — text
- `next_retry_at` — datetime
- `created_at`, `updated_at`

### 7) `publish_results`
Immutable log of every publish attempt.

Fields:
- `result_id` (PK)
- `job_id` (FK)
- `started_at`, `finished_at`
- `success` (bool)
- `post_url` (nullable)
- `platform_post_id` (nullable)
- `error_class` — captcha|ui_change|network|rate_limit|unknown
- `error_detail` — text

### 8) `metrics_daily`
Daily performance snapshots (per platform, per channel).

Fields:
- `date` (PK part)
- `platform` (PK part)
- `channel_name` (PK part)
- `posts` — int
- `views_median`, `views_total`
- `likes_total`, `comments_total`, `shares_total`, `saves_total` (if available)
- `avg_view_duration_s` (if available)
- `notes`

---

## Queue semantics
### Publish job selection
Workers should select jobs using:
- `status = queued`
- `schedule_at <= now()`
- `next_retry_at IS NULL OR next_retry_at <= now()`

Locking strategy:
- SQLite: optimistic update (set status=running where status=queued)
- Postgres: `FOR UPDATE SKIP LOCKED`

### Retry/backoff
- attempts 1–3: exponential backoff (e.g. 2m, 10m, 45m)
- after 3 failures: pause job + flag channel/account for review

---

## Cross-posting model (collector accounts)
Instead of 50 TikTok + 50 IG:
- `publisher_account` chooses one of a smaller set of collector identities.
- Mapping logic lives in Bot Manager config:
  - Finance → `tiktok_fin_01..03`
  - Tech → `tiktok_tech_01..02`
  - etc.

Graduation:
- When a category/identity proves winners, create 1:1 publisher accounts and update mapping.

---

## Minimal JSON representation (for exports/debug)
If we want to export a publish job as JSON:

```json
{
  "job_id": "uuid",
  "platform": "youtube",
  "channel_name": "market_meltdowns",
  "publisher_account": "youtube:market_meltdowns",
  "render_path": "renders/youtube/market_meltdowns/2026-03-02/clip_001.mp4",
  "caption_text": "He panic sold the bottom…",
  "hashtags": ["#stocks", "#trading"],
  "schedule_at": "2026-03-03T18:12:00Z",
  "attempts": 0
}
```

---

## Future-proofing notes
- Keep **platform workers** isolated so UI changes only break one module.
- Store template versions so we can correlate performance with edits.
- Keep publish results immutable for audit + debugging.
