"""
Compatibility shim - re-exports from db_queue for backward compatibility.
The actual implementation is in db_queue.py
"""

from publisher.db_queue import (
    add_publish_job,
    get_next_job,
    save_early_url,
    get_early_url,
    update_job_status,
    fail_job,
    get_db_connection,
)

__all__ = [
    "add_publish_job",
    "get_next_job",
    "save_early_url",
    "get_early_url",
    "update_job_status",
    "fail_job",
    "get_db_connection",
]
