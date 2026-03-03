"""
Clip Empire - Google Account Creator
Creates a Google account and saves credentials to the database.

Usage:
  python create_account.py <channel_name>
  python create_account.py market_meltdowns

Requires: playwright installed + chromium downloaded
  pip install playwright && playwright install chromium
"""
import sys
import os
import asyncio
import secrets
import string
import re
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from db import add_account, get_account
from schema import Account
from channel_definitions import CHANNELS
from setup_wizard import generate_password, RECOVERY_EMAIL

PROFILES_DIR = Path(__file__).parent.parent / "profiles"

# Realistic first/last name pools for generated accounts
FIRST_NAMES = ["Alex","Jordan","Morgan","Casey","Taylor","Riley","Drew","Blake","Quinn","Avery",
               "Logan","Peyton","Reese","Hayden","Cameron","Skyler","Jamie","Parker","Sage","Dylan"]
LAST_NAMES = ["Miller","Davis","Wilson","Moore","Taylor","Anderson","Thomas","Jackson","White",
              "Harris","Martin","Garcia","Thompson","Lee","Clark","Lewis","Hill","Walker","Hall","Young"]

# Plausible birth years for accounts (22-35 years old)
import random


def generate_account_name(channel_name: str) -> tuple[str, str, str]:
    """Generate a realistic first name, last name, and Gmail username."""
    first = random.choice(FIRST_NAMES)
    last = random.choice(LAST_NAMES)
    num = random.randint(1980, 2002)
    # Gmail: firstname.lastname + numbers
    username_options = [
        f"{first.lower()}.{last.lower()}{num}",
        f"{first.lower()}{last.lower()}{random.randint(10,99)}",
        f"{first.lower()}_{last.lower()}{random.randint(1,999)}",
    ]
    username = random.choice(username_options)
    return first, last, username


