"""Quick diagnostic — opens Studio, waits for you to open the upload dialog,
then prints all contenteditable elements so we can find the right selector."""

from playwright.sync_api import sync_playwright
import json

PROFILE = "profiles/market_meltdowns"

with sync_playwright() as p:
    ctx = p.chromium.launch_persistent_context(
        user_data_dir=PROFILE,
        headless=False,
        args=["--start-maximized"],
    )
    pg = ctx.new_page()
    pg.goto("https://studio.youtube.com")
    input("\n>>> Open the upload dialog, select renders/x.mp4, wait for Details tab, then press Enter here...\n")

    els = pg.evaluate("""() => {
        return Array.from(document.querySelectorAll('[contenteditable]')).map(el => {
            return {
                tag: el.tagName,
                id: el.id || '',
                ariaLabel: el.getAttribute('aria-label') || '',
                placeholder: el.getAttribute('placeholder') || '',
                parentTag: el.parentElement ? el.parentElement.tagName : '',
                parentId: el.parentElement ? (el.parentElement.id || '') : '',
                textContent: el.textContent.trim().substring(0, 40)
            };
        });
    }""")

    print("\n=== CONTENTEDITABLE ELEMENTS ===")
    for e in els:
        print(e)

    ctx.close()
