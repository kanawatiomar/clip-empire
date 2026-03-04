"""
Sora API Generator — Clip Empire
Submits video generation jobs, polls for completion, downloads MP4s.

Usage:
    python generator.py --channel market_meltdowns --count 5
    python generator.py --channel all --count 3
    python generator.py --channel crypto_confessions --index 0  # specific prompt
"""

import os
import sys
import time
import json
import argparse
import requests
from pathlib import Path
from datetime import datetime

# ── Load .env ────────────────────────────────────────────────────────────────
def _load_env():
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

_load_env()

# ── Config ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
FOOTAGE_DIR = BASE_DIR / "footage"
STATE_FILE = BASE_DIR / "gen_state.json"
FOOTAGE_DIR.mkdir(exist_ok=True)

API_KEY = os.getenv("OPENAI_API_KEY")
BASE_URL = "https://api.openai.com/v1"
HEADERS = lambda: {"Authorization": f"Bearer {API_KEY}", "Content-Type": "application/json"}

# sora-2 = faster/cheaper, sora-2-pro = higher quality
MODEL = os.getenv("SORA_MODEL", "sora-2")

# 9:16 vertical for Shorts. Sora supports: 480x854, 720x1280
SIZE = os.getenv("SORA_SIZE", "720x1280")

# Duration in seconds (5-20)
DURATION = int(os.getenv("SORA_DURATION", "8"))

# Poll interval
POLL_INTERVAL = 15  # seconds


# ── State tracking ───────────────────────────────────────────────────────────
def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"generated": {}, "jobs": {}}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def mark_generated(channel: str, prompt_index: int, filename: str, state: dict):
    if channel not in state["generated"]:
        state["generated"][channel] = []
    state["generated"][channel].append({
        "index": prompt_index,
        "file": filename,
        "timestamp": datetime.now(datetime.timezone.utc).isoformat()
    })
    save_state(state)


# ── API calls ────────────────────────────────────────────────────────────────
def submit_job(prompt: str) -> dict:
    """Submit a video generation job. Returns job object with id + status."""
    model = os.getenv("SORA_MODEL", "sora-2")
    size = os.getenv("SORA_SIZE", "720x1280")
    duration = os.getenv("SORA_DURATION", "8")  # must be string: "4", "8", or "12"
    resp = requests.post(
        f"{BASE_URL}/videos",
        headers=HEADERS(),
        json={
            "model": model,
            "prompt": prompt,
            "size": size,
            "seconds": duration,
        },
        timeout=30
    )
    resp.raise_for_status()
    return resp.json()


def get_job_status(video_id: str) -> dict:
    """Poll job status."""
    resp = requests.get(
        f"{BASE_URL}/videos/{video_id}",
        headers=HEADERS(),
        timeout=15
    )
    resp.raise_for_status()
    return resp.json()


def download_video(video_id: str, out_path: Path) -> bool:
    """Download completed video to out_path."""
    resp = requests.get(
        f"{BASE_URL}/videos/{video_id}/content",
        headers=HEADERS(),
        timeout=60,
        stream=True
    )
    resp.raise_for_status()
    with open(out_path, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)
    return True


def delete_video(video_id: str):
    """Delete video from OpenAI storage after downloading."""
    try:
        resp = requests.delete(
            f"{BASE_URL}/videos/{video_id}",
            headers=HEADERS(),
            timeout=15
        )
        resp.raise_for_status()
    except Exception as e:
        print(f"  ⚠️  Could not delete {video_id} from OpenAI: {e}")


# ── Core workflow ────────────────────────────────────────────────────────────
def wait_for_job(video_id: str, prompt_preview: str) -> bool:
    """Poll until job is completed or failed. Returns True on success."""
    print(f"  ⏳ Waiting for job {video_id[:20]}...")
    start = time.time()
    while True:
        elapsed = int(time.time() - start)
        data = get_job_status(video_id)
        status = data.get("status", "unknown")
        progress = data.get("progress", 0)

        print(f"  [{elapsed:>3}s] status={status} progress={progress}%")

        if status == "completed":
            return True
        elif status in ("failed", "cancelled"):
            print(f"  ❌ Job {status}: {data.get('error', 'unknown error')}")
            return False

        time.sleep(POLL_INTERVAL)


