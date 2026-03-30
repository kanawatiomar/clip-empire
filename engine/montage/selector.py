"""Select clips for montage compilation from the clip_empire database.

Picks already-published Shorts (used_at IS NOT NULL) that haven't been
included in a montage yet, ordered by view_count descending.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
from pathlib import Path
from typing import List

# ── ffprobe path (mirrors encode.py) ────────────────────────────────────────
_FFMPEG_BIN_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / (
    "Microsoft/WinGet/Packages/"
    "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/"
    "ffmpeg-8.1-full_build/bin"
)
FFPROBE_BIN = str(_FFMPEG_BIN_DIR / "ffprobe.exe") if (_FFMPEG_BIN_DIR / "ffprobe.exe").exists() else "ffprobe"

DEFAULT_DB = str(Path(__file__).resolve().parents[2] / "clip_empire.db")


def _ensure_montage_column(conn: sqlite3.Connection) -> None:
    """Add montage_used column to source_clips if it doesn't exist."""
    cursor = conn.execute("PRAGMA table_info(source_clips)")
    columns = {row[1] for row in cursor.fetchall()}
    if "montage_used" not in columns:
        conn.execute(
            "ALTER TABLE source_clips ADD COLUMN montage_used INTEGER DEFAULT 0"
        )
        conn.commit()
        print("[selector] Added montage_used column to source_clips")


def _probe_duration(path: str) -> float | None:
    """Get video duration in seconds via ffprobe."""
    try:
        result = subprocess.run(
            [
                FFPROBE_BIN, "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                path,
            ],
            capture_output=True, text=True, timeout=15,
        )
        return float(result.stdout.strip())
    except Exception:
        return None


def select_montage_clips(
    channel: str,
    db_path: str = DEFAULT_DB,
    target_seconds: float = 480,
) -> list[dict]:
    """Return clips for a montage, filling up to *target_seconds* total.

    Selection criteria:
      - Belong to *channel*
      - Have a render_path that exists on disk (via platform_variants)
      - Already published as Shorts (source_clips.used_at IS NOT NULL)
      - Not yet used in a montage (montage_used IS NULL or 0)
      - Ordered by view_count DESC

    Each returned dict has keys:
        clip_id, title, creator, view_count, render_path, duration_s
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    _ensure_montage_column(conn)

    rows = conn.execute(
        """
        SELECT sc.clip_id, sc.title, sc.creator, sc.view_count,
               pv.render_path
        FROM source_clips sc
        JOIN platform_variants pv ON pv.clip_id = sc.clip_id
        WHERE sc.channel_name = ?
          AND sc.used_at IS NOT NULL
          AND (sc.montage_used IS NULL OR sc.montage_used = 0)
          AND pv.render_path IS NOT NULL
        ORDER BY sc.view_count DESC
        """,
        (channel,),
    ).fetchall()

    selected: list[dict] = []
    total_dur = 0.0

    for row in rows:
        rpath = row["render_path"]
        if not Path(rpath).exists():
            continue

        dur = _probe_duration(rpath)
        if dur is None or dur < 3:
            continue

        if total_dur + dur > target_seconds * 1.15:
            # Allow slight overshoot but not too much
            if total_dur >= target_seconds * 0.8:
                break
            continue

        selected.append({
            "clip_id": row["clip_id"],
            "title": row["title"],
            "creator": row["creator"],
            "view_count": row["view_count"],
            "render_path": rpath,
            "duration_s": dur,
        })
        total_dur += dur

        if total_dur >= target_seconds:
            break

    conn.close()
    print(f"[selector] Selected {len(selected)} clips, ~{total_dur:.0f}s total for {channel}")
    return selected


def mark_montage_used(clip_ids: list[str], db_path: str = DEFAULT_DB) -> None:
    """Mark clips as used in a montage so they aren't re-selected."""
    if not clip_ids:
        return
    conn = sqlite3.connect(db_path)
    conn.executemany(
        "UPDATE source_clips SET montage_used = 1 WHERE clip_id = ?",
        [(cid,) for cid in clip_ids],
    )
    conn.commit()
    conn.close()
    print(f"[selector] Marked {len(clip_ids)} clips as montage_used")