async def create_google_account(channel_name: str):
    if channel_name not in CHANNELS:
        print(f"Unknown channel: {channel_name}")
        return

    if get_account(channel_name):
        print(f"[!] Account for '{channel_name}' already exists.")
        return

    defn = CHANNELS[channel_name]
    profile_path = str(PROFILES_DIR / channel_name)
    Path(profile_path).mkdir(parents=True, exist_ok=True)

    first, last, username = generate_account_name(channel_name)
    email = f"{username}@gmail.com"
    password = generate_password(16)
    birth_day = str(random.randint(1, 28))
    birth_year = str(random.randint(1988, 2001))
    birth_month = str(random.randint(1, 12))

    print(f"\n{'='*55}")
    print(f"  Creating account for: {defn['display_name']}")
    print(f"  Name:     {first} {last}")
    print(f"  Email:    {email}")
    print(f"  Password: {password}")
    print(f"{'='*55}\n")

    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("Install: pip install playwright && playwright install chromium")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=profile_path,
            headless=False,
            args=["--no-first-run", "--no-default-browser-check",
                  "--disable-blink-features=AutomationControlled"],
            locale="en-US",
        )
        page = browser.pages[0] if browser.pages else await browser.new_page()

        print("[→] Navigating to Google account creation...")
        await page.goto("https://accounts.google.com/signup/v2/createaccount?flowName=GlifWebSignIn&flowEntry=SignUp")
        await page.wait_for_timeout(2000)

        # Fill first name
        try:
            await page.fill("input[name='firstName']", first)
            await page.wait_for_timeout(300)
            await page.fill("input[name='lastName']", last)
            await page.wait_for_timeout(500)
            await page.get_by_role("button", name="Next").click()
            await page.wait_for_timeout(2000)
        except Exception as e:
            print(f"[!] Name step failed: {e}")

        # Fill birthday and gender
        try:
            await page.wait_for_load_state("networkidle")
            # Month - try multiple selector approaches
            month_select = page.locator("select#month")
            if await month_select.count() > 0:
                await month_select.select_option(value=birth_month)
                await page.wait_for_timeout(300)
            # Day
            day_input = page.locator("input#day")
            if await day_input.count() > 0:
                await day_input.triple_click()
                await day_input.fill(birth_day)
                await page.wait_for_timeout(200)
            # Year
            year_input = page.locator("input#year")
            if await year_input.count() > 0:
                await year_input.triple_click()
                await year_input.fill(birth_year)
                await page.wait_for_timeout(200)
            # Gender - "Rather not say" = value 5, Male = 1, Female = 2
            gender_select = page.locator("select#gender")
            if await gender_select.count() > 0:
                await gender_select.select_option(value="1")  # Male
                await page.wait_for_timeout(300)
            await page.wait_for_timeout(700)
            await page.get_by_role("button", name="Next").click()
            await page.wait_for_timeout(3000)
        except Exception as e:
            print(f"[!] Birthday step failed: {e}")

        # Choose username - use custom
        try:
            custom_option = page.get_by_text("Create your own Gmail address", exact=False)
            if await custom_option.is_visible():
                await custom_option.click()
                await page.wait_for_timeout(500)

            username_input = page.locator("input[name='Username'], input[aria-label*='username' i]")
            if await username_input.is_visible():
                await username_input.fill(username)
                await page.wait_for_timeout(500)
                await page.get_by_role("button", name="Next").click()
                await page.wait_for_timeout(2000)

            # Check if username taken
            error = await page.locator("text='That username is taken'").is_visible()
            if error:
                username = f"{username}{random.randint(100,999)}"
                email = f"{username}@gmail.com"
                await username_input.fill(username)
                await page.wait_for_timeout(300)
                await page.get_by_role("button", name="Next").click()
                await page.wait_for_timeout(2000)
        except Exception as e:
            print(f"[!] Username step failed: {e}")

        # Fill password
        try:
            pwd = page.locator("input[name='Passwd'], input[type='password']").first
            if await pwd.is_visible():
                await pwd.fill(password)
            confirm = page.locator("input[name='PasswdAgain'], input[name='confirm_passwd']")
            if await confirm.is_visible():
                await confirm.fill(password)
            await page.wait_for_timeout(500)
            await page.get_by_role("button", name="Next").click()
            await page.wait_for_timeout(3000)
        except Exception as e:
            print(f"[!] Password step failed: {e}")

        # PHONE VERIFICATION - needs human input
        phone_detected = "phonenumber" in page.url or await page.locator("input#phoneNumberId, input[name='phoneNumber'], input[aria-label*='phone' i]").first.is_visible()
        if phone_detected:
            print("\n" + "="*55)
            print("  📱 PHONE VERIFICATION REQUIRED")
            print("="*55)
            print(f"  You need to enter a phone number.")
            print(f"  Use a number from 5sim.net")
            phone = input("  Enter phone number (with country code, e.g. +12025551234): ").strip()

            phone_input = page.locator("input#phoneNumberId, input[name='phoneNumber'], input[aria-label*='phone' i]").first
            if await phone_input.is_visible():
                await phone_input.fill(phone)
                await page.get_by_role("button", name="Next", exact=False).click()
                await page.wait_for_timeout(4000)

            # Wait for SMS code
            print(f"\n  Waiting for SMS code for {phone}...")
            print("  (Check 5sim.net for the incoming SMS)")
            sms_code = input("  Enter SMS code: ").strip()

            code_input = page.locator("input[type='tel'], input[name='code']").first
            if await code_input.is_visible():
                await code_input.fill(sms_code)
                await page.get_by_role("button", name="Verify").click()
                await page.wait_for_timeout(3000)
        else:
            phone = "skipped"

        # Recovery email (optional - skip or add master recovery)
        try:
            skip = page.get_by_role("button", name="Skip")
            if await skip.is_visible():
                await skip.click()
                await page.wait_for_timeout(2000)
        except Exception:
            pass

        # Accept Terms
        try:
            agree = page.get_by_role("button", name="I agree")
            if await agree.is_visible():
                await agree.click()
                await page.wait_for_timeout(3000)
        except Exception:
            pass

        # Confirm final URL
        final_url = page.url
        print(f"\n  Final URL: {final_url}")

        # Check success
        if "myaccount.google.com" in final_url or "gmail.com" in final_url:
            print(f"\n[✓] Account created successfully!")
        else:
            print(f"\n[?] Uncertain - check the browser window.")
            input("    Press Enter when you're sure the account is created...")

        await browser.close()

    # Save to database
    account = Account(
        channel_name=channel_name,
        display_name=defn["display_name"],
        niche=defn["niche"],
        email=email,
        password=password,
        recovery_email=RECOVERY_EMAIL,
        phone_used=phone,
        chrome_profile_path=profile_path,
        created_at=datetime.now().isoformat(),
        status="active",
    )
    add_account(account)
    print(f"[✓] Saved to database: {channel_name} → {email}")
    print(f"\n  Next: python lockdown.py {channel_name}")


async def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        print(f"\nAvailable channels:")
        for name, defn in CHANNELS.items():
            print(f"  {name:25} ({defn['niche']})")
        return
    await create_account(args[0])


# Fix name reference
create_account = create_google_account

if __name__ == "__main__":
    asyncio.run(main())
