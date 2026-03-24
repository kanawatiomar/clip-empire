import os
# -*- coding: utf-8 -*-

import time

import urllib.request

import json as _json

from dataclasses import dataclass

from typing import Optional

from datetime import datetime, timedelta, timezone as dt_timezone



# Ã¢"â‚¬Ã¢"â‚¬ Discord alert channels (Clip Empire server) Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬

# Load .env from repo root if not already set

_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")

if os.path.exists(_env_path) and not os.environ.get("DISCORD_BOT_TOKEN"):

    for _line in open(_env_path):

        if _line.startswith("DISCORD_BOT_TOKEN="):

            os.environ["DISCORD_BOT_TOKEN"] = _line.strip().split("=", 1)[1]

_DISCORD_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")

_CH_SUCCESS  = "1480139743709888665"  # #publish-success

_CH_FAILURES = "1480139754514157729"  # #publish-failures

_CH_QUEUED   = "1480139732284604544"  # #queued-jobs



def _discord_post(channel_id: str, message: str) -> None:

    """Fire-and-forget Discord message via direct API (urllib) â€” supports multiline messages."""

    try:

        payload = _json.dumps({"content": message}).encode("utf-8")

        req = urllib.request.Request(

            f"https://discord.com/api/v10/channels/{channel_id}/messages",

            data=payload,

            headers={

                "Authorization": f"Bot {_DISCORD_TOKEN}",

                "Content-Type": "application/json",

                "User-Agent": "ClipEmpire/1.0",

            },

            method="POST",

        )

        with urllib.request.urlopen(req, timeout=15) as resp:

            print(f"[discord] Alert sent to {channel_id} (status {resp.status})")

    except Exception as e:

        print(f"[discord] Alert failed: {e}")

# Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬Ã¢"â‚¬



from playwright.sync_api import sync_playwright, Page, expect, TimeoutError as PWTimeout

import pytz # Will need 'pip install pytz'



from publisher.queue import get_next_job, update_job_status, fail_job, save_early_url, get_early_url

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

    # Confirmed via debug_selectors.py - exact aria-labels on the contenteditable divs

    "title_textbox": "div#textbox[aria-label='Add a title that describes your video (type @ to mention a channel)']",

    "description_textbox": "div#textbox[aria-label='Tell viewers about your video (type @ to mention a channel)']",

    # Tags field (inside "More options" section)

    "tags_input": "input[aria-label='Tags']",

    "more_options_button": "ytcp-button#toggle-button",

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

    # Headless mode: no visible browser window (better for background operation)
    headless: bool = True

    # Timezone for scheduling

    timezone: str = "America/Denver"





def _profile_path_for_channel(cfg: YouTubeWorkerConfig, channel_name: str) -> str:

    return os.path.join(cfg.profiles_dir, channel_name)


def _studio_url_for_channel(channel_name: str) -> str:
    """Returns the direct Studio URL for the channel, or generic Studio URL as fallback."""
    try:
        import sqlite3 as _sq3
        conn = _sq3.connect(os.path.join(os.path.dirname(__file__), "..", "accounts", "accounts.db"))
        row = conn.execute(
            "SELECT youtube_channel_id FROM accounts WHERE channel_name=?", (channel_name,)
        ).fetchone()
        conn.close()
        if row and row[0]:
            return f"https://studio.youtube.com/channel/{row[0]}"
    except Exception:
        pass
    return YOUTUBE_STUDIO_URL





def _wait_for_selector(page: Page, selector: str, timeout_ms: int) -> None:

    expect(page.locator(selector)).to_be_visible(timeout=timeout_ms)





