import os
import time
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timedelta

from playwright.sync_api import sync_playwright, Page, expect, TimeoutError as PWTimeout
import pytz # Will need 'pip install pytz'

from publisher.queue import get_next_job, update_job_status, fail_job
from accounts.channel_definitions import CHANNELS # To get made_for_kids status

LOGS_DIR = os.path.join(os.getcwd(), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)

def _save_failure_artifacts(page: Page, job_id: str) -> None:
    try:
        png_path = os.path.join(LOGS_DIR, f"youtube_fail_{job_id}.png")
        html_path = os.path.join(LOGS_DIR, f"youtube_fail_{job_id}.html")
        page.screenshot(path=png_path, full_page=True)
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(page.content())
        print(f"Saved failure artifacts: {png_path} / {html_path}")
    except Exception as e:
        print(f"Failed to save artifacts: {e}")


def _log_step(job_id: str, step: str) -> None:
    print(f"[{job_id}] {step}")


YOUTUBE_STUDIO_URL = "https://studio.youtube.com"
UPLOAD_URL_SUFFIX = "/upload"

# --- SELECTORS (Robustness is key) ---
SELECTORS = {
    "upload_button": "#create-icon", # This is the '+' icon
    "upload_menu_item": "tp-yt-paper-item[test-id=\"upload-beta\"]",
    "file_input": "input[type=\"file\"]",
    "title_textbox": "#textbox[aria-label=\"Add title\"]",
    "description_textbox": "#textbox[aria-label=\"Add description\"]",
    "not_made_for_kids_radio": "#not-made-for-kids-radio-button",
    "next_button": "#next-button",
    "visibility_radio_button": "tp-yt-paper-radio-button[name=\"SCHEDULE\"]", # For schedule radio
    "schedule_date_input": "#date-textbox > input",
    "schedule_time_input": "#time-textbox > input",
    "schedule_button": "#schedule-button",
    "publish_button": "#publish-button", # This is used if publishing immediately
    "video_link_text": "a.ytcp-video-info-renderer-metadata-details",
    "error_dialog": "ytcp-dialog.warning",
    "save_button": "#save-button", # When publishing immediately
    "close_button": "#close-button", # For the final 'video uploaded' dialog
    "processing_progress": ".progress-label.style-scope.ytcp-uploads-dialog",
    "checks_complete": ".ytcp-uploads-review-stage-status-text",
}

@dataclass
class YouTubeWorkerConfig:
    # Base directory that contains per-channel Chrome user-data-dirs
    profiles_dir: str = os.path.join(os.getcwd(), "profiles")
    # Maximum time to wait for Studio to load
    nav_timeout_ms: int = 60_000
    # Headless should be False for reliability (and to allow manual intervention)
    headless: bool = False
    # Timezone for scheduling
    timezone: str = "America/Denver"


def _profile_path_for_channel(cfg: YouTubeWorkerConfig, channel_name: str) -> str:
    return os.path.join(cfg.profiles_dir, channel_name)


def _wait_for_selector(page: Page, selector: str, timeout_ms: int) -> None:
    expect(page.locator(selector)).to_be_visible(timeout=timeout_ms)


def _login_to_studio_if_needed(page: Page, cfg: YouTubeWorkerConfig) -> None:
    """Navigates to Studio and verifies login. Raises error if redirected or not on Studio page."""
    page.goto(YOUTUBE_STUDIO_URL, wait_until="domcontentloaded", timeout=cfg.nav_timeout_ms)

    url = page.url
    if "accounts.google.com" in url:
        raise RuntimeError(f"Not logged in (redirected to {url}). Manual login required for channel.")

    if "studio.youtube.com" not in url and not page.url.endswith(UPLOAD_URL_SUFFIX):
        # Sometimes Studio has an interstitial, try navigating again to ensure we land on Studio
        # or the upload page if we were on it before
        page.goto(YOUTUBE_STUDIO_URL, wait_until="domcontentloaded", timeout=cfg.nav_timeout_ms)
        if "studio.youtube.com" not in page.url and not page.url.endswith(UPLOAD_URL_SUFFIX):
            raise RuntimeError(f"Unexpected URL after navigation: {page.url}")

    # Wait for Studio to load some key elements, without brittle selectors
    try:
        page.wait_for_timeout(1500) # Give some buffer
        page.wait_for_load_state("networkidle", timeout=15_000)
    except PWTimeout:
        pass # Best effort, might not be networkidle for very long

    print(f"Successfully reached YouTube Studio: {page.url}")

def _click_upload(page: Page, cfg: YouTubeWorkerConfig) -> None:
    print("Clicking upload button...")
    _wait_for_selector(page, SELECTORS["upload_button"], cfg.nav_timeout_ms)
    page.locator(SELECTORS["upload_button"]).click()
    _wait_for_selector(page, SELECTORS["upload_menu_item"], cfg.nav_timeout_ms)
    page.locator(SELECTORS["upload_menu_item"]).click()
    print("Upload menu clicked.")

def _upload_file(page: Page, cfg: YouTubeWorkerConfig, video_path: str) -> None:
    print(f"Uploading file: {video_path}")
    _wait_for_selector(page, SELECTORS["file_input"], cfg.nav_timeout_ms)
    page.locator(SELECTORS["file_input"]).set_input_files(video_path)
    print("File selected for upload.")

def _fill_details(page: Page, cfg: YouTubeWorkerConfig, title: str, description: str, made_for_kids: bool) -> None:
    print("Filling video details...")
    _wait_for_selector(page, SELECTORS["title_textbox"], cfg.nav_timeout_ms)
    page.locator(SELECTORS["title_textbox"]).fill(title)
    page.locator(SELECTORS["description_textbox"]).fill(description)

    if made_for_kids:
        # Assuming 'Made for kids' is the default, if not, we'd need to select it
        # For now, we only handle 'Not made for kids' explicitly if it's not the default
        pass # Need to implement selecting 'Made for kids' if it's an option to click
    else:
        # Ensure 'Not made for kids' is selected
        _wait_for_selector(page, SELECTORS["not_made_for_kids_radio"], cfg.nav_timeout_ms)
        is_checked = page.locator(SELECTORS["not_made_for_kids_radio"]).get_attribute("aria-checked")
        if is_checked == "false":
            page.locator(SELECTORS["not_made_for_kids_radio"]).click()
            print("Selected 'Not made for kids'.")
        else:
            print("'Not made for kids' already selected.")
    
    # Navigate to next step (Video elements)
    page.locator(SELECTORS["next_button"]).click()
    print("Clicked Next (to Video elements).")
    # Navigate to next step (Checks)
    page.locator(SELECTORS["next_button"]).click()
    print("Clicked Next (to Checks).")

def _set_visibility_and_schedule(
    page: Page, cfg: YouTubeWorkerConfig, schedule_at: datetime, timezone: str
) -> str:
    print("Setting visibility and schedule...")
    _wait_for_selector(page, SELECTORS["next_button"], cfg.nav_timeout_ms) # Ensure on Visibility page
    page.locator(SELECTORS["next_button"]).click() # To Visibility page
    print("Clicked Next (to Visibility).")

    now = datetime.now(pytz.timezone(timezone))
    schedule_time_local = schedule_at.astimezone(pytz.timezone(timezone))
    
    if schedule_time_local <= now + timedelta(minutes=5): # Publish immediately if schedule_at is in past or very soon
        print("Scheduling for immediate publish.")
        # For immediate publish, click 'Public' and then 'Publish'
        page.locator("tp-yt-paper-radio-button[name=\"PUBLIC\"]").click()
        _wait_for_selector(page, SELECTORS["publish_button"], cfg.nav_timeout_ms)
        page.locator(SELECTORS["publish_button"]).click()
        print("Clicked Publish (immediate).")
        return "published"
    else:
        print(f"Scheduling for {schedule_time_local.strftime("%Y-%m-%d %H:%M")}")
        page.locator(SELECTORS["visibility_radio_button"]).click()

        # Open date picker
        _wait_for_selector(page, SELECTORS["schedule_date_input"], cfg.nav_timeout_ms)
        page.locator(SELECTORS["schedule_date_input"]).click()
        
        # Set date (Playwright can directly fill, simpler than clicking calendar)
        schedule_date_str = schedule_time_local.strftime("%b %d, %Y") # e.g., Jan 01, 2026
        page.fill(SELECTORS["schedule_date_input"], schedule_date_str)

        # Set time
        _wait_for_selector(page, SELECTORS["schedule_time_input"], cfg.nav_timeout_ms)
        page.fill(SELECTORS["schedule_time_input"], schedule_time_local.strftime("%I:%M %p")) # e.g., 03:00 PM

        _wait_for_selector(page, SELECTORS["schedule_button"], cfg.nav_timeout_ms)
        page.locator(SELECTORS["schedule_button"]).click()
        print("Clicked Schedule button.")
        return "scheduled"

def _verify_upload_success(page: Page, cfg: YouTubeWorkerConfig, publish_type: str) -> Optional[str]:
    print("Verifying upload success...")
    # Wait for the confirmation dialog or redirect to video details
    try:
        # This selector is for the dialog that appears after successful upload and schedule/publish
        _wait_for_selector(page, SELECTORS["video_link_text"], 120_000) # Give more time for processing
        link_el = page.locator(SELECTORS["video_link_text"]).first
        video_link_text = link_el.inner_text().strip()
        href = link_el.get_attribute("href")
        video_link = None
        if href:
            # href may be relative
            if href.startswith("http"):
                video_link = href
            else:
                video_link = "https://studio.youtube.com" + href
        elif video_link_text.startswith("http"):
            video_link = video_link_text

        if not video_link:
            raise RuntimeError(f"Upload dialog found but could not extract video URL (text='{video_link_text}', href={href})")

        print(f"Upload successful! Video URL: {video_link}")
        
        # Click close button to dismiss dialog
        try:
            _wait_for_selector(page, SELECTORS["close_button"], cfg.nav_timeout_ms)
            page.locator(SELECTORS["close_button"]).click()
            print("Closed upload success dialog.")
        except PWTimeout:
            print("Close button not found, dialog may have closed itself or page redirected.")

        return video_link

    except PWTimeout:
        # Check for error dialogs
        if page.locator(SELECTORS["error_dialog"]).is_visible():
            error_text = page.locator(SELECTORS["error_dialog"]).inner_text()
            raise RuntimeError(f"Upload failed with dialog error: {error_text}")
        
        # Check for stuck processing (if video link not found after long wait)
        if page.locator(SELECTORS["processing_progress"]).is_visible():
            progress_text = page.locator(SELECTORS["processing_progress"]).inner_text()
            if "Checks complete" not in progress_text and "Processing complete" not in progress_text:
                raise RuntimeError(f"Upload stuck in processing: {progress_text}. Reschedule and retry.")

        raise RuntimeError("Upload verification timed out. No video link found.")