def generate_clip(channel: str, prompt: str, prompt_index: int, state: dict) -> str | None:
    """
    Full flow: submit → poll → download → delete from OpenAI.
    Returns local filename on success, None on failure.
    """
    print(f"\n🎬 Generating clip {prompt_index+1} for [{channel}]")
    print(f"   Prompt: {prompt[:80]}...")

    # Submit
    try:
        job = submit_job(prompt)
    except requests.HTTPError as e:
        print(f"  ❌ Submit failed: {e.response.status_code} — {e.response.text[:200]}")
        return None

    video_id = job["id"]
    print(f"  ✅ Job submitted: {video_id}")

    # Save pending job to state
    state["jobs"][video_id] = {
        "channel": channel,
        "prompt_index": prompt_index,
        "prompt": prompt,
        "submitted_at": datetime.now(datetime.timezone.utc).isoformat()
    }
    save_state(state)

    # Poll
    success = wait_for_job(video_id, prompt)
    if not success:
        return None

    # Download
    channel_dir = FOOTAGE_DIR / channel
    channel_dir.mkdir(exist_ok=True)
    timestamp = datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
    filename = f"{channel}_{timestamp}_p{prompt_index:02d}.mp4"
    out_path = channel_dir / filename

    print(f"  ⬇️  Downloading → {filename}")
    try:
        download_video(video_id, out_path)
    except Exception as e:
        print(f"  ❌ Download failed: {e}")
        return None

    file_size_mb = out_path.stat().st_size / (1024 * 1024)
    print(f"  ✅ Saved ({file_size_mb:.1f} MB): {out_path}")

    # Cleanup OpenAI storage
    delete_video(video_id)

    # Update state
    mark_generated(channel, prompt_index, str(out_path), state)

    return filename


# ── CLI ───────────────────────────────────────────────────────────────────────
def main():
    # Add parent dir to path for imports
    sys.path.insert(0, str(BASE_DIR.parent.parent))

    from sora.prompts import get_prompts, list_channels

    parser = argparse.ArgumentParser(description="Generate Sora clips for Clip Empire")
    parser.add_argument("--channel", default="market_meltdowns",
                        help="Channel name or 'all' for all channels")
    parser.add_argument("--count", type=int, default=3,
                        help="Number of clips to generate per channel")
    parser.add_argument("--index", type=int, default=None,
                        help="Generate specific prompt index only")
    parser.add_argument("--model", default="sora-2",
                        choices=["sora-2", "sora-2-pro"],
                        help="Sora model: sora-2 or sora-2-pro (default: sora-2)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show prompts without generating")
    args = parser.parse_args()

    # Override model if specified
    os.environ["SORA_MODEL"] = args.model

    if not API_KEY:
        print("❌ OPENAI_API_KEY not set. Add it to your .env or environment.")
        sys.exit(1)

    state = load_state()

    # Pick channels
    channels = list_channels() if args.channel == "all" else [args.channel]

    total_generated = 0
    total_failed = 0

    for channel in channels:
        prompts = get_prompts(channel)
        if not prompts:
            print(f"⚠️  No prompts found for channel: {channel}")
            continue

        # Already generated indices
        done_indices = {
            item["index"]
            for item in state["generated"].get(channel, [])
        }

        # Pick prompts to generate
        if args.index is not None:
            to_generate = [(args.index, prompts[args.index])] if args.index < len(prompts) else []
        else:
            # Pick next N prompts not yet generated
            available = [(i, p) for i, p in enumerate(prompts) if i not in done_indices]
            to_generate = available[:args.count]

        if not to_generate:
            print(f"\n✅ [{channel}] All prompts already generated!")
            continue

        print(f"\n{'='*60}")
        print(f"Channel: {channel} | Generating {len(to_generate)} clip(s)")
        print(f"Model: {MODEL} | Size: {SIZE} | Duration: {DURATION}s")
        print(f"{'='*60}")

        if args.dry_run:
            for i, prompt in to_generate:
                print(f"  [{i:02d}] {prompt}")
            continue

        for prompt_index, prompt in to_generate:
            result = generate_clip(channel, prompt, prompt_index, state)
            if result:
                total_generated += 1
            else:
                total_failed += 1

    print(f"\n{'='*60}")
    print(f"✅ Done! Generated: {total_generated} | Failed: {total_failed}")
    print(f"Footage saved to: {FOOTAGE_DIR}")


if __name__ == "__main__":
    main()
