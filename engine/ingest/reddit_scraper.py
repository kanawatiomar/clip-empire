"""Reddit viral post scraper for viral_recaps channel.

Scrapes hot posts from subreddits, filters by score, and generates hook/punchline text.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional
import requests
from datetime import datetime
import re

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


SUBREDDITS = [
    "wallstreetbets",
    "antiwork",
    "personalfinance",
    "financialindependence",
    "mildlyinfuriating",
]

MIN_SCORE = 1000
MIN_TITLE_LENGTH = 10
MAX_TITLE_LENGTH = 200

HEADERS = {
    "User-Agent": "ViralRecaps/1.0"
}


class RedditPost:
    """Represents a single Reddit post with extracted metadata."""
    
    def __init__(self, data: dict, subreddit: str):
        self.subreddit = subreddit
        self.title = data.get("title", "")
        self.url = f"https://reddit.com{data.get('permalink', '')}"
        self.post_url = data.get("url", "")
        self.score = data.get("score", 0)
        self.selftext = data.get("selftext", "")
        self.over_18 = data.get("over_18", False)
        self.post_hint = data.get("post_hint", "")
        self.is_video = data.get("is_video", False)
        
        # Try to extract direct image URL
        self.image_url = self._extract_image_url(data)
    
    def _extract_image_url(self, data: dict) -> Optional[str]:
        """Extract a direct image URL if available."""
        url = data.get("url", "")
        
        # Direct image URL (most common)
        if url and any(url.endswith(ext) for ext in [".jpg", ".jpeg", ".png", ".gif", ".webp"]):
            # Must be a real URL, not reddit.com
            if url.startswith(("http://", "https://")) and "reddit.com" not in url:
                return url
        
        # Check post_hint for image posts
        post_hint = data.get("post_hint", "")
        if post_hint != "image":
            return None  # Only process image posts, skip videos/links/text
        
        # Media metadata (for hosted images)
        if "media_metadata" in data and data["media_metadata"]:
            # Get first image from media
            for key, media in data["media_metadata"].items():
                if media.get("type") == "image":
                    img_url = media.get("s", {}).get("x")
                    if img_url and img_url.startswith(("http://", "https://")):
                        return img_url
        
        # Gallery data
        if data.get("gallery_data") and data.get("post_hint") == "gallery":
            gallery_items = data["gallery_data"].get("items", [])
            if gallery_items:
                media_id = gallery_items[0].get("media_id")
                if media_id and "media_metadata" in data:
                    media = data["media_metadata"].get(media_id, {})
                    img_url = media.get("s", {}).get("x")
                    if img_url and img_url.startswith(("http://", "https://")):
                        return img_url
        
        return None
    
    def is_valid(self) -> bool:
        """Check if post meets filtering criteria."""
        # Filter NSFW
        if self.over_18:
            return False
        
        # Filter by score
        if self.score < MIN_SCORE:
            return False
        
        # Filter by title length
        if len(self.title) < MIN_TITLE_LENGTH or len(self.title) > MAX_TITLE_LENGTH:
            return False
        
        # MUST have a valid image URL (not optional)
        if not self.image_url:
            return False
        
        # Validate image URL is actually a URL
        if not isinstance(self.image_url, str) or not self.image_url.startswith(('http://', 'https://')):
            return False
        
        return True


def scrape_subreddit(subreddit: str, limit: int = 25) -> list[dict]:
    """Scrape hot posts from a subreddit.
    
    Args:
        subreddit: Subreddit name (without r/)
        limit: Number of posts to fetch
    
    Returns:
        List of valid post dicts with {title, image_url, post_url, subreddit, score}
    """
    url = f"https://www.reddit.com/r/{subreddit}/hot.json?limit={limit}"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
    except Exception as e:
        print(f"[reddit] Error fetching {subreddit}: {e}")
        return []
    
    try:
        data = response.json()
    except Exception as e:
        print(f"[reddit] Error parsing JSON for {subreddit}: {e}")
        return []
    
    posts = []
    children = data.get("data", {}).get("children", [])
    
    for child in children:
        post_data = child.get("data", {})
        post = RedditPost(post_data, subreddit)
        
        if post.is_valid():
            posts.append({
                "title": post.title,
                "image_url": post.image_url,
                "post_url": post.url,
                "subreddit": post.subreddit,
                "score": post.score,
                "selftext": post.selftext,
            })
    
    return posts


def scrape_all_subreddits(limit_per_sub: int = 25) -> list[dict]:
    """Scrape all configured subreddits and deduplicate."""
    all_posts = []
    seen_titles = set()
    
    for subreddit in SUBREDDITS:
        posts = scrape_subreddit(subreddit, limit=limit_per_sub)
        
        for post in posts:
            # Avoid duplicates
            title_lower = post["title"].lower()
            if title_lower not in seen_titles:
                all_posts.append(post)
                seen_titles.add(title_lower)
    
    # Sort by score descending
    all_posts.sort(key=lambda x: x["score"], reverse=True)
    
    return all_posts


def load_used_posts(used_json_path: str = "data/reddit_used.json") -> set[str]:
    """Load set of already-used post titles."""
    if not Path(used_json_path).exists():
        return set()
    
    try:
        with open(used_json_path, "r") as f:
            data = json.load(f)
            return set(data.get("used_titles", []))
    except Exception as e:
        print(f"[reddit] Error loading used posts: {e}")
        return set()


def save_used_posts(used_titles: set[str], used_json_path: str = "data/reddit_used.json"):
    """Save set of used post titles."""
    Path(used_json_path).parent.mkdir(parents=True, exist_ok=True)
    
    with open(used_json_path, "w") as f:
        json.dump({
            "used_titles": sorted(list(used_titles)),
            "last_updated": datetime.now().isoformat(),
        }, f, indent=2)


def filter_unused_posts(posts: list[dict], used_json_path: str = "data/reddit_used.json") -> list[dict]:
    """Filter out already-used posts."""
    used = load_used_posts(used_json_path)
    return [p for p in posts if p["title"].lower() not in used]


def word_wrap(text: str, max_chars: int = 20) -> str:
    """Word wrap text to fit on video."""
    words = text.split()
    lines = []
    current_line = []
    current_length = 0
    
    for word in words:
        if current_length + len(word) + 1 > max_chars and current_line:
            lines.append(" ".join(current_line))
            current_line = [word]
            current_length = len(word)
        else:
            current_line.append(word)
            current_length += len(word) + 1
    
    if current_line:
        lines.append(" ".join(current_line))
    
    return "\n".join(lines)


def generate_hook_and_punchline(title: str) -> tuple[str, str]:
    """Generate dramatic hook and punchline using OpenAI.
    
    Args:
        title: Reddit post title
    
    Returns:
        (hook, punchline) tuple
    """
    if not HAS_OPENAI:
        # Fallback: use title as hook
        hook = word_wrap(title[:100], max_chars=20)
        return (hook, "")
    
    try:
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            # Try to load from .env
            env_path = Path("../.env")
            if env_path.exists():
                with open(env_path) as f:
                    for line in f:
                        if line.startswith("OPENAI_API_KEY="):
                            api_key = line.split("=", 1)[1].strip()
                            break
        
        if not api_key:
            raise ValueError("No OPENAI_API_KEY found")
        
        client = OpenAI(api_key=api_key)
        
        prompt = f"""Generate a dramatic hook and punchline for a finance/work drama Reddit post.
