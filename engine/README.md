# Clip Empire Engine (Custom 50-Account Pipeline)

Purpose-built content engine for the Clip Empire system (not reused from old clip engines).

## What it does

1. **Ingest** source clips from multi-platform sources (YouTube/TikTok/Reddit/Twitter via `yt-dlp`)
2. **Deduplicate globally** so a source clip is never reused across channels
3. **Transform** each clip:
   - 9:16 conversion (blurred background for landscape)
   - Whisper captions (GPU if available, CPU fallback)
   - Hook + CTA overlays per niche
   - Final encode (NVENC if available)
4. **Safety filter** removes policy-risk clips before transforms
5. **Queue** for publish via `publish_jobs` (consumed by `publisher/youtube_worker.py`)

## Entry point

```bash
python -m engine.cli --channel market_meltdowns
python -m engine.cli --all --count 1
python -m engine.cli --all --trend-radar
python -m engine.cli --status
```

## Files

- `engine/config/sources.py` — source config per channel
- `engine/config/templates.py` — niche hooks/CTAs/hashtags/titles
- `engine/ingest/ytdlp.py` — downloader
- `engine/ingest/dedup.py` — global dedup tracker (`source_clips` table)
- `engine/ingest/trend_radar.py` — optional trend signal → source expansion
- `engine/ingest/safety.py` — policy keyword pre-filter
- `engine/transform/crop.py` — 9:16 transform
- `engine/transform/caption.py` — Whisper → ASS subtitles
- `engine/transform/overlay.py` — text overlays
- `engine/transform/encode.py` — final render
- `engine/scheduler/runner.py` — orchestrator
- `engine/scheduler/queue_writer.py` — publish queue bridge

## Notes

- This is designed for scale to 50 channels and queue-native publishing.
- Existing worker (`publisher/youtube_worker.py`) already supports full end-to-end upload with real URL capture.
- Keep source configs fresh and platform-safe.
