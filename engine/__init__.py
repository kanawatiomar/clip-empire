"""Clip Empire Engine — purpose-built content pipeline for 50-channel YouTube Shorts empire.

Stages:
  1. Ingest  — yt-dlp downloads source clips per niche
  2. Dedup   — skip anything already used by any channel
  3. Transform — crop → caption (Whisper) → overlay → encode
  4. Queue   — writes to publish_jobs table for the publisher
"""

__version__ = "1.0.0"
