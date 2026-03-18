"""
service/job_manager.py — Create and update intake jobs in the DB.
"""
import uuid
from datetime import datetime, timezone
from service.db import get_connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_job(client_id: str, source_type: str, source_path: str) -> str:
    """Insert a new intake_job row. Returns job_id."""
    job_id = str(uuid.uuid4())
    now = _now()
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO intake_jobs (job_id, client_id, source_type, source_path, status, created_at, updated_at)
            VALUES (?, ?, ?, ?, 'pending', ?, ?)
            """,
            (job_id, client_id, source_type, source_path, now, now),
        )
        conn.execute(
            """
            INSERT INTO intake_audit (audit_id, job_id, action, details, at)
            VALUES (?, ?, 'created', ?, ?)
            """,
            (str(uuid.uuid4()), job_id, f"source_type={source_type}", now),
        )
    print(f"[job_manager] Created job {job_id} for client '{client_id}' ({source_type})")
    return job_id


def update_job_status(job_id: str, status: str, details: str = ""):
    now = _now()
    with get_connection() as conn:
        conn.execute(
            "UPDATE intake_jobs SET status=?, updated_at=? WHERE job_id=?",
            (status, now, job_id),
        )
        conn.execute(
            """
            INSERT INTO intake_audit (audit_id, job_id, action, details, at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), job_id, f"status→{status}", details, now),
        )


def ensure_client(client_id: str, display_name: str = ""):
    """Insert client row if it doesn't exist yet."""
    now = _now()
    name = display_name or client_id
    with get_connection() as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO clients (client_id, display_name, created_at, updated_at)
            VALUES (?, ?, ?, ?)
            """,
            (client_id, name, now, now),
        )
