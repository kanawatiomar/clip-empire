"""Main runner for viral_recaps Reddit screenshot pipeline.

Run from repo root: python -m engine.viral_recaps_runner --count 2 --dry-run

Orchestrates scraping, compositing, and queuing for viral_recaps channel.
"""

from __future__ import annotations

import sys
import argparse
import json
from pathlib import Path
from datetime import datetime
import sqlite3
import uuid
from typing import Optional

# Import directly from modules to avoid __init__.py issues
from engine.ingest import reddit_scraper
from engine.transform import bg_generator, meme_compositor


class ViralRecapsRunner:
    """Orchestrates the viral_recaps pipeline."""
    
    def __init__(
        self,
        db_path: str = "clip_empire.db",
        renders_dir: str = "renders",
        used_json_path: str = "data/reddit_used.json",
    ):
        self.db_path = db_path
        self.renders_dir = Path(renders_dir)
        self.channel_renders_dir = self.renders_dir / "viral_recaps"
        self.used_json_path = used_json_path
        
        # Create directories
        self.channel_renders_dir.mkdir(parents=True, exist_ok=True)
        
        # Ensure background video exists
        self.bg_path = bg_generator.get_or_create_background()
        print(f"[runner] Background video: {self.bg_path}")
    
    def get_db_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
    
    def insert_publish_job(
        self,
        clip_id: str,
        video_path: str,
        title: str,
        channel_name: str,
    ) -> bool:
        """Insert a publish_job into the database queue.
        
        Args:
            clip_id: Unique clip ID
            video_path: Path to the rendered MP4
            title: Display title
            channel_name: Target channel (e.g., "viral_recaps")
        
        Returns:
            True if inserted successfully
        """
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Insert publish job
            cursor.execute("""
                INSERT INTO publish_jobs (
                    job_id,
                    clip_id,
                    channel,
                    status,
                    video_path,
                    title,
                    created_at,
                    updated_at,
                    attempts,
                    max_attempts,
                    metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()),  # job_id
                clip_id,            # clip_id
                channel_name,       # channel
                "pending",          # status
                video_path,         # video_path
                title,              # title
                datetime.now().isoformat(),  # created_at
                datetime.now().isoformat(),  # updated_at
                0,                  # attempts
                3,                  # max_attempts
                json.dumps({"source": "reddit_scraper"}),  # metadata
            ))
            
            conn.commit()
            conn.close()
            
            print(f"[runner] Inserted publish job: {clip_id}")
            return True
        
        except Exception as e:
            print(f"[runner] Error inserting publish job: {e}")
            return False
    
    def process_post(self, post: dict, dry_run: bool = False) -> bool:
        """Process a single Reddit post.
        
        Args:
            post: Post dict from scraper {title, image_url, post_url, subreddit, score}
            dry_run: If True, don't write to disk or DB
        
        Returns:
            True if successful
        """
        post_title = post["title"]
        image_url = post["image_url"]
        post_url = post["post_url"]
        subreddit = post["subreddit"]
        score = post["score"]
        
        print(f"\n[runner] Processing: {post_title[:60]}...")
        print(f"         Sub: {subreddit}, Score: {score}")
        
        # Generate hook and punchline
        hook, punchline = reddit_scraper.generate_hook_and_punchline(post_title)
        print(f"         Hook: {hook.replace(chr(10), ' / ')}")
        if punchline:
            print(f"         Punchline: {punchline.replace(chr(10), ' / ')}")
        
        if dry_run:
            print("[runner] DRY RUN: would create video here")
            return True
        
        # Create unique clip ID
        clip_id = f"reddit_{subreddit}_{score}_{uuid.uuid4().hex[:8]}"
        
        # Render output path
        output_path = str(self.channel_renders_dir / f"{clip_id}_final.mp4")
        
        # Create the short
        success = meme_compositor.create_short(
            bg_video_path=self.bg_path,
            image_url=image_url,
            hook_text=hook,
            punchline_text=punchline,
            output_path=output_path,
            duration_s=20,
        )
        
        if not success:
            print(f"[runner] Failed to create short")
            return False
        
        # Insert publish job
        display_title = f"{subreddit}: {post_title[:80]}"
        self.insert_publish_job(
            clip_id=clip_id,
            video_path=output_path,
            title=display_title,
            channel_name="viral_recaps",
        )
        
        # Mark as used
        used = reddit_scraper.load_used_posts(self.used_json_path)
        used.add(post_title.lower())
        reddit_scraper.save_used_posts(used, self.used_json_path)
        
        return True
    
    def run(
        self,
        count: int = 5,
        dry_run: bool = False,
    ) -> int:
        """Run the pipeline.
        
        Args:
            count: Number of posts to process
            dry_run: If True, don't write to disk or DB
        
        Returns:
            Number of successful posts processed
        """
        print(f"\n{'='*60}")
        print(f"Viral Recaps Pipeline Started")
        print(f"{'='*60}")
        print(f"DRY RUN: {dry_run}")
        print(f"Target count: {count}")
        
        # Scrape all subreddits
        print(f"\n[runner] Scraping Reddit (finance/business subreddits)...")
        all_posts = reddit_scraper.scrape_all_subreddits(limit_per_sub=25)
        print(f"[runner] Found {len(all_posts)} posts total")
        
        # Filter to unused only
        unused_posts = reddit_scraper.filter_unused_posts(all_posts, self.used_json_path)
        print(f"[runner] {len(unused_posts)} posts are new")
        
        if not unused_posts:
            print("[runner] No new posts to process")
            return 0
        
        # Process up to count posts
        success_count = 0
        for i, post in enumerate(unused_posts[:count]):
            if self.process_post(post, dry_run=dry_run):
                success_count += 1
            
            if success_count >= count:
                break
        
        print(f"\n{'='*60}")
        print(f"Pipeline Complete: {success_count}/{count} successful")
        print(f"{'='*60}\n")
        
        return success_count


def main():
    """Entry point."""
    parser = argparse.ArgumentParser(description="Viral Recaps Reddit screenshot pipeline")
    parser.add_argument("--count", type=int, default=5, help="Number of posts to process")
    parser.add_argument("--dry-run", action="store_true", help="Don't write to disk or DB")
    parser.add_argument("--db", default="clip_empire.db", help="Path to database")
    parser.add_argument("--renders", default="renders", help="Renders output directory")
    
    args = parser.parse_args()
    
    runner = ViralRecapsRunner(
        db_path=args.db,
        renders_dir=args.renders,
    )
    
    success = runner.run(
        count=args.count,
        dry_run=args.dry_run,
    )
    
    sys.exit(0 if success > 0 else 1)


if __name__ == "__main__":
    main()
