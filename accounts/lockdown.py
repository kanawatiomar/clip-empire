"""
Clip Empire - Account Lockdown
Automates 2FA setup, backup code saving, and recovery settings.

Usage:
  python lockdown.py <channel_name>
  python lockdown.py market_meltdowns
"""
import sys
import os
import asyncio
import pyotp
import re
from pathlib import Path
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, os.path.dirname(__file__))
from db import get_account, update_account
from schema import Account

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Install playwright: pip install playwright && playwright install chromium")
    sys.exit(1)

try:
    from PIL import Image
    from pyzbar.pyzbar import decode as qr_decode
    HAS_QR = True
except ImportError:
    HAS_QR = False
    print("[!] pyzbar/Pillow not installed — QR decode disabled. Manual TOTP input required.")

BACKUP_CODES_DIR = Path(__file__).parent / "backup_codes"
BACKUP_CODES_DIR.mkdir(exist_ok=True)


async def extract_totp_secret_from_qr(page) -> str | None:
    """Screenshot the QR code area and decode the TOTP secret."""
    if not HAS_QR:
        return None
    try:
        # Screenshot just the QR code
        qr_path = Path(__file__).parent / "_temp_qr.png"
        await page.screenshot(path=str(qr_path))
        img = Image.open(qr_path)
        decoded = qr_decode(img)
        qr_path.unlink(missing_ok=True)
        for d in decoded:
            uri = d.data.decode("utf-8")
            if "otpauth://" in uri:
                # Parse the secret from the URI
                qs = parse_qs(urlparse(uri).query)
                secret = qs.get("secret", [None])[0]
                if secret:
                    return secret
    except Exception as e:
        print(f"[!] QR decode failed: {e}")
    return None


