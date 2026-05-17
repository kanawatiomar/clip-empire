"""
service/pipeline.py — Orchestrates the full intake → extract → candidate pipeline.
Called by service/intake.py after a job is created.
"""
import uuid
import json
from datetime import datetime, timezone

from service.db import get_connection
from service.job_manager import update_job_status
from service.extract.ingest import get_source_video
from service.extract.analyze import analyze_video
from service.extract.generate import generate_candidates


def _save_candidates_to_db(candidates: list[dict]):
    """Persist generated candidates into the clip_candidates table."""
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        for c in candidates:
            conn.execute(
                """
                INSERT OR IGNORE INTO clip_candidates
                    (candidate_id, job_id, clip_path, title, description, hashtags, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    c["candidate_id"],
                    c["job_id"],
                    c["clip_path"],
                    c.get("title", ""),
                    c.get("description", ""),
                    json.dumps(c.get("hashtags", [])),
                    "pending_review",
                    now,
                ),
            )


def run_pipeline(job_id: str, source_type: str, source_path: str, client_id: str, niche: str = "default") -> list[dict]:
    """
    Full pipeline:
      1. Download/locate source video
      2. Detect scenes + transcribe
      3. Generate 9:16 clip candidates
      4. Persist to DB
      5. Return candidate list
    """
    update_job_status(job_id, "analyzing")

    try:
        # Step 1: Ingest
        video_path = get_source_video(source_type, source_path, job_id)
        print(f"[pipeline] Source video: {video_path}")

        # Step 2: Analyze
        segments = analyze_video(video_path, job_id)
        print(f"[pipeline] Segments: {len(segments)}")

        update_job_status(job_id, "generating")

        # Step 3: Generate candidates
        candidates = generate_candidates(video_path, segments, job_id, client_id, niche)

        # Step 4: Save to DB
        _save_candidates_to_db(candidates)

        update_job_status(job_id, "done", f"{len(candidates)} candidates")
        return candidates

    except Exception as e:
        update_job_status(job_id, "failed", str(e))
        raise
