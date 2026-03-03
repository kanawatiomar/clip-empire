"""Ops dashboard status exporter."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path


def export_status(db_path: str = "data/clip_empire.db", out_path: str = "output/ops_status.json") -> str:
    conn = sqlite3.connect(db_path)
    payload = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "jobs": {},
        "channels_active": 0,
    }

    row = conn.execute("SELECT COUNT(1) FROM channels WHERE status = 'active'").fetchone()
    payload["channels_active"] = int(row[0] or 0)

    for status in ("queued", "running", "succeeded", "failed"):
        r = conn.execute("SELECT COUNT(1) FROM publish_jobs WHERE status = ?", (status,)).fetchone()
        payload["jobs"][status] = int(r[0] or 0)

    conn.close()
    path = Path(out_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(path)
