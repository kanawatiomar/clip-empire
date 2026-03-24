"""Main runner for fomo_highlights Reddit screenshot pipeline.

Run from repo root: python -m engine.fomo_highlights_runner --count 2 --dry-run

Orchestrates scraping, compositing, and queuing for fomo_highlights channel.
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

# Repo root = parent of engine/
REPO_ROOT = Path(__file__).resolve().parent.parent

# Import directly from modules to avoid __init__.py issues
from engine.ingest import reddit_scraper
from engine.transform import bg_generator, meme_compositor


class ViralRecapsRunner:
    """Orchestrates the fomo_highlights pipeline."""
    
    def __init__(
        self,
        db_path: str = str(REPO_ROOT / "data" / "clip_empire.db"),
        renders_dir: str = str(REPO_ROOT / "renders"),
        used_json_path: str = str(REPO_ROOT / "data" / "reddit_used.json"),
    ):
        self.db_path = db_path
        self.renders_dir = Path(renders_dir)
        self.channel_renders_dir = self.renders_dir / "fomo_highlights"
        self.used_json_path = used_json_path
        
        # Create directories
        self.channel_renders_dir.mkdir(parents=True, exist_ok=True)
        
        # Ensure background video exists
        self.bg_path = bg_generator.get_or_create_background(str(REPO_ROOT / "data" / "viral_bg.mp4"))
        print(f"[runner] Background video: {self.bg_path}")
    
    def get_db_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        # Always resolve to absolute path
        db = str(REPO_ROOT / "data" / "clip_empire.db")
        conn = sqlite3.connect(db)
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
            channel_name: Target channel (e.g., "fomo_highlights")
        
        Returns:
            True if inserted successfully
        """
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            
            # Insert publish job using actual schema
            import uuid as _uuid
            from datetime import datetime as _dt, timedelta
            job_id = str(_uuid.uuid4())
            now = _dt.now().isoformat()
            # Schedule 1 hour from now
            schedule_at = (_dt.now() + timedelta(hours=1)).strftime('%Y-%m-%dT%H:%M:%S')
            cursor.execute("""
                INSERT INTO publish_jobs (
                    job_id, variant_id, platform, channel_name,
                    publisher_account, schedule_at, status,
                    attempts, caption_text, render_path,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id, clip_id, 'youtube', channel_name,
                channel_name, schedule_at, 'queued',
                0, title, video_path,
                now, now,
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
        hook, punchline = reddit_scraper.generate_hook_and_punchline(post_title, subreddit=subreddit, score=score)
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
            channel_name="fomo_highlights",
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

