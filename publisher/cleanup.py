"""
cleanup.py — Delete render files for already-succeeded publish jobs.

Run once to clear the existing backlog, or periodically to stay lean.
Safe to run any time — only touches files belonging to jobs marked 'succeeded'.

Usage:
    python publisher/cleanup.py           # dry run (preview only)
    python publisher/cleanup.py --delete  # actually delete files
"""

import os
import sys
import sqlite3
from datetime import datetime

DATABASE_PATH = "data/clip_empire.db"


def cleanup_succeeded_renders(dry_run: bool = True) -> None:
    if not os.path.exists(DATABASE_PATH):
        print(f"DB not found: {DATABASE_PATH}")
        return

    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT job_id, channel_name, render_path, updated_at FROM publish_jobs "
        "WHERE status = 'succeeded' AND render_path IS NOT NULL"
    ).fetchall()
    conn.close()

    total_bytes = 0
    deleted = 0
    missing = 0
    skipped = 0

    print(f"{'[DRY RUN] ' if dry_run else ''}Scanning {len(rows)} succeeded jobs...\n")

    for row in rows:
        path = row["render_path"]
        if not path:
            continue
        if os.path.exists(path):
            size = os.path.getsize(path)
            total_bytes += size
            if dry_run:
                print(f"  WOULD DELETE  {path}  ({size / 1_000_000:.1f} MB)  [{row['channel_name']}]")
                skipped += 1
            else:
                try:
                    os.remove(path)
                    print(f"  DELETED  {path}  ({size / 1_000_000:.1f} MB)  [{row['channel_name']}]")
                    deleted += 1
                except Exception as e:
                    print(f"  ERROR deleting {path}: {e}")
        else:
            missing += 1

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Summary:")
    print(f"  Jobs scanned:    {len(rows)}")
    print(f"  Files found:     {deleted + skipped}")
    print(f"  Already gone:    {missing}")
    if dry_run:
        print(f"  Would free:      {total_bytes / 1_000_000:.1f} MB")
        print(f"\nRun with --delete to actually remove files.")
    else:
        print(f"  Deleted:         {deleted}")
        print(f"  Freed:           {total_bytes / 1_000_000:.1f} MB")


if __name__ == "__main__":
    dry_run = "--delete" not in sys.argv
    cleanup_succeeded_renders(dry_run=dry_run)
