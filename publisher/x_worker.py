"""X (Twitter) video poster for Clip Empire.

Posts short-form vertical videos with captions + hashtags via Twitter API v1.1
(media upload) + v2 (tweet creation).
"""
from __future__ import annotations

import os
import time
import json
from pathlib import Path
from typing import Optional

import requests
from requests_oauthlib import OAuth1

_ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

def _load_creds() -> dict:
    creds = {}
    if _ENV_PATH.exists():
        for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                creds[k.strip()] = v.strip()
    return creds

def _get_auth() -> OAuth1:
    c = _load_creds()
    return OAuth1(
        c["X_CONSUMER_KEY"],
        c["X_CONSUMER_SECRET"],
        c["X_ACCESS_TOKEN"],
        c["X_ACCESS_TOKEN_SECRET"],
    )

# ── Media upload (chunked for videos) ────────────────────────────────────────

def _upload_video(video_path: str) -> Optional[str]:
    """Upload video via Twitter chunked media upload. Returns media_id_string."""
    auth = _get_auth()
    path = Path(video_path)
    total_bytes = path.stat().st_size
    mime = "video/mp4"

    # INIT
    r = requests.post(
        "https://upload.twitter.com/1.1/media/upload.json",
        data={"command": "INIT", "media_type": mime,
              "total_bytes": total_bytes, "media_category": "tweet_video"},
        auth=auth,
    )
    r.raise_for_status()
    media_id = r.json()["media_id_string"]
    print(f"[x] Upload INIT — media_id={media_id}")

    # APPEND chunks
    chunk_size = 4 * 1024 * 1024  # 4MB
    segment = 0
    with open(video_path, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            r = requests.post(
                "https://upload.twitter.com/1.1/media/upload.json",
                data={"command": "APPEND", "media_id": media_id,
                      "segment_index": segment},
                files={"media": chunk},
                auth=auth,
            )
            r.raise_for_status()
            segment += 1
            print(f"[x] Uploaded chunk {segment} ({len(chunk)//1024}KB)")

    # FINALIZE
    r = requests.post(
        "https://upload.twitter.com/1.1/media/upload.json",
        data={"command": "FINALIZE", "media_id": media_id},
        auth=auth,
    )
    r.raise_for_status()
    info = r.json()
    print(f"[x] Finalized — state={info.get('processing_info', {}).get('state', 'done')}")

    # Wait for processing
    processing = info.get("processing_info", {})
    while processing.get("state") in ("pending", "in_progress"):
        wait = processing.get("check_after_secs", 3)
        print(f"[x] Processing... waiting {wait}s")
        time.sleep(wait)
        r = requests.get(
            "https://upload.twitter.com/1.1/media/upload.json",
            params={"command": "STATUS", "media_id": media_id},
            auth=auth,
        )
        r.raise_for_status()
        processing = r.json().get("processing_info", {})

    state = processing.get("state", "succeeded")
    if state == "failed":
        print(f"[x] Video processing failed: {processing}")
        return None

    print(f"[x] Video ready — media_id={media_id}")
    return media_id


# ── Tweet creation ────────────────────────────────────────────────────────────

def post_video_tweet(video_path: str, text: str) -> Optional[str]:
    """Upload video and post tweet. Returns tweet URL or None on failure."""
    print(f"[x] Uploading video: {Path(video_path).name}")
    media_id = _upload_video(video_path)
    if not media_id:
        return None

    auth = _get_auth()

    # Post tweet via v2
    payload = {
        "text": text[:280],
        "media": {"media_ids": [media_id]},
    }
    r = requests.post(
        "https://api.twitter.com/2/tweets",
        json=payload,
        auth=auth,
    )
    if r.status_code not in (200, 201):
        print(f"[x] Tweet failed {r.status_code}: {r.text[:300]}")
        return None

    tweet_id = r.json()["data"]["id"]
    # Get username for URL
    creds = _load_creds()
    # We know it's @onchainjit (arc_highlightz)
    tweet_url = f"https://x.com/onchainjit/status/{tweet_id}"
    print(f"[x] Posted: {tweet_url}")
    return tweet_url


# ── Channel → account mapping ─────────────────────────────────────────────────

_CHANNEL_X_ACCOUNT = {
    "arc_highlightz": "onchainjit",
}

def get_x_account(channel_name: str) -> Optional[str]:
    return _CHANNEL_X_ACCOUNT.get(channel_name)


# ── Caption builder ──────────────────────────────────────────────────────────

# Creator-specific hashtags (no game-specific tags that might be wrong)
_CREATOR_HASHTAGS = {
    "tfue":            "#Tfue #TwitchClips #Gaming #GamingClips #Clutch",
    "cloakzy":         "#Cloakzy #TwitchClips #Gaming #GamingClips",
    "shinyatheninja":  "#Shinya #TwitchClips #Gaming #GamingClips",
    "myth":            "#Myth #TwitchClips #Gaming #GamingClips",
    "bugha":           "#Bugha #TwitchClips #Gaming #GamingClips",
}
_DEFAULT_HASHTAGS = "#TwitchClips #Gaming #GamingClips #Clutch"


def build_tweet_text(caption: str, hashtags: Optional[str] = None, creator: str = "") -> str:
    """Build Twitter-native tweet text — punchy, with creator-appropriate hashtags."""
    import random

    openers = [
        "this clip is actually insane 💀",
        "bro said hold on real quick 😭",
        "no way he just did that 🎮",
        "the lobby was NOT ready",
        "this one broke me 💀",
        "ok this is actually crazy",
        "chat would've lost it 🔥",
        "lowkey one of the best clips i've seen",
        "this guy is cooked 💀",
        "not even close lmaooo",
        "the timing on this 😭",
        "someone call 911",
    ]

    opener = random.choice(openers)

    # Add creator mention
    creator_tag = ""
    if creator and creator.lower() != "unknown":
        creator_tag = f" (via {creator.capitalize()})"

    # Use creator-specific hashtags, not generic Fortnite tags
    creator_key = (creator or "").lower().strip()
    tag_str = _CREATOR_HASHTAGS.get(creator_key, _DEFAULT_HASHTAGS)
    tags = f"\n\n{tag_str}"

    base = f"{opener}{creator_tag}"
    max_base = 280 - len(tags)
    if len(base) > max_base:
        base = base[:max_base - 1] + "..."
    return base + tags


if __name__ == "__main__":
    # Quick test
    import sys
    if len(sys.argv) > 1:
        url = post_video_tweet(sys.argv[1], "Test clip 🎮 #gaming #fortnite")
        print(f"Result: {url}")
    else:
        auth = _get_auth()
        r = requests.get("https://api.twitter.com/1.1/account/verify_credentials.json", auth=auth)
        print(f"Auth OK: @{r.json().get('screen_name')}")
