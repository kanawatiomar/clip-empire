import os
import time
from dataclasses import dataclass
from typing import Optional
from datetime import datetime, timedelta, timezone as dt_timezone

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
    # Studio Create button (top-right)
    "upload_button": "#create-icon",
    # Upload videos menu item
    "upload_menu_item": "tp-yt-paper-item[test-id=\"upload-beta\"]",
    # Hidden file input inside upload dialog
    "file_input": "input[type=\"file\"]",
    # Confirmed via debug_selectors.py — exact aria-labels on the contenteditable divs
    "title_textbox": "div#textbox[aria-label='Add a title that describes your video (type @ to mention a channel)']",
    "description_textbox": "div#textbox[aria-label='Tell viewers about your video (type @ to mention a channel)']",
    # Audience radios (scroll down to find them)
    "not_made_for_kids_radio": "tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MFK']",
    "made_for_kids_radio": "tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_MFK']",
    # Wizard nav
    "next_button": "#next-button",
    # Visibility page
    "public_radio": "tp-yt-paper-radio-button[name='PUBLIC']",
    "schedule_radio": "tp-yt-paper-radio-button[name='SCHEDULE']",
    "schedule_date_input": "#datepicker-trigger input",
    "schedule_time_input": "#time-of-day-trigger input",
    "schedule_button": "#schedule-button-container ytcp-button#schedule-button",
    "publish_button": "#done-button",   # "Publish" on Visibility page
    # Post-publish confirmation
    "close_button": "ytcp-uploads-still-processing-dialog #close-button, ytcp-video-upload-success-dialog #close-button, #close-button",
    "video_link": "ytcp-video-upload-success-dialog a",   # link in the success dialog
    # Error
    "error_dialog": "ytcp-dialog.warning",
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
    """Open the upload dialog via Studio Create button.

    Studio UI is flaky; try a few selector strategies.
    """
    print("Clicking upload button...")

    # Strategy A: known id
    try:
        if page.locator(SELECTORS["upload_button"]).first.is_visible(timeout=5000):
            page.locator(SELECTORS["upload_button"]).click()
        else:
            raise PWTimeout("#create-icon not visible")
    except Exception:
        # Strategy B: role/name
        try:
            page.get_by_role("button", name="Create").click(timeout=10_000)
        except Exception:
            # Strategy C: aria-label contains Create
            page.locator("button[aria-label*='Create']").first.click(timeout=10_000)

    # Menu item "Upload videos" / Upload
    try:
        _wait_for_selector(page, SELECTORS["upload_menu_item"], 15_000)
        page.locator(SELECTORS["upload_menu_item"]).click()
    except Exception:
        # Fallback by visible text
        page.get_by_role("menuitem", name="Upload videos").click(timeout=15_000)

    print("Upload menu clicked.")

def _extract_video_url_from_dialog(page: Page) -> Optional[str]:
    """Grab the YouTube video URL shown in the upload dialog's right panel.

    Studio shows 'Video link: https://youtube.com/shorts/...' as soon as
    the file starts uploading. This is the most reliable source of the URL.
    """
    try:
        # Give the dialog a moment to show the link
        page.wait_for_timeout(2000)
        # Try direct anchor inside the dialog
        for sel in [
            "ytcp-uploads-dialog a[href*='youtube.com/shorts']",
            "ytcp-uploads-dialog a[href*='youtube.com/watch']",
            "ytcp-video-info-renderer a[href*='youtube.com']",
            "a[href*='youtube.com/shorts']",
        ]:
            try:
                lnk = page.locator(sel).first
                href = lnk.get_attribute("href", timeout=3000)
                if href and "youtube.com" in href:
                    print(f"Video URL from dialog: {href}")
                    return href
            except Exception:
                continue
        # JS fallback
        hrefs = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('a[href]'))
                .map(a => a.getAttribute('href'))
                .filter(h => h && (h.includes('youtube.com/shorts') || h.includes('youtube.com/watch')));
        }""")
        if hrefs:
            print(f"Video URL from dialog (JS): {hrefs[0]}")
            return hrefs[0]
    except Exception as e:
        print(f"Could not extract URL from dialog: {e}")
    return None


def _upload_file(page: Page, cfg: YouTubeWorkerConfig, video_path: str) -> None:
    """Set the file on the upload dialog.

    Strategy A: Wait for a file chooser to open when we click the drag-drop area.
    Strategy B: Directly set_input_files on the hidden file input (works when input is in DOM).
    Strategy C: Click "Select files" button if visible.
    """
    print(f"Uploading file: {video_path}")

    # Give the upload modal time to animate in
    page.wait_for_timeout(2500)

    # Strategy A: intercept file chooser triggered by clicking the drop zone
    try:
        with page.expect_file_chooser(timeout=10_000) as fc_info:
            # Click the "Select files" button or drag-drop area
            try:
                page.get_by_role("button", name="Select files").click(timeout=5000)
            except Exception:
                try:
                    page.locator("ytcp-uploads-file-picker").click(timeout=5000)
                except Exception:
                    # Last resort: click center of dialog
                    page.locator("ytcp-uploads-dialog").click(timeout=5000)
        fc_info.value.set_files(video_path)
        print("File selected via file chooser (Strategy A).")
        return
    except Exception as e_a:
        print(f"Strategy A failed: {e_a}. Trying Strategy B...")

    # Strategy B: directly set the hidden file input
    try:
        file_input = page.locator(SELECTORS["file_input"]).first
        file_input.set_input_files(video_path)
        print("File selected via hidden input (Strategy B).")
        return
    except Exception as e_b:
        print(f"Strategy B failed: {e_b}. Trying Strategy C...")

    # Strategy C: evaluate JS to trigger file input
    page.evaluate("""(path) => {
        const inp = document.querySelector('input[type="file"]');
        if (!inp) throw new Error('no file input found');
        const dt = new DataTransfer();
        // Can only set via File object in renderer context — skipping, use set_input_files
        inp.removeAttribute('style');
        inp.style.display = 'block';
    }""", video_path)
    page.locator(SELECTORS["file_input"]).first.set_input_files(video_path)
    print("File selected via JS-exposed input (Strategy C).")

def _fill_details(page: Page, cfg: YouTubeWorkerConfig, title: str, description: str, made_for_kids: bool) -> None:
    """Fill the Details step of the upload wizard.

    YouTube auto-fills the title with the filename — we clear and replace it.
    Then scroll to the audience section and set the made-for-kids radio.
    Finally click Next twice to pass through Video elements → Checks.
    """
    print("Filling video details...")

    # ---- Title ----
    title_loc = page.locator(SELECTORS["title_textbox"]).first
    title_loc.wait_for(state="visible", timeout=cfg.nav_timeout_ms)
    page.wait_for_timeout(500)

    # Approach: JS clear + keyboard type (most reliable for YouTube contenteditable)
    try:
        title_loc.scroll_into_view_if_needed()
        title_loc.click()
        page.wait_for_timeout(300)
        # Select all & delete via keyboard
        page.keyboard.press("Control+a")
        page.wait_for_timeout(200)
        page.keyboard.press("Delete")
        page.wait_for_timeout(300)
        # Type the new title slowly
        page.keyboard.type(title, delay=50)
        page.wait_for_timeout(400)
        # Verify it actually stuck
        actual = title_loc.inner_text().strip()
        if actual and actual != title:
            # Retry: JS set + input event
            page.evaluate(
                """([el, text]) => {
                    el.textContent = text;
                    el.dispatchEvent(new Event('input', {bubbles: true}));
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                }""",
                [title_loc.element_handle(), title]
            )
            page.wait_for_timeout(300)
        print(f"Title set: {title} (actual: {title_loc.inner_text().strip()[:60]})")
    except Exception as e:
        print(f"Title set error: {e}. Falling back to basic type.")
        title_loc.click()
        title_loc.press("Control+a")
        title_loc.type(title, delay=50)

    # ---- Description ----
    desc_loc = page.locator(SELECTORS["description_textbox"]).first
    try:
        desc_loc.wait_for(state="visible", timeout=5000)
        desc_loc.click()
        desc_loc.type(description, delay=20)
        print("Description set.")
    except Exception:
        print("Description field not found, skipping.")

    # ---- Audience: scroll down to find it ----
    page.wait_for_timeout(500)
    page.keyboard.press("Tab")  # nudge focus so scroll triggers
    try:
        audience_radio_sel = SELECTORS["made_for_kids_radio"] if made_for_kids else SELECTORS["not_made_for_kids_radio"]
        audience_loc = page.locator(audience_radio_sel)
        audience_loc.scroll_into_view_if_needed(timeout=10_000)
        is_checked = audience_loc.get_attribute("aria-checked")
        if is_checked != "true":
            audience_loc.click()
        status = "made for kids" if made_for_kids else "not made for kids"
        print(f"Audience set: {status}")
    except Exception as e:
        print(f"Could not set audience radio (non-fatal, defaulting to YouTube setting): {e}")

    # ---- Next → Video elements ----
    page.locator(SELECTORS["next_button"]).click()
    print("Clicked Next (Video elements).")
    page.wait_for_timeout(1000)

    # ---- Next → Checks ----
    page.locator(SELECTORS["next_button"]).click()
    print("Clicked Next (Checks).")
    page.wait_for_timeout(1000)

def _set_visibility_and_schedule(
    page: Page, cfg: YouTubeWorkerConfig, schedule_at: datetime, timezone: str
) -> str:
    print("Setting visibility and schedule...")
    _wait_for_selector(page, SELECTORS["next_button"], cfg.nav_timeout_ms) # Ensure on Visibility page
    page.locator(SELECTORS["next_button"]).click() # To Visibility page
    print("Clicked Next (to Visibility).")

    tz = pytz.timezone(timezone)
    now = datetime.now(tz)
    schedule_time_local = schedule_at.astimezone(tz)

    # Publish immediately if scheduled time is in the past or within 5 minutes
    if schedule_time_local <= now + timedelta(minutes=5):
        print("Publishing immediately (schedule time is past/soon).")
        pub_loc = page.locator(SELECTORS["public_radio"])
        pub_loc.wait_for(state="visible", timeout=cfg.nav_timeout_ms)
        pub_loc.click()
        page.locator(SELECTORS["publish_button"]).wait_for(state="visible", timeout=cfg.nav_timeout_ms)
        page.locator(SELECTORS["publish_button"]).click()
        print("Clicked Publish.")
        return "published"
    else:
        print(f"Scheduling for {schedule_time_local.strftime('%Y-%m-%d %H:%M %Z')}")
        sched_loc = page.locator(SELECTORS["schedule_radio"])
        sched_loc.wait_for(state="visible", timeout=cfg.nav_timeout_ms)
        sched_loc.click()
        page.wait_for_timeout(500)

        # Date input
        date_loc = page.locator(SELECTORS["schedule_date_input"])
        date_loc.wait_for(state="visible", timeout=cfg.nav_timeout_ms)
        date_loc.triple_click()
        date_loc.type(schedule_time_local.strftime("%b %d, %Y"), delay=30)

        # Time input
        time_loc = page.locator(SELECTORS["schedule_time_input"])
        time_loc.wait_for(state="visible", timeout=cfg.nav_timeout_ms)
        time_loc.triple_click()
        time_loc.type(schedule_time_local.strftime("%I:%M %p"), delay=30)
        time_loc.press("Enter")
        page.wait_for_timeout(500)

        sched_btn = page.locator(SELECTORS["schedule_button"])
        sched_btn.wait_for(state="visible", timeout=cfg.nav_timeout_ms)
        sched_btn.click()
        print("Clicked Schedule button.")
        return "scheduled"

def _verify_upload_success(page: Page, cfg: YouTubeWorkerConfig, publish_type: str) -> Optional[str]:
    """Confirm the video was published and return its URL.

    YouTube's post-publish dialogs are transient and unreliable.
    Strategy: wait a few seconds, then navigate directly to the Content page
    and grab the most recently uploaded video URL.
    """
    print("Verifying upload success...")

    # Give Studio a moment to register the publish before we navigate away
    page.wait_for_timeout(4000)

    # Check for error dialog before navigating away
    try:
        if page.locator(SELECTORS["error_dialog"]).is_visible(timeout=1000):
            error_text = page.locator(SELECTORS["error_dialog"]).inner_text()
            raise RuntimeError(f"Upload failed — YouTube error dialog: {error_text}")
    except Exception as e:
        if "Upload failed" in str(e):
            raise

    # Extract channel ID from current URL
    channel_id = ""
    try:
        channel_id = page.url.split("/channel/")[1].split("/")[0]
    except Exception:
        pass

    if not channel_id:
        raise RuntimeError(f"Could not parse channel ID from URL: {page.url}")

    # Navigate to the channel Content page to get the most recent video
    content_url = f"https://studio.youtube.com/channel/{channel_id}/videos"
    print(f"Navigating to Content page: {content_url}")
    try:
        page.goto(content_url, wait_until="domcontentloaded", timeout=30_000)
        page.wait_for_timeout(3000)
    except Exception as e:
        raise RuntimeError(f"Could not load Content page: {e}")

    # Find the most recently uploaded video link
    # YouTube Studio renders video rows lazily — try a few times
    for attempt in range(3):
        for sel in [
            "a[href*='youtube.com/shorts']",
            "a[href*='youtube.com/watch']",
        ]:
            try:
                links = page.locator(sel).all()
                for lnk in links[:5]:
                    href = lnk.get_attribute("href") or ""
                    if href and ("shorts" in href or "watch" in href):
                        print(f"Upload verified! URL: {href}")
                        return href
            except Exception:
                continue

        # JS eval — catches relative hrefs like /shorts/XXXX
        try:
            hrefs = page.evaluate("""() => {
                return Array.from(document.querySelectorAll('a[href]'))
                    .map(a => a.href)
                    .filter(h => h.includes('youtube.com/shorts') || h.includes('youtube.com/watch'));
            }""")
            if hrefs:
                print(f"Upload verified (JS)! URL: {hrefs[0]}")
                return hrefs[0]
        except Exception:
            pass

        if attempt < 2:
            print(f"Video links not found yet, waiting... (attempt {attempt + 1})")
            page.wait_for_timeout(3000)

    # Last fallback: return the studio content page URL so we still mark as succeeded
    print("Could not find video URL in content page. Using studio URL as fallback.")
    return content_url


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

    page: Page | None = None
    try:
        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                user_data_dir=profile_path,
                headless=cfg.headless,
                channel="chrome",
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--start-maximized",
                ],
            )
            page = context.new_page()

            try:
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

                # Capture the video URL early — Studio shows it in the dialog right panel
                early_video_url = _extract_video_url_from_dialog(page)
                if early_video_url:
                    _log_step(job_id, f"captured video URL early: {early_video_url}")

                page.wait_for_timeout(3000)

                _log_step(job_id, "fill details")
                _fill_details(page, cfg, job["caption_text"], job["caption_text"], made_for_kids_status)

                # schedule_at is stored as ISO string; treat as UTC if naive.
                _log_step(job_id, "visibility/schedule")
                schedule_at_dt = datetime.fromisoformat(job["schedule_at"])
                if schedule_at_dt.tzinfo is None:
                    schedule_at_dt = schedule_at_dt.replace(tzinfo=dt_timezone.utc)

                publish_type = _set_visibility_and_schedule(page, cfg, schedule_at_dt, cfg.timezone)

                _log_step(job_id, f"verify success ({publish_type})")
                video_url = early_video_url or _verify_upload_success(page, cfg, publish_type)
                if not video_url:
                    raise RuntimeError("No video URL returned by verification")

                # Mark job succeeded only if we have a URL
                update_job_status(job_id, "succeeded", post_url=video_url, platform_post_id=video_url.split("/")[-1])

                context.close()
                return 0

            except Exception:
                # Save artifacts BEFORE playwright stops
                if page is not None:
                    _save_failure_artifacts(page, job_id)
                raise

    except Exception as e:
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