Focus on: salary drama, job losses, investment wins/losses, boss behavior, workplace frustration.

Reddit title: "{title}"

Return ONLY a JSON object with exactly this format (no markdown, no extra text):
{{"hook": "dramatic setup or question (max 12 words)", "punchline": "surprising outcome or reaction (max 10 words)"}}

Examples of good pairs:
- Hook: "Employee asked for raise after 5 years. Boss's reply:"  Punchline: "They got a new job paying double."
- Hook: "Guy invested his life savings in one stock"  Punchline: "It went up 500% in 6 months."
- Hook: "Server told boss they quit mid-shift"  Punchline: "The boss's face was priceless."

Be punchy, dramatic, use casual/internet language. Focus on the unexpected twist or emotional reaction."""
        
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=150,
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Try to parse JSON
        try:
            result = json.loads(result_text)
            hook = word_wrap(result.get("hook", "")[:100], max_chars=20)
            punchline = word_wrap(result.get("punchline", ""), max_chars=22)
            return (hook, punchline)
        except json.JSONDecodeError:
            # Fallback parsing
            lines = result_text.split("\n")
            hook = word_wrap(title[:100], max_chars=20)
            punchline = ""
            return (hook, punchline)
    
    except Exception as e:
        print(f"[reddit] Error generating hook/punchline: {e}")
        # Fallback: use title as hook
        hook = word_wrap(title[:100], max_chars=20)
        return (hook, "")


if __name__ == "__main__":
    # Test scraper
    print("[reddit] Scraping all subreddits...")
    posts = scrape_all_subreddits()
    print(f"Found {len(posts)} valid posts")
    
    # Show first 3
    for i, post in enumerate(posts[:3]):
        print(f"\n--- Post {i+1} ---")
        print(f"Title: {post['title']}")
        print(f"Sub: {post['subreddit']}")
        print(f"Score: {post['score']}")
        print(f"Image URL: {post['image_url'][:60] if post['image_url'] else 'None'}...")
        
        hook, punchline = generate_hook_and_punchline(post['title'])
        print(f"Hook: {hook}")
        print(f"Punchline: {punchline}")
