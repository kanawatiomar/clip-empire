"""
service/db.py — Lightweight SQLite connection helper for the intake layer.
"""
import sqlite3
import os

DB_PATH = os.environ.get(
    "CLIP_EMPIRE_DB",
    os.path.join(os.path.dirname(__file__), "..", "data", "clip_empire.db"),
)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(os.path.abspath(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn
