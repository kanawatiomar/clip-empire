import os
import time
from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

from publisher.queue import get_next_job, update_job_status, fail_job

YOUTUBE_STUDIO_URL = "https://studio.youtube.com"


@dataclass
class YouTubeWorkerConfig:
    # Base directory that contains per-channel Chrome user-data-dirs
    profiles_dir: str = os.path.join(os.getcwd(), "profiles")
    # Maximum time to wait for Studio to load
    nav_timeout_ms: int = 60_000
    # Headless should be False for reliability (and to allow manual intervention)
    headless: bool = False


def _profile_path_for_channel(cfg: YouTubeWorkerConfig, channel_name: str) -> str:
    return os.path.join(cfg.profiles_dir, channel_name)


def open_studio_and_verify_logged_in(page, cfg: YouTubeWorkerConfig) -> None:
    page.goto(YOUTUBE_STUDIO_URL, wait_until="domcontentloaded", timeout=cfg.nav_timeout_ms)

    # Heuristic checks (no brittle selectors yet)
    # 1) If we get redirected to accounts.google.com -> not logged in
    url = page.url
    if "accounts.google.com" in url:
        raise RuntimeError(f"Not logged in (redirected to {url}).")

    # 2) Studio should contain 'studio.youtube.com'
    if "studio.youtube.com" not in url:
        # Sometimes an interstitial appears; still treat as failure for now.
        raise RuntimeError(f"Unexpected URL after navigation: {url}")

    # Try to detect the Studio shell (best-effort)
    try:
        page.wait_for_timeout(1500)
        page.wait_for_load_state("networkidle", timeout=15_000)
    except PWTimeout:
        pass


def run_once(cfg: Optional[YouTubeWorkerConfig] = None, channel_name: Optional[str] = None) -> int:
    """Claims 1 queued YouTube job and performs a stub publish:

    - launches the channel's Chrome profile
    - opens YouTube Studio
    - verifies session is logged in

    Returns exit code (0=did work, 2=no job)."""

    cfg = cfg or YouTubeWorkerConfig()
    job = get_next_job(platform="youtube", channel_name=channel_name)
    if not job:
        return 2

    job_id = job["job_id"]
    ch = job["channel_name"]
    profile_path = _profile_path_for_channel(cfg, ch)

    # Ensure profile dir exists (it should be created by setup_wizard)
    os.makedirs(profile_path, exist_ok=True)

    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=profile_path,
                headless=cfg.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--start-maximized",
                ],
            )
            page = context.new_page()

            open_studio_and_verify_logged_in(page, cfg)

            # Stub success: we reached Studio.
            update_job_status(job_id, "succeeded", post_url=None, platform_post_id=None)

            # Keep window open briefly so you can see it (optional)
            page.wait_for_timeout(1000)
            context.close()

        return 0

    except Exception as e:
        # Put job back with backoff
        fail_job(job_id, error_class="youtube_worker", error_detail=str(e))
        return 1


if __name__ == "__main__":
    code = run_once()
    raise SystemExit(code)
