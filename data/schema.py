
import sqlite3
from typing import Optional, List, Dict
from datetime import datetime

DATABASE_PATH = "data/clip_empire.db"

def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()

    # Channels table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            channel_name TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            daily_target INTEGER NOT NULL DEFAULT 3,
            format_pack_version TEXT,
            made_for_kids BOOLEAN NOT NULL DEFAULT 0, -- New field
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # Sources table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sources (
            source_id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            url TEXT,
            creator TEXT,
            title TEXT,
            download_path TEXT,
            duration_s REAL,
            ingested_at TEXT NOT NULL,
            notes TEXT
        )
    """)

    # Segments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS segments (
            segment_id TEXT PRIMARY KEY,
            source_id TEXT NOT NULL,
            start_ms INTEGER NOT NULL,
            end_ms INTEGER NOT NULL,
            hook_score REAL,
            story_score REAL,
            novelty_score REAL,
            category_fit_score REAL,
            overall_score REAL,
            language TEXT,
            transcript_path TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (source_id) REFERENCES sources (source_id)
        )
    """)

    # Clip Assets table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS clip_assets (
            clip_id TEXT PRIMARY KEY,
            segment_id TEXT NOT NULL,
            channel_name TEXT NOT NULL,
            clip_type TEXT NOT NULL,
            template_id TEXT,
            template_version TEXT,
            target_length_s REAL,
            master_render_path TEXT,
            audio_lufs REAL,
            qa_status TEXT NOT NULL DEFAULT 'unknown',
            created_at TEXT NOT NULL,
            FOREIGN KEY (segment_id) REFERENCES segments (segment_id),
            FOREIGN KEY (channel_name) REFERENCES channels (channel_name)
        )
    """)

    # Platform Variants table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS platform_variants (
            variant_id TEXT PRIMARY KEY,
            clip_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            render_path TEXT,
            caption_text TEXT,
            hashtags TEXT, -- Stored as JSON string
            first_frame_hook TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (clip_id) REFERENCES clip_assets (clip_id)
        )
    """)

    # Publish Jobs table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS publish_jobs (
            job_id TEXT PRIMARY KEY,
            variant_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            channel_name TEXT NOT NULL,
            publisher_account TEXT,
            schedule_at TEXT NOT NULL,
            schedule_at_ts INTEGER, -- epoch seconds (UTC). Used for comparisons.
            status TEXT NOT NULL DEFAULT 'queued',
            attempts INTEGER NOT NULL DEFAULT 0,
            last_error TEXT,
            next_retry_at TEXT,
            next_retry_at_ts INTEGER, -- epoch seconds (UTC)
            caption_text TEXT, /* New field */
            hashtags TEXT,    /* New field - stored as JSON string */
            render_path TEXT, /* New field */
            first_frame_hook TEXT, /* New field */
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (variant_id) REFERENCES platform_variants (variant_id),
            FOREIGN KEY (channel_name) REFERENCES channels (channel_name)
        )
    """)

    # Publish Results table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS publish_results (
            result_id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT NOT NULL,
            success BOOLEAN NOT NULL,
            post_url TEXT,
            platform_post_id TEXT,
            error_class TEXT,
            error_detail TEXT,
            FOREIGN KEY (job_id) REFERENCES publish_jobs (job_id)
        )
    """)

    # Metrics Daily table
    cursor.execute("""
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
        )
    """)

    conn.commit()
    conn.close()
    print(f"Database initialized at {DATABASE_PATH}")

if __name__ == '__main__':
    init_db()
