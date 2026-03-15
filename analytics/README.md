# YouTube Analytics Sync

Real-time view count synchronization from YouTube Data API v3 for the Clip Empire Dashboard.

## Overview

This system fetches YouTube view counts for published Shorts and updates the database with real analytics. It's designed to replace the hardcoded view counts with actual data from YouTube.

## Architecture

```
auth_setup.py → OAuth token generation → tokens/{channel}.pickle
sync_all.py → Batch sync for all channels
youtube_analytics.py → Per-channel sync (queries YouTube API, updates DB)
```

## Setup Steps

### 1. Install Dependencies

```bash
cd analytics
python -m pip install -r requirements.txt
```

Or for Python 3.3+:
```bash
py -3 -m pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client
```

### 2. Copy Credentials

Place `client_secrets.json` files in the `analytics/` directory:

- **For arc_highlightz, fomo_highlights, market_meltdowns:**
  Copy from clip_engine project and rename to `client_secrets_main.json`

- **For viral_recaps:**
  Copy from clip_engine_viral project and rename to `client_secrets_viral.json`

These are in your ventures/clip_engine folders. **Do NOT commit these to git** (they contain secrets).

### 3. Setup OAuth Per Channel

For each channel, run:

```bash
python auth_setup.py <channel_name>
```

Example:
```bash
python auth_setup.py arc_highlightz
python auth_setup.py fomo_highlights
python auth_setup.py market_meltdowns
python auth_setup.py viral_recaps
```

This will:
1. Open your browser for Google OAuth consent
2. Save a token file to `tokens/{channel}.pickle`
3. Ready the channel for analytics sync

## Usage

### Manual Sync

Sync a single channel:
```bash
python youtube_analytics.py arc_highlightz
```

Sync all configured channels:
```bash
python sync_all.py
```

### Scheduled Sync (Windows Task Scheduler)

To set up hourly automatic sync:

```powershell
# Run as Administrator
.\create_scheduler_task.ps1
```

This creates a Task Scheduler task:
- **Name:** ClipEmpire-AnalyticsSync
- **Path:** \ClipEmpire\ClipEmpire-AnalyticsSync
- **Schedule:** Every hour
- **Action:** Runs `sync_all.py`

To manually trigger the task:
```powershell
Start-ScheduledTask -TaskName ClipEmpire-AnalyticsSync
```

To view task details:
```powershell
Get-ScheduledTask -TaskName ClipEmpire-AnalyticsSync
```

## How It Works

### Database Updates

1. **publish_results table:**
   - Adds/updates `views` column with YouTube Shorts view count
   - Matches videos by extracting video ID from `post_url`

2. **source_clips table:**
   - Updates `view_count` if the video is linked via platform_variants

### View Sources

The system prioritizes YouTube published video views:

- **YouTube Shorts views:** From `publish_results.views` (YouTube Data API)
- **Source clip views:** From `source_clips.view_count` (fallback)

Dashboard functions use YouTube views when available, falling back to source views.

## Supported Channels

```
arc_highlightz      → clipengine-488422 project
fomo_highlights     → clipengine-488422 project
market_meltdowns    → clipengine-488422 project
viral_recaps        → clipengine_viral project
```

## Video ID Extraction

The system supports multiple YouTube URL formats:

- `youtube.com/shorts/VIDEO_ID` ✓
- `youtube.com/watch?v=VIDEO_ID` ✓
- `youtu.be/VIDEO_ID` ✓

## Troubleshooting

### "Token not found for channel"
```bash
python auth_setup.py <channel_name>
```

### "No YouTube videos found"
Check that `post_url` in publish_results contains youtube.com URLs.

### "ModuleNotFoundError"
Ensure dependencies are installed:
```bash
python -m pip install -r requirements.txt
```

### Task Scheduler Issues
Verify Python path in `create_scheduler_task.ps1` matches your installation.

## Files

```
analytics/
├── auth_setup.py              # OAuth setup per channel
├── youtube_analytics.py        # Core sync logic
├── sync_all.py                # Batch sync all channels
├── create_scheduler_task.ps1  # Windows Task Scheduler setup
├── requirements.txt            # Python dependencies
├── tokens/                     # Saved OAuth tokens (auto-created)
│   └── {channel}.pickle
└── client_secrets_*.json       # OAuth credentials (not in git)
```

## Dashboard Integration

The dashboard (`dashboard/generate_data.py`) now reads from:

- **get_recent_clips()** → `publish_results.views`
- **get_hall_of_fame()** → YouTube views (preferred) or source views
- **get_channel_leaderboard()** → Combined YouTube + source views

All view counts are formatted with compact notation (K/M suffixes).