def _login_to_studio_if_needed(page: Page, cfg: YouTubeWorkerConfig, studio_url: str = YOUTUBE_STUDIO_URL) -> None:

    """Navigates to Studio and verifies login. Raises error if redirected or not on Studio page."""

    # Navigate to base Studio first (avoids channel-specific URL triggering re-auth)
    # then navigate to the target channel URL once session is confirmed.
    base_url = YOUTUBE_STUDIO_URL
    page.goto(base_url, wait_until="domcontentloaded", timeout=cfg.nav_timeout_ms)
    page.wait_for_timeout(2000)

    # If base URL already redirected to sign-in, handle it before going to channel URL
    if "studio.youtube.com" in page.url and studio_url != base_url:
        page.goto(studio_url, wait_until="domcontentloaded", timeout=cfg.nav_timeout_ms)

    url = page.url

    # Handle Google "Verify it's you" / "Sign in again" interstitial
    # This shows when Google needs re-confirmation but credentials are already saved
    if "accounts.google.com" in url:
        # Try clicking through the interstitial (Next button, then password autofill)
        for _attempt in range(3):
            try:
                # "Verify it's you" page â†’ click Next (id=identifierNext or button)
                page.evaluate("""() => {
                    const el = document.getElementById('identifierNext')
                        || document.querySelector('#next')
                        || document.querySelector('[data-primary-action-label]')
                        || Array.from(document.querySelectorAll('button')).find(b => b.innerText.trim() === 'Next');
                    if (el) el.click();
                }""")
                page.wait_for_timeout(3000)
            except Exception:
                pass
            try:
                # Password page â†’ click saved password or submit
                pwd = page.locator("input[type=password]").first
                if pwd.count() > 0:
                    pwd.wait_for(state="visible", timeout=5000)
                    pwd.click()
                    page.wait_for_timeout(800)
                    page.keyboard.press("Return")
                    page.wait_for_timeout(4000)
            except Exception:
                pass
            page.wait_for_timeout(2000)
            if "accounts.google.com" not in page.url:
                break  # made it past login
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

        // Can only set via File object in renderer context - skipping, use set_input_files

        inp.removeAttribute('style');

        inp.style.display = 'block';

    }""", video_path)

    page.locator(SELECTORS["file_input"]).first.set_input_files(video_path)

    print("File selected via JS-exposed input (Strategy C).")



def _upload_thumbnail(page: Page, thumbnail_path: str) -> None:
    """Upload a custom thumbnail in the Details step.

    YouTube Studio has a thumbnail upload button in the Details dialog.
    We click it, intercept the file chooser, and set the thumbnail file.
    """
    if not thumbnail_path or not os.path.exists(thumbnail_path):
        print(f"[thumbnail] Skipping â€” file not found: {thumbnail_path}")
        return
    try:
        # Scroll to thumbnail section
        thumb_btn = page.locator("button#still-selection-button, ytcp-thumbnail-uploader button, [test-id='thumbnail-upload-button']").first
        if thumb_btn.count() == 0:
            # Try broader selector
            thumb_btn = page.get_by_text("Upload thumbnail", exact=False).first
        thumb_btn.scroll_into_view_if_needed(timeout=5000)
        page.wait_for_timeout(500)
        with page.expect_file_chooser(timeout=8000) as fc_info:
            thumb_btn.click(timeout=5000)
        fc_info.value.set_files(thumbnail_path)
        page.wait_for_timeout(1500)
        print(f"[thumbnail] Uploaded: {os.path.basename(thumbnail_path)}")
    except Exception as e:
        print(f"[thumbnail] Upload skipped (non-fatal): {e}")


def _fill_details(page: Page, cfg: YouTubeWorkerConfig, title: str, description: str, made_for_kids: bool, hashtags: list = None, thumbnail_path: str = None) -> None:

    """Fill the Details step of the upload wizard.



    YouTube auto-fills the title with the filename - we clear and replace it.

    Then scroll to the audience section and set the made-for-kids radio.

    Finally click Next twice to pass through Video elements Ã¢â€ ' Checks.

    """

    print("Filling video details...")

    hashtags = hashtags or []



    # ---- Title ----

    title_loc = page.locator(SELECTORS["title_textbox"]).first

    title_loc.wait_for(state="visible", timeout=cfg.nav_timeout_ms)

    title_loc.click()

    title_loc.press("Control+a")

    title_loc.type(title, delay=30)

    print(f"Title set: {title}")

    # ---- Thumbnail ----
    if thumbnail_path:
        _upload_thumbnail(page, thumbnail_path)

    # ---- Description (caption + hashtags appended) ----

    desc_loc = page.locator(SELECTORS["description_textbox"]).first

    try:

        desc_loc.wait_for(state="visible", timeout=5000)

        desc_loc.click()

        full_description = description

        if hashtags:

            tag_line = " ".join(f"#{t.lstrip('#')}" for t in hashtags)

            full_description = f"{description}\n\n{tag_line}"

        desc_loc.type(full_description, delay=20)

        print(f"Description set with {len(hashtags)} hashtags.")

    except Exception:

        print("Description field not found, skipping.")



    # ---- Tags (via More options) ----

    if hashtags:

        try:

            more_btn = page.locator(SELECTORS["more_options_button"]).first

            more_btn.wait_for(state="visible", timeout=5000)

            more_btn.click()

            page.wait_for_timeout(1000)

            tags_input = page.locator(SELECTORS["tags_input"]).first

            tags_input.wait_for(state="visible", timeout=5000)

            tags_input.click()

            tags_str = ",".join(t.lstrip('#') for t in hashtags)

            tags_input.type(tags_str, delay=20)

            # Press Enter or comma to confirm tags

            tags_input.press("Return")

            print(f"Tags set: {tags_str}")

        except Exception as e:

            print(f"Could not set tags (non-fatal): {e}")



    # ---- Audience: scroll down to find it ----

    page.wait_for_timeout(1000)

    page.keyboard.press("Tab")  # nudge focus so scroll triggers

    # Try multiple selectors â€” YouTube has changed the name attribute over time
    audience_selectors_not_kids = [
        "tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_NOT_MFK']",
        "tp-yt-paper-radio-button[name='VIDEO_NOT_MADE_FOR_KIDS']",
        "tp-yt-paper-radio-button[name='NOT_MADE_FOR_KIDS']",
    ]
    audience_selectors_kids = [
        "tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS_MFK']",
        "tp-yt-paper-radio-button[name='VIDEO_MADE_FOR_KIDS']",
        "tp-yt-paper-radio-button[name='MADE_FOR_KIDS']",
    ]
    target_selectors = audience_selectors_kids if made_for_kids else audience_selectors_not_kids

    audience_set = False
    for sel in target_selectors:
        try:
            loc = page.locator(sel).first
            loc.scroll_into_view_if_needed(timeout=5_000)
            page.wait_for_timeout(500)
            if loc.get_attribute("aria-checked") != "true":
                loc.click()
                page.wait_for_timeout(500)
            # Verify it's checked
            if loc.get_attribute("aria-checked") == "true":
                status = "made for kids" if made_for_kids else "not made for kids"
                print(f"Audience set: {status} (selector: {sel})")
                audience_set = True
                break
        except Exception:
            continue

    if not audience_set:
        # JS fallback: find any "No" radio (not made for kids) in the audience section
        try:
            result = page.evaluate("""
                () => {
                    const radios = Array.from(document.querySelectorAll('tp-yt-paper-radio-button'));
                    const notKids = radios.find(r => {
                        const name = r.getAttribute('name') || '';
                        return name.includes('NOT') || name.includes('not');
                    });
                    if (notKids) { notKids.click(); return notKids.getAttribute('name'); }
                    return null;
                }
            """)
            if result:
                print(f"Audience set via JS fallback: {result}")
                audience_set = True
                page.wait_for_timeout(500)
        except Exception as e:
            print(f"JS audience fallback failed: {e}")

    if not audience_set:
        print("WARNING: Could not set audience â€” video may be saved as Draft. Check studio manually.")

    page.wait_for_timeout(1000)

    # ---- Next â†’ Video elements ----

    page.locator(SELECTORS["next_button"]).click()

    print("Clicked Next (Video elements).")

    page.wait_for_timeout(2000)



    # ---- Next â†’ Checks ----

    page.locator(SELECTORS["next_button"]).click()

    print("Clicked Next (Checks).")

    page.wait_for_timeout(3000)  # Give the content check time to run



def _set_visibility_and_schedule(

    page: Page, cfg: YouTubeWorkerConfig, schedule_at: datetime, timezone: str

) -> str:

    print("Setting visibility and schedule...")

    # Wait for content check to complete â€” next button must be enabled (not just visible)
    _wait_for_selector(page, SELECTORS["next_button"], cfg.nav_timeout_ms)
    # Poll until next button is enabled (content check spinner gone)
    for _attempt in range(30):
        try:
            btn = page.locator(SELECTORS["next_button"]).first
            disabled = btn.get_attribute("disabled")
            aria_disabled = btn.get_attribute("aria-disabled")
            if disabled is None and aria_disabled != "true":
                break
        except Exception:
            pass
        page.wait_for_timeout(1000)

    page.locator(SELECTORS["next_button"]).click()  # To Visibility page

    print("Clicked Next (to Visibility).")



    tz = pytz.timezone(timezone)

    now = datetime.now(tz)

    schedule_time_local = schedule_at.astimezone(tz)

    time_delta = schedule_time_local - now

    use_scheduling = time_delta.total_seconds() > 15 * 60  # More than 15 minutes in future

    

    if use_scheduling:

        print(f"Scheduling video for {schedule_time_local.isoformat()} (in {time_delta.total_seconds()/60:.1f} minutes)")

    else:

        print(f"Publishing immediately as Public (schedule_at is {time_delta.total_seconds()/60:.1f} minutes from now)")



    # Wait for the visibility page to fully load (radio group must be present)

    page.wait_for_selector("#privacy-radios", timeout=cfg.nav_timeout_ms)

    page.wait_for_timeout(2000)  # extra settle time for web components



    if use_scheduling:

        # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

        # SCHEDULING PATH: Click Schedule radio, set date/time, click Schedule button

        # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

        print("Selecting SCHEDULE option...")

        # Click the Schedule radio button using JS dispatch (same pattern as Public)
        page.evaluate("""() => {
            const radios = document.querySelectorAll('tp-yt-paper-radio-button');
            for (const r of radios) {
                if (r.getAttribute('name') === 'SCHEDULE') {
                    r.click();
                    r.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
                    r.dispatchEvent(new Event('tap', {bubbles: true}));
                    const inner = r.shadowRoot && r.shadowRoot.querySelector('#radioButton');
                    if (inner) inner.click();
                    break;
                }
            }
        }""")

        page.wait_for_timeout(1000)

        # Wait for date/time inputs to appear

        try:

            date_input = page.locator(SELECTORS["schedule_date_input"])

            date_input.wait_for(state="visible", timeout=10000)

            print("Date input appeared.")

        except Exception as e:

            print(f"WARNING: Date input did not appear: {e}")



        # Set the date input (MM/DD/YYYY format)

        date_str = schedule_time_local.strftime("%m/%d/%Y")

        print(f"Setting date to: {date_str}")

        try:

            date_input = page.locator(SELECTORS["schedule_date_input"])

            date_input.fill(date_str)

            date_input.dispatch_event("change")

            page.wait_for_timeout(1000)

        except Exception as e:

            print(f"WARNING: Could not set date: {e}")



        # Set the time input (HH:MM AM/PM format)

        time_str = schedule_time_local.strftime("%I:%M %p").lstrip("0")  # Remove leading 0 from hour

        print(f"Setting time to: {time_str}")

        try:

            time_input = page.locator(SELECTORS["schedule_time_input"])

            time_input.fill(time_str)

            time_input.dispatch_event("change")

            page.wait_for_timeout(1000)

        except Exception as e:

            print(f"WARNING: Could not set time: {e}")



        # Click the Schedule button

        print("Clicking Schedule button...")

        try:

            schedule_button = page.locator(SELECTORS["schedule_button"])

            schedule_button.wait_for(state="visible", timeout=10000)

            # Try JS click first

            page.evaluate("""() => {
                const btn = document.querySelector('#schedule-button-container ytcp-button#schedule-button');
                if (btn) {
                    btn.click();
                    btn.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
                }
            }""")

            page.wait_for_timeout(500)

            # Fallback: Playwright click

            try:

                schedule_button.click(force=True, timeout=5000)

            except Exception:

                pass

            page.wait_for_timeout(1000)

            print("Clicked Schedule button.")

        except Exception as e:

            print(f"WARNING: Could not click Schedule button: {e}")



        # Wait for confirmation (upload dialog close or success dialog)

        try:

            page.locator("ytcp-uploads-dialog").wait_for(state="detached", timeout=60000)

            print("Upload dialog closed â€” scheduling confirmed.")

        except Exception:

            try:

                page.locator("ytcp-video-upload-success-dialog").wait_for(state="visible", timeout=15000)

                print("Upload success dialog appeared â€” scheduling confirmed.")

            except Exception:

                print("Dialog wait timed out â€” waiting 5s for scheduling to register...")

                page.wait_for_timeout(5000)



        return f"scheduled:{schedule_at.isoformat()}"



    else:

        # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

        # PUBLISH IMMEDIATELY PATH: Click Public radio and Publish button

        # â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•â•

        # Use multiple strategies to select Public â€” aria-checked alone is not enough
        # (YouTube web components can show aria-checked=true without triggering form state change)
        def _try_select_public() -> bool:
            """Returns True if done-button text became 'Publish'."""
            # Strategy 1: click the inner paper-radio-button directly
            page.evaluate("""() => {
                const radios = document.querySelectorAll('tp-yt-paper-radio-button');
                for (const r of radios) {
                    if (r.getAttribute('name') === 'PUBLIC') {
                        r.click();
                        r.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
                        r.dispatchEvent(new Event('tap', {bubbles: true}));
                        // Also try clicking the inner radio
                        const inner = r.shadowRoot && r.shadowRoot.querySelector('#radioButton');
                        if (inner) inner.click();
                        break;
                    }
                }
            }""")
            page.wait_for_timeout(800)
            # Check if done-button text changed to Publish
            btn_text = page.evaluate("() => { const b = document.querySelector('#done-button'); return b ? b.innerText.trim() : ''; }")
            print(f"  done-button text after JS click: {btn_text!r}")
            return btn_text.lower() == "publish"

        publish_confirmed = False
        for attempt in range(4):
            publish_confirmed = _try_select_public()
            if publish_confirmed:
                print(f"Public selected + done-button is 'Publish' (attempt {attempt+1})")
                break
            # Also try clicking via Playwright locator as backup
            try:
                pub_loc = page.locator(SELECTORS["public_radio"])
                if pub_loc.count() > 0:
                    pub_loc.click(force=True)
                    page.wait_for_timeout(600)
            except Exception:
                pass
            btn_text = page.evaluate("() => { const b = document.querySelector('#done-button'); return b ? b.innerText.trim() : ''; }")
            print(f"  After fallback click attempt {attempt+1}: done-button={btn_text!r}")
            if btn_text.lower() == "publish":
                publish_confirmed = True
                break

        if not publish_confirmed:
            # Last resort: check aria-checked and proceed anyway if it looks right
            final_checked = page.evaluate("() => { const b = document.querySelector('tp-yt-paper-radio-button[name=\"PUBLIC\"]'); return b ? b.getAttribute('aria-checked') : null; }")
            btn_text = page.evaluate("() => { const b = document.querySelector('#done-button'); return b ? b.innerText.trim() : ''; }")
            print(f"WARNING: done-button still shows {btn_text!r} (aria-checked={final_checked}). Proceeding anyway.")

        print("Public visibility confirmed.")

        # Wait for done-button to be clickable, then click
        done_loc = page.locator(SELECTORS["publish_button"])
        done_loc.wait_for(state="visible", timeout=cfg.nav_timeout_ms)

        # Strategy 1: JS click on inner button element (most reliable for Shadow DOM)
        page.evaluate("""() => {
            const outer = document.querySelector('#done-button');
            if (!outer) return;
            // Try inner tp-yt-paper-button first
            const inner = outer.querySelector('tp-yt-paper-button, button, [role="button"]');
            const target = inner || outer;
            target.removeAttribute('disabled');
            target.removeAttribute('aria-disabled');
            target.click();
            target.dispatchEvent(new MouseEvent('click', {bubbles: true, cancelable: true}));
        }""")
        page.wait_for_timeout(500)

        # Strategy 2: Playwright force-click as backup
        try:
            done_loc.click(force=True, timeout=5000)
        except Exception:
            pass

        # Strategy 3: Keyboard Enter as final fallback
        page.wait_for_timeout(300)
        done_loc.press("Enter")

        print("Clicked Publish.")

        # Debug: screenshot right after clicking Publish to see dialog state
        page.wait_for_timeout(2000)
        try:
            page.screenshot(path=f"_publish_debug_{job_id[:8]}.png")
            print(f"Post-publish screenshot saved.")
        except Exception:
            pass

        # Handle "We're still checking your content" confirmation dialog
        # YouTube shows this when content checks haven't completed â€” must click "Publish anyway"
        page.wait_for_timeout(2000)
        try:
            # Look for any dialog with "Publish anyway" button
            publish_anyway = page.locator("tp-yt-paper-button, ytcp-button").filter(has_text="Publish anyway").first
            if publish_anyway.count() > 0 and publish_anyway.is_visible():
                print("'We're still checking your content' dialog appeared â€” clicking 'Publish anyway'...")
                publish_anyway.click(force=True)
                page.wait_for_timeout(1000)
                print("Clicked 'Publish anyway' â€” video will publish as Public.")
        except Exception as e:
            print(f"Publish-anyway dialog check: {e}")

        # Wait for the upload dialog to fully close â€” confirms YouTube accepted the publish.
        # If we navigate away before this, YouTube saves as draft instead of publishing.
        # The dialog closes when YouTube finishes processing the publish action.
        try:
            # Primary: wait for the upload dialog to disappear
            page.locator("ytcp-uploads-dialog").wait_for(state="detached", timeout=60000)
            print("Upload dialog closed â€” publish confirmed.")
        except Exception:
            try:
                # Fallback: wait for post-publish success dialog
                page.locator("ytcp-video-upload-success-dialog").wait_for(state="visible", timeout=15000)
                print("Upload success dialog appeared â€” publish confirmed.")
            except Exception:
                # Last resort: just wait 8 seconds for YouTube to process the click
                print("Dialog wait timed out â€” waiting 8s for publish to register...")
                page.wait_for_timeout(8000)

        return "published"



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

            raise RuntimeError(f"Upload failed - YouTube error dialog: {error_text}")

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

    # YouTube Studio renders video rows lazily - try a few times

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



        # JS eval - catches relative hrefs like /shorts/XXXX

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



    # Could not find video URL on content page â€” return None so caller falls back to early_video_url
    print("Could not find video URL in content page. Falling back to early-captured URL.")

    return None





def run_once(cfg: Optional[YouTubeWorkerConfig] = None, channel_name: Optional[str] = None) -> int:

    """Claims 1 queued YouTube job and performs a stub publish:



    - launches the channel's Chrome profile

    - opens YouTube Studio

    - verifies session is logged in



    Returns exit code (0=did work or nothing to do, 1=real failure)."""



    cfg = cfg or YouTubeWorkerConfig()



    # Ensure pytz is available for timezone operations

    try:

        import pytz

    except ImportError:

        print("Error: pytz not installed. Please run 'pip install pytz'.")

        return 1



    job = get_next_job(platform="youtube", channel_name=channel_name)

    if not job:

        print('No queued jobs ready -- nothing to do.')

        return 0



    job_id = job["job_id"]

    ch = job["channel_name"]

    # Skip jobs for paused channels â€” cancel them so they don't block the queue
    try:
        import sqlite3 as _sq3
        _conn = _sq3.connect("data/clip_empire.db")
        _row = _conn.execute("SELECT status FROM channels WHERE channel_name=?", (ch,)).fetchone()
        _conn.close()
        if _row and _row[0] == "paused":
            print(f"[publisher] Channel {ch} is paused â€” cancelling job {job_id}")
            update_job_status(job_id, "cancelled")
            return 0
    except Exception as _e:
        print(f"[publisher] Channel status check failed (non-fatal): {_e}")

    profile_path = _profile_path_for_channel(cfg, ch)



    # Notify #queued-jobs that we're picking up this job

    title_preview = (job.get("caption_text") or "Untitled")[:80]

    scheduled_str = job.get("schedule_at", "")[:16].replace("T", " ")

    _discord_post(_CH_QUEUED,

        f"[PUBLISHING] **Publishing now** - `{ch}`\n"

        f"**{title_preview}**\n"

        f"Scheduled: {scheduled_str} UTC  |  Job: `{job_id[:8]}`"

    )



    # Retrieve made_for_kids status from channel definitions or assume False

    channel_def = CHANNELS.get(ch, {})

    made_for_kids_status = channel_def.get("made_for_kids", False)



    # Ensure profile dir exists (it should be created by setup_wizard)

    os.makedirs(profile_path, exist_ok=True)



    # Kill any lingering Chrome processes holding the profile lock before launching
    import subprocess as _sp
    _sp.run(["taskkill", "/F", "/IM", "chrome.exe"], capture_output=True)
    _sp.run(["taskkill", "/F", "/IM", "chromium.exe"], capture_output=True)
    import time as _time; _time.sleep(1)

    # Remove SingletonLock if it exists
    import pathlib as _pathlib
    for _lock in ["SingletonLock", "SingletonCookie", "SingletonSocket", "lockfile"]:
        _lp = _pathlib.Path(profile_path) / _lock
        if _lp.exists():
            _lp.unlink(missing_ok=True)

    page: Page | None = None

    try:

        with sync_playwright() as p:

            context = p.chromium.launch_persistent_context(

                user_data_dir=profile_path,

                headless=cfg.headless,

                channel="chrome",  # use system Chrome (not Playwright Chromium â€” blocked by Defender)

                args=[

                    "--disable-blink-features=AutomationControlled",

                    "--start-maximized",

                ],

            )

            page = context.new_page()



            try:

                _log_step(job_id, "open studio")

                _studio_url = _studio_url_for_channel(ch)
                print(f"Navigating to channel-specific Studio: {_studio_url}")
                _login_to_studio_if_needed(page, cfg, studio_url=_studio_url)
                print(f"Successfully reached YouTube Studio: {page.url}")



                _log_step(job_id, "click upload")

                _click_upload(page, cfg)



                # Use job data for file, title, description

                video_file_path = job["render_path"]

                # Duplicate-upload guard: if a previous attempt already uploaded
                # this video (early_url was saved) but crashed before marking
                # succeeded, skip the re-upload and just mark it done.
                _saved_early_url = get_early_url(job_id)
                if _saved_early_url and job.get("attempts", 0) > 1:
                    print(f"[dedup] Retry detected with saved URL {_saved_early_url} â€” skipping re-upload.")
                    update_job_status(job_id, "succeeded", post_url=_saved_early_url, platform_post_id=_saved_early_url.split("/")[-1])
                    _discord_post(_CH_SUCCESS, f"âœ… **{ch}** | `{job.get('caption_text','')}` (retry dedup â€” already uploaded)\n{_saved_early_url}")
                    return 0

                if not os.path.exists(video_file_path):

                    raise FileNotFoundError(f"Rendered video file not found: {video_file_path}")



                _log_step(job_id, f"set input file: {video_file_path}")

                _upload_file(page, cfg, video_file_path)



                # Capture the video URL early - Studio shows it in the dialog right panel
                # (used only as fallback; _verify_upload_success is the primary source)

                early_video_url = _extract_video_url_from_dialog(page)

                if early_video_url:

                    _log_step(job_id, f"captured video URL early (fallback only): {early_video_url}")
                    # Persist immediately â€” crash-safe dedup on retry
                    save_early_url(job_id, early_video_url)

                # Wait for upload to finish (progress bar disappears / Next button becomes enabled)
                _log_step(job_id, "waiting for upload to complete...")
                try:
                    page.wait_for_function(
                        "() => !document.querySelector('ytcp-video-upload-progress[uploading]')",
                        timeout=300_000,  # 5 min max
                    )
                    print("Upload progress complete.")
                except Exception as _wait_err:
                    print(f"Upload progress wait timed out or failed (continuing): {_wait_err}")

                page.wait_for_timeout(3000)



                _log_step(job_id, "fill details")

                job_hashtags = job.get("hashtags") or []

                if isinstance(job_hashtags, str):

                    import json as _json2

                    try:

                        job_hashtags = _json2.loads(job_hashtags)

                    except Exception:

                        job_hashtags = []

                # Build description with optional creator credit
                _base_desc = job["caption_text"]
                try:
                    import sqlite3 as _sq3c
                    _cr_row = _sq3c.connect(os.path.join(os.path.dirname(__file__), "..", "data", "clip_empire.db")).execute(
                        "SELECT creator FROM source_clips WHERE clip_id=(SELECT clip_id FROM platform_variants WHERE variant_id=?)",
                        (job.get("variant_id") or "",)
                    ).fetchone()
                    _creator = (_cr_row[0] or "").strip() if _cr_row else ""
                    # Map creator key â†’ YouTube handle
                    _HANDLE_MAP = {
                        "patrickboyle": "@PatrickBoyleOnFinance",
                        "wallstreetmillennial": "@WallStreetMillennial",
                        "coffeezilla": "@coffeeziIIa",
                        "rareliquid": "@RareLiquid",
                        "plainbagel": "@theplainbagel",
                        "tfue": "@tfue",
                        "cloakzy": "@cloakzy",
                        "shroud": "@shroud",
                        "nickmercs": "@NICKMERCS",
                        "timthetatman": "@timthetatman",
                        "moistcr1tikal": "@moistcr1tikal",
                        "hasanabi": "@hasanabi",
                        "ludwig": "@LudwigAhgren",
                    }
                    _handle = _HANDLE_MAP.get(_creator.lower(), "")
                    if _handle:
                        _base_desc = f"{_base_desc}\n\nOriginal: {_handle}"
                except Exception:
                    pass
                _thumb_path = job.get("thumbnail_path") or ""
                _fill_details(page, cfg, job["caption_text"], _base_desc, made_for_kids_status, hashtags=job_hashtags, thumbnail_path=_thumb_path)



                # schedule_at is stored as ISO string; treat as UTC if naive.

                _log_step(job_id, "visibility/schedule")

                schedule_at_dt = datetime.fromisoformat(job["schedule_at"])

                if schedule_at_dt.tzinfo is None:

                    schedule_at_dt = schedule_at_dt.replace(tzinfo=dt_timezone.utc)



                publish_type = _set_visibility_and_schedule(page, cfg, schedule_at_dt, cfg.timezone)



                _log_step(job_id, f"verify success ({publish_type})")

                # Primary: verify via Content page (confirms video is actually live)
                # Fallback: early_video_url captured from upload dialog
                video_url = _verify_upload_success(page, cfg, publish_type) or early_video_url

                if not video_url:

                    raise RuntimeError("No video URL returned by verification")



                # Mark job succeeded only if we have a URL

                update_job_status(job_id, "succeeded", post_url=video_url, platform_post_id=video_url.split("/")[-1])

                # Auto-cleanup: delete render file after successful upload (keeps disk lean)
                try:
                    if os.path.exists(video_file_path):
                        os.remove(video_file_path)
                        print(f"[cleanup] Deleted render file: {video_file_path}")
                    else:
                        print(f"[cleanup] Render file already gone: {video_file_path}")
                except Exception as _cleanup_err:
                    print(f"[cleanup] Could not delete render file (non-fatal): {_cleanup_err}")



                # Discord success alert

                title = job.get("caption_text", "Unknown title")[:80]

                channel_emoji = {
                    "arc_highlightz": "ðŸŽ®",
                    "fomo_highlights": "ðŸ”¥",
                    "viral_recaps": "ðŸ˜‚",
                    "market_meltdowns": "ðŸ“‰",
                }.get(ch, "ðŸ“¹")

                # Determine publish status and format messages accordingly
                if publish_type.startswith("scheduled:"):
                    # Extract scheduled datetime from return value
                    scheduled_iso = publish_type.split(":", 1)[1]
                    scheduled_dt = datetime.fromisoformat(scheduled_iso)
                    scheduled_local = scheduled_dt.astimezone(pytz.timezone(cfg.timezone))
                    time_str = scheduled_local.strftime("%b %d, %I:%M %p")

                    # Build YouTube Studio edit link from video URL
                    try:
                        video_id = video_url.rstrip("/").split("/")[-1]
                        studio_url = f"https://studio.youtube.com/video/{video_id}/edit"
                    except Exception:
                        studio_url = "https://studio.youtube.com"

                    # Post review alert to channel-specific Discord channel
                    _REVIEW_CHANNEL_MAP = {
                        # Gaming
                        "arc_highlightz":     "1475944657040179314",  # #arc-clip-alerts
                        "fomo_highlights":    "1475997768882458836",  # #fomo-clip-alerts
                        "viral_recaps":       "1476840009133985834",  # #viral-clip-alerts
                        # Finance
                        "market_meltdowns":   "1480139743709888665",  # #publish-success
                        "crypto_confessions": "1480139743709888665",
                        "rich_or_ruined":     "1480139743709888665",
                        # Business
                        "startup_graveyard":  "1480139743709888665",
                        "self_made_clips":    "1480139743709888665",
                        # Tech/Other
                        "ai_did_what":        "1480139743709888665",
                        "gym_moments":        "1480139743709888665",
                        "kitchen_chaos":      "1480139743709888665",
                        "cases_unsolved":     "1480139743709888665",
                        "unfiltered_clips":   "1480139743709888665",
                        "stream_sirens":      "1480139743709888665",
                        "stream_queens":      "1480139743709888665",
                    }
                    # Fallback to #publish-success for any unmapped channel
                    review_ch = _REVIEW_CHANNEL_MAP.get(ch, "1480139743709888665")
                    if review_ch:
                        _discord_post(review_ch,
                            f"ðŸ‘€ **REVIEW NEEDED** â€” `{ch}` {channel_emoji}\n"
                            f"**{title}**\n"
                            f"Goes live: **{time_str}** MDT\n"
                            f"Preview: <{video_url}>\n"
                            f"Edit/delete: <{studio_url}>\n"
                            f"_(Delete before {time_str} to cancel)_"
                        )

                    _discord_post(_CH_SUCCESS,
                        f"ðŸ—“ï¸ **{ch}** {channel_emoji}\n"
                        f"> {title}\n"
                        f"Scheduled for {time_str} | <{video_url}>"
                    )
                else:
                    # Published immediately
                    _discord_post(_CH_SUCCESS,
                        f"âœ… **{ch}** {channel_emoji}\n"
                        f"> {title}\n"
                        f"{video_url}"
                    )

                    _discord_post(_CH_QUEUED,
                        f"âœ… **{ch}** published â†’ <{video_url}>"
                    )



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

        _discord_post(_CH_FAILURES,

            f"[FAIL] **{job_id[:8]}** failed - `{error_class}`\n"

            f"{error_detail[:300]}"

        )

        _discord_post(_CH_QUEUED,

            f"[FAIL] **Failed** - `{ch}` job `{job_id[:8]}`\n"

            f"`{error_class}`: {error_detail[:200]}"

        )

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



    code = run_once(YouTubeWorkerConfig(headless=True))

    print(f"Worker exited with code: {code}")

    raise SystemExit(code)




