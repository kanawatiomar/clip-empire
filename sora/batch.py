"""
Sora Batch Generator — Clip Empire
Stockpile mode: generate X clips per channel across all 10 channels.
Designed to run overnight or in background to build a footage library.

Usage:
    python batch.py                     # 3 clips per channel (30 total)
    python batch.py --per-channel 5     # 5 clips per channel (50 total)
    python batch.py --channels market_meltdowns crypto_confessions
    python batch.py --dry-run           # preview prompts + cost estimate
"""

import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sora.prompts import list_channels, get_prompts
from sora.generator import (
    generate_clip, load_state, MODEL, SIZE, DURATION, FOOTAGE_DIR
)


COST_PER_SECOND = {
    "sora-2": 0.10,
    "sora-2-pro": 0.50,
}


def estimate_cost(n_clips: int, seconds: int, model: str) -> float:
    rate = COST_PER_SECOND.get(model, 0.10)
    return n_clips * seconds * rate


def main():
    parser = argparse.ArgumentParser(description="Batch generate Sora footage for all channels")
    parser.add_argument("--per-channel", type=int, default=3,
                        help="Clips to generate per channel (default: 3)")
    parser.add_argument("--channels", nargs="+", default=None,
                        help="Specific channels (default: all)")
    parser.add_argument("--model", default=MODEL,
                        choices=["sora-2", "sora-2-pro"],
                        help="Model to use")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show plan + cost estimate without generating")
    args = parser.parse_args()

    channels = args.channels or list_channels()
    total_clips = len(channels) * args.per_channel
    est_cost = estimate_cost(total_clips, DURATION, args.model)

    print(f"""
==============================================
  SORA BATCH GENERATOR -- CLIP EMPIRE
==============================================
  Channels:     {len(channels)}
  Per channel:  {args.per_channel}
  Total clips:  {total_clips}
  Model:        {args.model}
  Duration:     {DURATION}s per clip
  Est. cost:    ${est_cost:.2f}
==============================================
""")

    if args.dry_run:
        print("DRY RUN - prompts that would be generated:\n")
        state = load_state()
        for channel in channels:
            prompts = get_prompts(channel)
            done = {item["index"] for item in state["generated"].get(channel, [])}
            available = [(i, p) for i, p in enumerate(prompts) if i not in done]
            to_gen = available[:args.per_channel]
            print(f"  [{channel}] - {len(to_gen)} clips:")
            for i, prompt in to_gen:
                print(f"    [{i:02d}] {prompt[:80]}...")
            print()
        return

    confirm = input(f"Generate {total_clips} clips for ~${est_cost:.2f}? [y/N]: ").strip().lower()
    if confirm != "y":
        print("Aborted.")
        return

    state = load_state()
    total_ok = 0
    total_fail = 0

    for channel in channels:
        prompts = get_prompts(channel)
        done = {item["index"] for item in state["generated"].get(channel, [])}
        available = [(i, p) for i, p in enumerate(prompts) if i not in done]
        to_gen = available[:args.per_channel]

        if not to_gen:
            print(f"\n[{channel}] fully stocked - skipping")
            continue

        for idx, prompt in to_gen:
            result = generate_clip(channel, prompt, idx, state)
            if result:
                total_ok += 1
            else:
                total_fail += 1

    print(f"\n{'='*50}")
    print(f"BATCH COMPLETE")
    print(f"  Generated: {total_ok}")
    print(f"  Failed:    {total_fail}")
    print(f"  Footage:   {FOOTAGE_DIR}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
