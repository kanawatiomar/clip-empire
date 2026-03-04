# Phase 1 PR Plan: Client Intake + Auto-Extraction

This plan implements the multi-tenant intake system without breaking the existing pipeline.

## PR 1: Intake Database & Setup (Phase 1A)
**Goal:** Create the basic tables to track clients, jobs, and generated clips.
- `data/schema.py`: add schemas for `clients`, `intake_jobs`, `clip_candidates`
- `data/migrate.py`: add idempotent alter-table / create-table logic
- `service/db.py`: basic helper for connection/logging
- **Commit:** `feat(intake): add multi-tenant db schema and migrations for client jobs`

## PR 2: Intake CLI Skeletons (Phase 1B)
**Goal:** Command-line entry points to start an extraction job.
- `service/intake.py`: argparse logic to handle `--url`, `--file`, and `--client`
- `service/job_manager.py`: logic to insert record into `intake_jobs` and initialize state
- **Commit:** `feat(intake): build CLI entry point to accept local files or URLs`

## PR 3: Auto-Extraction Pipeline (Phase 1C)
**Goal:** The engine that chops long videos into Shorts candidates.
- `service/extract/ingest.py`: download url via yt-dlp or copy file to `input/clients/`
- `service/extract/analyze.py`: basic scene/audio logic + Whisper transcribe scaffold
- `service/extract/generate.py`: chop into 10–30 candidates, save records to `clip_candidates`
- `service/pipeline.py`: glue them together
- **Commit:** `feat(intake): build auto-extraction pipeline scaffold for candidate generation`

## PR 4: Review Queue & Handoff (Phase 1D)
**Goal:** Export choices to a JSON feed, allow approval, push to existing publisher queue.
- `service/review_queue.py`: JSON export logic / basic approval command
- `service/handoff.py`: map approved `clip_candidates` straight into `publish_jobs` by passing them to `QueueWriter.enqueue()`
- **Commit:** `feat(intake): add JSON review queue and integration with publish_jobs`

## Execution Commands
Once merged, you'll run:
```powershell
python -m service.intake --url https://youtube.com/watch... --client test_client_1
python -m service.review --export output/client1_review.json
python -m service.review --approve candidate_id_123
```
