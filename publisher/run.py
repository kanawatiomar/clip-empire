import argparse
import sys

# Force UTF-8 stdout/stderr on Windows
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from publisher.youtube_worker import run_once as run_youtube_once, YouTubeWorkerConfig


def main():
    ap = argparse.ArgumentParser(description="Clip Empire publisher runner")
    ap.add_argument("--platform", required=True, choices=["youtube"], help="publishing platform")
    ap.add_argument("--channel", default=None, help="optional channel_name to restrict job claiming")
    ap.add_argument("--headless", action="store_true", help="run headless (not recommended)")
    args = ap.parse_args()

    if args.platform == "youtube":
        cfg = YouTubeWorkerConfig(headless=args.headless)
        rc = run_youtube_once(cfg=cfg, channel_name=args.channel)
        raise SystemExit(rc)


if __name__ == "__main__":
    main()
