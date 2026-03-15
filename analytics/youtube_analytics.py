#!/usr/bin/env python3
"""
Fetch YouTube view counts and update the database.
Usage: python youtube_analytics.py arc_highlightz
"""

import sys
import os
import sqlite3
import pickle
import re
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse, parse_qs
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# Channel to credentials mapping
CHANNEL_CREDENTIALS = {
    'arc_highlightz': 'client_secrets_main.json',
    'fomo_highlights': 'client_secrets_main.json',
    'market_meltdowns': 'client_secrets_main.json',
    'viral_recaps': 'client_secrets_viral.json',
}

def extract_video_id(url):
    """Extract YouTube video ID from various URL formats."""
    if not url:
        return None
    
    # youtube.com/shorts/VIDEO_ID
    shorts_match = re.search(r'youtube\.com/shorts/([a-zA-Z0-9_-]+)', url)
    if shorts_match:
        return shorts_match.group(1)
    
    # youtube.com/watch?v=VIDEO_ID
    watch_match = re.search(r'youtube\.com/watch\?v=([a-zA-Z0-9_-]+)', url)
    if watch_match:
        return watch_match.group(1)
    
    # youtu.be/VIDEO_ID
    short_match = re.search(r'youtu\.be/([a-zA-Z0-9_-]+)', url)
    if short_match:
        return short_match.group(1)
    
    return None

def load_token(channel_name):
    """Load saved OAuth token for channel."""
    token_path = Path(__file__).parent / 'tokens' / f'{channel_name}.pickle'
    
    if not token_path.exists():
        print(f"Error: No token found for {channel_name}")
        print(f"Run: python auth_setup.py {channel_name}")
        return None
    
    with open(token_path, 'rb') as token_file:
        creds = pickle.load(token_file)
    
    # Refresh if needed
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
    
    return creds

def get_youtube_views(youtube, video_ids):
    """Fetch view counts for multiple videos."""
    if not video_ids:
        return {}
    
    views = {}
    # Process in chunks of 50 (API limit per request)
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i:i+50]
        request = youtube.videos().list(
            part='statistics',
            id=','.join(chunk)
        )
        response = request.execute()
        
        for item in response.get('items', []):
            video_id = item['id']
            view_count = int(item['statistics'].get('viewCount', 0))
            views[video_id] = view_count
    
    return views

def sync_channel_analytics(channel_name):
    """Sync YouTube analytics for a channel."""
    db_path = Path(__file__).parent.parent / 'data' / 'clip_empire.db'
    
    # Load token
    creds = load_token(channel_name)
    if not creds:
        return None
    
    # Build YouTube service
    youtube = build('youtube', 'v3', credentials=creds)
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Add views column to publish_results if it doesn't exist
    cur.execute("PRAGMA table_info(publish_results)")
    columns = [col[1] for col in cur.fetchall()]
    if 'views' not in columns:
        print(f"  Adding 'views' column to publish_results...")
        cur.execute("ALTER TABLE publish_results ADD COLUMN views INTEGER DEFAULT 0")
        conn.commit()
    
    # Fetch succeeded publishes for this channel with YouTube URLs
    cur.execute("""
        SELECT pr.result_id, pr.post_url, pr.job_id, pr.views
        FROM publish_results pr
        JOIN publish_jobs pj ON pr.job_id = pj.job_id
        WHERE pj.channel_name = ? 
          AND pr.success = 1
          AND pr.post_url LIKE '%youtube%'
          AND pr.post_url IS NOT NULL
    """, (channel_name,))
    
    results = cur.fetchall()
    
    if not results:
        print(f"  No YouTube videos found for {channel_name}")
        conn.close()
        return {'channel': channel_name, 'updated': 0, 'total': 0, 'avg_views': 0}
    
    print(f"  Found {len(results)} YouTube videos for {channel_name}")
    
    # Extract video IDs and fetch view counts
    video_data = {}
    for row in results:
        video_id = extract_video_id(row['post_url'])
        if video_id:
            video_data[video_id] = row
    
    if not video_data:
        print(f"  Could not extract video IDs")
        conn.close()
        return {'channel': channel_name, 'updated': 0, 'total': 0, 'avg_views': 0}
    
    print(f"  Fetching view counts for {len(video_data)} videos...")
    views = get_youtube_views(youtube, list(video_data.keys()))
    
    # Update database
    updated = 0
    total_views = 0
    
    for video_id, row in video_data.items():
        if video_id in views:
            view_count = views[video_id]
            cur.execute("""
                UPDATE publish_results
                SET views = ?
                WHERE result_id = ?
            """, (view_count, row['result_id']))
            
            # Also find and update source_clips if linked
            cur.execute("""
                SELECT pj.variant_id FROM publish_jobs pj
                WHERE pj.job_id = ?
            """, (row['job_id'],))
            
            variant_row = cur.fetchone()
            if variant_row:
                cur.execute("""
                    SELECT clip_id FROM platform_variants
                    WHERE variant_id = ?
                """, (variant_row[0],))
                
                clip_row = cur.fetchone()
                if clip_row:
                    cur.execute("""
                        UPDATE source_clips
                        SET view_count = ?
                        WHERE clip_id = ?
                    """, (view_count, clip_row[0]))
            
            updated += 1
            total_views += view_count
    
    conn.commit()
    conn.close()
    
    avg_views = total_views / updated if updated > 0 else 0
    print(f"  ✓ Updated {updated} videos, avg {int(avg_views):,} views")
    
    return {
        'channel': channel_name,
        'updated': updated,
        'total': len(video_data),
        'avg_views': int(avg_views)
    }

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: python youtube_analytics.py <channel_name>")
        print(f"Supported channels: {', '.join(CHANNEL_CREDENTIALS.keys())}")
        sys.exit(1)
    
    channel_name = sys.argv[1]
    
    if channel_name not in CHANNEL_CREDENTIALS:
        print(f"Error: Channel '{channel_name}' not recognized")
        print(f"Supported channels: {', '.join(CHANNEL_CREDENTIALS.keys())}")
        sys.exit(1)
    
    try:
        result = sync_channel_analytics(channel_name)
        if result:
            print(f"\nResult: {result}")
    except Exception as e:
        print(f"\nError syncing analytics: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
