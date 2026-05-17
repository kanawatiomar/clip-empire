"""
service/intake.py — CLI entry point for submitting clips into the intake pipeline.

Usage:
    python -m service.intake --url https://youtube.com/watch?v=... --client acme_corp
    python -m service.intake --file C:/clips/rawclip.mp4 --client acme_corp
"""
import argparse
import sys
import os
from service.job_manager import ensure_client, create_job, update_job_status
from service.pipeline import run_pipeline


def main():
    parser = argparse.ArgumentParser(
        description="Submit a video URL or local file into the clip intake pipeline."
    )
    parser.add_argument("--url", help="YouTube/web URL to ingest")
    parser.add_argument("--file", help="Local video file path to ingest")
    parser.add_argument("--client", required=True, help="Client ID (slug, e.g. acme_corp)")
    parser.add_argument("--client-name", default="", help="Human display name for the client (first run only)")
    parser.add_argument("--dry-run", action="store_true", help="Create job record but skip actual processing")
    args = parser.parse_args()

    if not args.url and not args.file:
        print("[intake] ERROR: Provide --url or --file", file=sys.stderr)
        sys.exit(1)

    if args.url and args.file:
        print("[intake] ERROR: Provide --url OR --file, not both", file=sys.stderr)
        sys.exit(1)

    # Ensure client row exists
    ensure_client(args.client, args.client_name)

    # Determine source
    if args.url:
        source_type = "url"
        source_path = args.url
    else:
        source_path = os.path.abspath(args.file)
        if not os.path.exists(source_path):
            print(f"[intake] ERROR: File not found: {source_path}", file=sys.stderr)
            sys.exit(1)
        source_type = "file"

    # Create job
    job_id = create_job(args.client, source_type, source_path)
    print(f"[intake] Job created: {job_id}")

    if args.dry_run:
        print("[intake] Dry-run mode — skipping extraction pipeline.")
        return

    # Run pipeline
    print(f"[intake] Running extraction pipeline for job {job_id}...")
    try:
        candidates = run_pipeline(job_id, source_type, source_path, args.client)
        print(f"[intake] Done. {len(candidates)} clip candidates generated.")
        for c in candidates:
            print(f"  - {c['candidate_id']}: {c.get('title', '(no title)')}")
    except Exception as e:
        update_job_status(job_id, "failed", str(e))
        print(f"[intake] FAILED: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
