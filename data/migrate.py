"""
data/migrate.py — Idempotent schema migrations for clip_empire.db.
Run this any time to ensure all tables exist without destroying data.
"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "clip_empire.db")


def migrate(db_path: str = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    c = conn.cursor()

    # ── Core tables (already created by data/schema.py) ──────────────────────
    c.executescript("""
        CREATE TABLE IF NOT EXISTS channels (
            channel_name TEXT PRIMARY KEY,
            niche TEXT NOT NULL,
            platform TEXT NOT NULL DEFAULT 'youtube',
            made_for_kids INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS sources (
            source_id TEXT PRIMARY KEY,
            channel_name TEXT NOT NULL,
            platform TEXT NOT NULL,
            handle TEXT NOT NULL,
            url TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (channel_name) REFERENCES channels (channel_name)
        );

        CREATE TABLE IF NOT EXISTS platform_variants (
            variant_id TEXT PRIMARY KEY,
            channel_name TEXT NOT NULL,
            source_clip_hash TEXT,
            render_path TEXT,
            caption_text TEXT,
            hashtags TEXT,
            duration_s REAL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (channel_name) REFERENCES channels (channel_name)
        );

        CREATE TABLE IF NOT EXISTS publish_jobs (
            job_id TEXT PRIMARY KEY,
            variant_id TEXT,
            platform TEXT NOT NULL DEFAULT 'youtube',
            channel_name TEXT NOT NULL,
            publisher_account TEXT,
            schedule_at TEXT,
            caption_text TEXT,
            hashtags TEXT,
            render_path TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (channel_name) REFERENCES channels (channel_name)
        );

        CREATE TABLE IF NOT EXISTS publish_results (
            result_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            post_url TEXT,
            platform_video_id TEXT,
            published_at TEXT,
            status TEXT,
            error_msg TEXT,
            FOREIGN KEY (job_id) REFERENCES publish_jobs (job_id)
        );

        CREATE TABLE IF NOT EXISTS metrics_daily (
            date TEXT NOT NULL,
            platform TEXT NOT NULL,
            channel_name TEXT NOT NULL,
            posts INTEGER,
            views_median INTEGER,
            views_total INTEGER,
            likes_total INTEGER,
            comments_total INTEGER,
            shares_total INTEGER,
            saves_total INTEGER,
            avg_view_duration_s REAL,
            notes TEXT,
            PRIMARY KEY (date, platform, channel_name),
            FOREIGN KEY (channel_name) REFERENCES channels (channel_name)
        );

        CREATE TABLE IF NOT EXISTS source_clips (
            clip_hash TEXT PRIMARY KEY,
            source_url TEXT,
            file_path TEXT,
            duration_s REAL,
            ingested_at TEXT NOT NULL DEFAULT (datetime('now')),
            used_on_channels TEXT
        );
    """)

    # ── Phase 1 Intake tables ─────────────────────────────────────────────────
    c.executescript("""
        CREATE TABLE IF NOT EXISTS clients (
            client_id TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS intake_jobs (
            job_id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            source_type TEXT NOT NULL,   -- 'url' | 'file'
            source_path TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (client_id) REFERENCES clients (client_id)
        );

        CREATE TABLE IF NOT EXISTS clip_candidates (
            candidate_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            clip_path TEXT NOT NULL,
            title TEXT,
            description TEXT,
            hashtags TEXT,   -- JSON array string
            status TEXT NOT NULL DEFAULT 'pending_review',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (job_id) REFERENCES intake_jobs (job_id)
        );

        CREATE TABLE IF NOT EXISTS intake_audit (
            audit_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT,
            at TEXT NOT NULL DEFAULT (datetime('now')),
            FOREIGN KEY (job_id) REFERENCES intake_jobs (job_id)
        );
    """)

    conn.commit()
    conn.close()
    print(f"[migrate] DB ready: {db_path}")


if __name__ == "__main__":
    migrate()

# Alias for backward compat
ensure_schema = migrate
