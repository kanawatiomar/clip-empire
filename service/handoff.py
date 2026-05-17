"""
service/handoff.py — Move approved clip candidates into publish_jobs.

Usage:
    python -m service.handoff --channel market_meltdowns
    python -m service.handoff --channel market_meltdowns --schedule-at "2026-03-10T15:00:00"
"""
import argparse
import json
from datetime import datetime, timezone, timedelta

from service.db import get_connection
from publisher.queue import add_publish_job


def handoff_approved(channel_name: str, schedule_at: str = None, platform: str = "youtube"):
    """
    Find all approved clip_candidates not yet handed off and enqueue them
    as publish_jobs for the given channel.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT * FROM clip_candidates WHERE status='approved'
            ORDER BY created_at ASC
            """,
        ).fetchall()

    if not rows:
        print("[handoff] No approved candidates to hand off.")
        return []

    # Default schedule: 1 hour from now
    if not schedule_at:
        schedule_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

    handed_off = []
    for row in rows:
        c = dict(row)
        hashtags = json.loads(c.get("hashtags") or "[]")
        hashtag_str = " ".join(hashtags)

        job_id = add_publish_job(
            variant_id=None,
            platform=platform,
            channel_name=channel_name,
            publisher_account=channel_name,
            schedule_at=schedule_at,
            caption_text=c.get("title", "") + "\n\n" + c.get("description", ""),
            hashtags=hashtag_str,
            render_path=c["clip_path"],
        )

        # Mark as published
        with get_connection() as conn:
            conn.execute(
                "UPDATE clip_candidates SET status='published' WHERE candidate_id=?",
                (c["candidate_id"],),
            )

        print(f"[handoff] Queued {c['candidate_id']} → publish_job {job_id} on {channel_name}")
        handed_off.append(job_id)

    return handed_off


def main():
    parser = argparse.ArgumentParser(description="Hand off approved clip candidates to publish queue")
    parser.add_argument("--channel", required=True, help="Target channel name (e.g. market_meltdowns)")
    parser.add_argument("--schedule-at", help="ISO datetime for publish (UTC). Defaults to 1h from now.")
    parser.add_argument("--platform", default="youtube", help="Platform (default: youtube)")
    args = parser.parse_args()

    jobs = handoff_approved(args.channel, args.schedule_at, args.platform)
    print(f"[handoff] {len(jobs)} publish jobs created.")


if __name__ == "__main__":
    main()
