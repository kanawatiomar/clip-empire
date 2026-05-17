"""
service/review_queue.py — Export pending clip candidates for human review,
and handle approve/reject actions.

Usage:
    python -m service.review --export output/review.json
    python -m service.review --approve <candidate_id>
    python -m service.review --reject <candidate_id>
    python -m service.review --list
"""
import argparse
import json
import os
import sys
from service.db import get_connection


def list_candidates(status: str = "pending_review") -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT cc.*, ij.client_id, ij.source_path
            FROM clip_candidates cc
            JOIN intake_jobs ij ON cc.job_id = ij.job_id
            WHERE cc.status = ?
            ORDER BY cc.created_at DESC
            """,
            (status,),
        ).fetchall()
    return [dict(r) for r in rows]


def export_review(output_path: str, status: str = "pending_review"):
    candidates = list_candidates(status)
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(candidates, f, indent=2)
    print(f"[review] Exported {len(candidates)} candidates → {output_path}")
    return candidates


def approve_candidate(candidate_id: str):
    with get_connection() as conn:
        conn.execute(
            "UPDATE clip_candidates SET status='approved' WHERE candidate_id=?",
            (candidate_id,),
        )
    print(f"[review] Approved: {candidate_id}")


def reject_candidate(candidate_id: str):
    with get_connection() as conn:
        conn.execute(
            "UPDATE clip_candidates SET status='rejected' WHERE candidate_id=?",
            (candidate_id,),
        )
    print(f"[review] Rejected: {candidate_id}")


def main():
    parser = argparse.ArgumentParser(description="Review clip candidates")
    parser.add_argument("--export", metavar="PATH", help="Export pending candidates to JSON")
    parser.add_argument("--approve", metavar="ID", help="Approve a candidate by ID")
    parser.add_argument("--reject", metavar="ID", help="Reject a candidate by ID")
    parser.add_argument("--list", action="store_true", help="List all pending candidates")
    args = parser.parse_args()

    if args.export:
        export_review(args.export)
    elif args.approve:
        approve_candidate(args.approve)
    elif args.reject:
        reject_candidate(args.reject)
    elif args.list:
        candidates = list_candidates()
        for c in candidates:
            print(f"  {c['candidate_id']}  job={c['job_id']}  title={c['title']}")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