def run_once(cfg: Optional[YouTubeWorkerConfig] = None, channel_name: Optional[str] = None) -> int:
    """Claims 1 queued YouTube job and performs a stub publish:

    - launches the channel's Chrome profile
    - opens YouTube Studio
    - verifies session is logged in

    Returns exit code (0=did work, 2=no job)."""

    cfg = cfg or YouTubeWorkerConfig()
    
    # Ensure pytz is available for timezone operations
    try:
        import pytz
    except ImportError:
        print("Error: pytz not installed. Please run 'pip install pytz'.")
        return 1

    job = get_next_job(platform="youtube", channel_name=channel_name)
    if not job:
        return 2

    job_id = job["job_id"]
    ch = job["channel_name"]
    profile_path = _profile_path_for_channel(cfg, ch)

    # Retrieve made_for_kids status from channel definitions or assume False
    channel_def = CHANNELS.get(ch, {})
    made_for_kids_status = channel_def.get("made_for_kids", False)

    # Ensure profile dir exists (it should be created by setup_wizard)
    os.makedirs(profile_path, exist_ok=True)

    page = None
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

            _log_step(job_id, "open studio")
            _login_to_studio_if_needed(page, cfg)

            _log_step(job_id, "click upload")
            _click_upload(page, cfg)

            # Use job data for file, title, description
            video_file_path = job["render_path"]
            if not os.path.exists(video_file_path):
                raise FileNotFoundError(f"Rendered video file not found: {video_file_path}")

            _log_step(job_id, f"set input file: {video_file_path}")
            _upload_file(page, cfg, video_file_path)

            page.wait_for_timeout(5000)

            _log_step(job_id, "fill details")
            _fill_details(page, cfg, job["caption_text"], job["caption_text"], made_for_kids_status)

            # schedule_at is stored as ISO string; treat as UTC if naive.
            _log_step(job_id, "visibility/schedule")
            schedule_at_dt = datetime.fromisoformat(job["schedule_at"])
            if schedule_at_dt.tzinfo is None:
                schedule_at_dt = schedule_at_dt.replace(tzinfo=timezone.utc)

            publish_type = _set_visibility_and_schedule(page, cfg, schedule_at_dt, cfg.timezone)

            _log_step(job_id, f"verify success ({publish_type})")
            video_url = _verify_upload_success(page, cfg, publish_type)
            if not video_url:
                raise RuntimeError("No video URL returned by verification")

            # Mark job succeeded only if we have a URL
            update_job_status(job_id, "succeeded", post_url=video_url, platform_post_id=video_url.split("/")[-1])

            context.close()
        return 0

    except Exception as e:
        if page is not None:
            _save_failure_artifacts(page, job_id)
        error_class = "unknown_error"
        error_detail = str(e)

        if "Not logged in" in error_detail:
            error_class = "auth_error"
        elif "Upload verification timed out" in error_detail:
            error_class = "upload_timeout"
        elif "Unexpected URL" in error_detail:
            error_class = "ui_navigation_error"
        elif "Element is not visible" in error_detail or "selector" in error_detail.lower():
            error_class = "ui_selector_error"
        elif "Upload failed with dialog error" in error_detail:
            error_class = "yt_dialog_error"
        elif "stuck in processing" in error_detail:
            error_class = "yt_processing_stuck"

        fail_job(job_id, error_class=error_class, error_detail=error_detail)
        return 1


if __name__ == "__main__":
    # This requires a pre-existing job in the queue
    # For testing, you might need to add a dummy job and ensure a dummy video file exists
    print("--- Running YouTube Worker (Full Upload Stub) ---")
    # Example: create a dummy video file for testing
    if not os.path.exists("renders/x.mp4"):
        os.makedirs("renders", exist_ok=True)
        with open("renders/x.mp4", "w") as f:
            f.write("dummy video content")

    code = run_once(YouTubeWorkerConfig(headless=False)) # Run headful for debugging
    print(f"Worker exited with code: {code}")
    raise SystemExit(code)