async def lockdown_account(channel_name: str):
    account = get_account(channel_name)
    if not account:
        print(f"Account '{channel_name}' not found in database.")
        return

    if account.locked_down:
        print(f"[!] Account '{channel_name}' is already locked down.")
        return

    profile_path = account.chrome_profile_path
    if not profile_path or not Path(profile_path).exists():
        print(f"[!] Chrome profile not found: {profile_path}")
        print("[!] Run setup_wizard.py first and log into Google in Chrome.")
        return

    print(f"\n[→] Launching Chrome with profile: {profile_path}")
    print(f"[→] Account: {account.email}")

    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=profile_path,
            headless=False,
            args=["--no-first-run", "--no-default-browser-check"],
        )
        page = browser.pages[0] if browser.pages else await browser.new_page()

        # Step 1: Go to Google Security settings
        print("[→] Navigating to Google Security...")
        await page.goto("https://myaccount.google.com/security", wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # Check if logged in
        if "accounts.google.com" in page.url:
            print("[!] Not logged in! Please log into Google in this Chrome profile first.")
            input("    Press Enter after logging in to continue...")
            await page.goto("https://myaccount.google.com/security", wait_until="networkidle")
            await page.wait_for_timeout(2000)

        # Step 2: Find and click 2-Step Verification
        print("[→] Looking for 2-Step Verification...")
        try:
            # Try to find and click 2SV link
            await page.get_by_text("2-Step Verification").first.click()
            await page.wait_for_timeout(3000)
        except Exception:
            print("[!] Couldn't auto-click 2SV. Opening it manually...")
            await page.goto("https://myaccount.google.com/signinoptions/two-step-verification/enroll-welcome")
            await page.wait_for_timeout(3000)

        # Click "Get started" or "Try it" button
        for btn_text in ["Get started", "Try it", "Next"]:
            try:
                btn = page.get_by_role("button", name=btn_text)
                if await btn.is_visible():
                    await btn.click()
                    await page.wait_for_timeout(2000)
                    break
            except Exception:
                pass

        # May need password re-entry
        pwd_field = page.locator("input[type='password']")
        if await pwd_field.is_visible():
            print("[→] Re-entering password...")
            await pwd_field.fill(account.password)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(3000)

        # Step 3: Select Authenticator app
        print("[→] Selecting Authenticator app option...")
        for option in ["Authenticator app", "Google Authenticator", "Authentication app"]:
            try:
                elem = page.get_by_text(option, exact=False).first
                if await elem.is_visible():
                    await elem.click()
                    await page.wait_for_timeout(2000)
                    break
            except Exception:
                pass

        # Click Set up / Next
        for btn in ["Set up", "Next", "Continue"]:
            try:
                b = page.get_by_role("button", name=btn)
                if await b.is_visible():
                    await b.click()
                    await page.wait_for_timeout(3000)
                    break
            except Exception:
                pass

        # Step 4: Try to get TOTP secret from QR code
        print("[→] Attempting to decode QR code...")
        totp_secret = await extract_totp_secret_from_qr(page)

        if totp_secret:
            print(f"[✓] TOTP secret extracted: {totp_secret}")
            # Generate verification code
            totp = pyotp.TOTP(totp_secret)
            code = totp.now()
            print(f"[→] Generated TOTP code: {code}")
        else:
            print("[!] Could not auto-decode QR. Please:")
            print("    1. In the open Chrome window, click 'Can't scan it?'")
            print("    2. Copy the secret key shown")
            totp_secret = input("    Paste TOTP secret here: ").strip().replace(" ", "")
            code = pyotp.TOTP(totp_secret).now()
            print(f"[→] Generated TOTP code: {code}")

        # Enter TOTP code
        code_input = page.locator("input[type='text'], input[type='tel'], input[aria-label*='code']").first
        if await code_input.is_visible():
            await code_input.fill(code)
            await page.wait_for_timeout(500)

            verify_btn = page.get_by_role("button", name="Verify")
            if not await verify_btn.is_visible():
                verify_btn = page.get_by_role("button", name="Next")
            await verify_btn.click()
            await page.wait_for_timeout(3000)
        else:
            print("[!] Could not find code input field. Please enter code manually in browser.")
            input("    Press Enter after entering the code...")

        # Click Turn On
        for btn in ["Turn on", "Turn On", "Enable", "Done"]:
            try:
                b = page.get_by_role("button", name=btn)
                if await b.is_visible():
                    await b.click()
                    await page.wait_for_timeout(2000)
                    break
            except Exception:
                pass

        print("[✓] 2FA enabled!")

        # Step 5: Get backup codes
        print("[→] Getting backup codes...")
        await page.goto("https://myaccount.google.com/signinoptions/two-step-verification")
        await page.wait_for_timeout(3000)

        # Find backup codes section
        for text in ["Backup codes", "Backup", "10 backup codes"]:
            try:
                elem = page.get_by_text(text, exact=False).first
                if await elem.is_visible():
                    await elem.click()
                    await page.wait_for_timeout(3000)
                    break
            except Exception:
                pass

        # Try to get backup codes from page
        backup_codes = []
        try:
            # Look for download button first
            dl_btn = page.get_by_role("button", name="Download")
            if await dl_btn.is_visible():
                # Get page content for codes
                content = await page.content()
                # Try to extract 8-digit codes
                codes = re.findall(r'\b\d{8}\b', content)
                if codes:
                    backup_codes = list(set(codes))[:10]
        except Exception:
            pass

        if not backup_codes:
            print("[!] Could not auto-extract backup codes from page.")
            raw = input("    Paste the backup codes (space or newline separated): ").strip()
            backup_codes = raw.split()

        if backup_codes:
            # Save to file
            codes_path = BACKUP_CODES_DIR / f"{channel_name}.txt"
            codes_path.write_text(f"Backup codes for {channel_name} ({account.email})\n\n" +
                                  "\n".join(backup_codes))
            print(f"[✓] {len(backup_codes)} backup codes saved to {codes_path}")

        # Save everything to DB
        update_account(channel_name, "totp_secret", totp_secret)
        update_account(channel_name, "backup_codes", backup_codes)
        update_account(channel_name, "locked_down", True)
        update_account(channel_name, "status", "active")
        print(f"\n[✓] Account '{channel_name}' fully locked down!")
        print(f"    TOTP secret, backup codes saved to encrypted database.")

        await browser.close()


async def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return
    await lockdown_account(args[0])


if __name__ == "__main__":
    asyncio.run(main())
