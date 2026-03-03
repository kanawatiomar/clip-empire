"""
Clip Empire - Google Account Creator (Desktop Control / PyAutoGUI)
Uses OS-level mouse/keyboard — bypasses ALL bot detection.

Usage:
  python create_account_gui.py market_meltdowns
"""
import sys
import os
import time
import random
import subprocess
import pyautogui
import pygetwindow as gw
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from db import add_account, get_account
from schema import Account
from channel_definitions import CHANNELS
from setup_wizard import generate_password, RECOVERY_EMAIL

PROFILES_DIR = Path(__file__).parent.parent / "profiles"
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PYTHON = r"C:\Users\kanaw\AppData\Local\Python\pythoncore-3.14-64\python.exe"

import string
import secrets

def gen_password(n=16):
    chars = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(secrets.choice(chars) for _ in range(n))

def gen_identity():
    firsts = ["Alex","Jordan","Morgan","Casey","Taylor","Riley","Blake","Quinn","Logan","Parker"]
    lasts  = ["Miller","Davis","Wilson","Moore","Taylor","Anderson","Thomas","Jackson","Harris","Clark"]
    import random
    first = random.choice(firsts)
    last  = random.choice(lasts)
    year  = random.randint(1988, 2001)
    user  = f"{first.lower()}.{last.lower()}{random.randint(10,99)}"
    return first, last, user, str(year)

def human_type(text: str, interval=(0.05, 0.15)):
    """Type text with random human-like delays."""
    for ch in text:
        pyautogui.typewrite(ch, interval=random.uniform(*interval))

def screenshot_and_show():
    """Take a screenshot and return the path."""
    path = r"C:\Users\kanaw\.openclaw\workspace\screenshot.png"
    pyautogui.screenshot(path)
    return path

def wait_and_click(x, y, delay=0.5):
    time.sleep(delay)
    pyautogui.moveTo(x, y, duration=random.uniform(0.3, 0.7))
    pyautogui.click()
    time.sleep(0.3)

def open_chrome_to_url(url: str, profile_path: str):
    """Open Chrome with specific profile."""
    subprocess.Popen([CHROME_PATH, f"--user-data-dir={profile_path}", "--no-first-run", url])
    time.sleep(4)  # Wait for Chrome to open

def create_account_gui(channel_name: str):
    if channel_name not in CHANNELS:
        print(f"Unknown channel: {channel_name}")
        return None

    defn = CHANNELS[channel_name]
    profile_path = str(PROFILES_DIR / channel_name)
    Path(profile_path).mkdir(parents=True, exist_ok=True)

    first, last, username, birth_year = gen_identity()
    birth_day   = str(random.randint(5, 25))
    birth_month = str(random.randint(1, 12))  # 1-12
    password    = gen_password()
    email       = f"{username}@gmail.com"

    print(f"\n{'='*55}")
    print(f"  Creating: {defn['display_name']}")
    print(f"  Name:     {first} {last}")
    print(f"  Email:    {email}")
    print(f"  Password: {password}")
    print(f"{'='*55}")

    # Open Chrome to Google signup
    print("\n[→] Opening Chrome to Google signup...")
    open_chrome_to_url(
        "https://accounts.google.com/signup/v2/createaccount?flowName=GlifWebSignIn&flowEntry=SignUp",
        profile_path
    )

    input("\n[?] Is the Google signup page visible? (Press Enter to continue)\n    If Chrome didn't open, open it manually to accounts.google.com/signup")

    # --- STEP 1: First name + Last name ---
    print("\n[→] Step 1: Filling name...")
    # Click First Name field (user positions it if needed)
    pyautogui.hotkey('ctrl', 'l')  # Focus address bar
    time.sleep(0.3)
    pyautogui.hotkey('alt', 'F4') if False else None  # don't close

    # Take screenshot to see current state
    screenshot_and_show()
    print("[→] Clicking First Name field...")

    # Use Tab-based navigation from address bar approach
    # Click somewhere safe first, then use keyboard
    pyautogui.click(640, 400)  # Click middle of page
    time.sleep(0.5)

    # Try to find and fill first name using pyautogui.locateOnScreen or just Tab
    # Since we know Google's signup form layout, use pyautogui.write with Tab navigation

    # Click on first name field - Google signup first field is usually ~400,380 in center
    # We'll use find-by-placeholder approach via keyboard shortcut
    pyautogui.hotkey('ctrl', 'a')  # select all (won't do harm)
    time.sleep(0.2)

    # Better: use keyboard to navigate
    # First, click somewhere to make sure page is focused
    pyautogui.click(640, 400)
    time.sleep(0.5)

    # Tab to first field
    pyautogui.press('tab')
    time.sleep(0.2)
    human_type(first)
    time.sleep(0.2)
    pyautogui.press('tab')
    human_type(last)
    time.sleep(0.3)

    # Click Next
    pyautogui.hotkey('alt', 'n')  # doesn't work for this but harmless
    # Find Next button via keyboard
    pyautogui.press('tab')
    pyautogui.press('tab')
    pyautogui.press('tab')
    pyautogui.press('tab')
    pyautogui.press('enter')
    time.sleep(2.5)

    # --- STEP 2: Birthday & Gender ---
    print("[→] Step 2: Birthday & Gender...")
    time.sleep(1)

    # Month dropdown - press Tab to reach it
    # Google's birthday page: Month(select) Day(input) Year(input) Gender(select)
    pyautogui.click(640, 400)
    time.sleep(0.5)

    # Tab through form: Month, Day, Year, Gender
    pyautogui.press('tab')  # focus first field (Month)
    time.sleep(0.2)

    # Select month by typing its number worth of arrow keys
    months = int(birth_month)
    for _ in range(months):
        pyautogui.press('down')
        time.sleep(0.1)

    pyautogui.press('tab')  # Day
    time.sleep(0.2)
    human_type(birth_day)

    pyautogui.press('tab')  # Year
    time.sleep(0.2)
    human_type(birth_year)

    pyautogui.press('tab')  # Gender
    time.sleep(0.2)
    pyautogui.press('down')  # Male = first option
    time.sleep(0.2)

    # Tab to Next button and press
    pyautogui.press('tab')
    time.sleep(0.2)
    pyautogui.press('enter')
    time.sleep(2.5)

    # --- STEP 3: Username ---
    print("[→] Step 3: Username...")
    time.sleep(1)

    # Select "Create your own" option if present
    # Tab to the custom username option
    pyautogui.click(640, 400)
    time.sleep(0.5)

    # Try pressing down arrows to select custom username option
    pyautogui.press('tab')
    pyautogui.press('space')  # might select "create your own" radio
    time.sleep(0.5)

    # Type username
    pyautogui.press('tab')
    human_type(username)
    time.sleep(0.3)

    pyautogui.press('tab')
    pyautogui.press('enter')
    time.sleep(2.5)

    # Check if taken - wait and screenshot
    screenshot_and_show()

    # --- STEP 4: Password ---
    print("[→] Step 4: Password...")
    time.sleep(1)

    pyautogui.click(640, 400)
    time.sleep(0.5)

    pyautogui.press('tab')
    human_type(password)
    pyautogui.press('tab')
    human_type(password)  # confirm
    time.sleep(0.3)

    pyautogui.press('tab')
    pyautogui.press('enter')
    time.sleep(3)

    # --- STEP 5: Phone verification ---
    print("\n" + "="*55)
    print("  📱 PHONE VERIFICATION")
    print("="*55)
    print(f"  1. Look at the Chrome window")
    print(f"  2. Enter this number: (you'll type it)")

    phone = input("  Paste your SMSPool number (digits only, e.g. 2765488725): ").strip()
    # Format as US number
    if not phone.startswith("+"):
        phone_formatted = f"+1{phone}"
    else:
        phone_formatted = phone

    print(f"[→] Entering phone: {phone_formatted}")
    pyautogui.click(640, 400)
    time.sleep(0.5)
    pyautogui.press('tab')
    human_type(phone_formatted)
    time.sleep(0.5)

    pyautogui.press('tab')
    pyautogui.press('enter')
    time.sleep(3)

    # Wait for SMS
    print(f"\n  Waiting for SMS on {phone}...")
    print("  Check SMSPool/5sim for the incoming code.")
    sms_code = input("  Enter SMS code: ").strip()

    print(f"[→] Entering SMS code: {sms_code}")
    pyautogui.click(640, 400)
    time.sleep(0.5)
    pyautogui.press('tab')
    human_type(sms_code)
    time.sleep(0.3)

    pyautogui.press('tab')
    pyautogui.press('enter')
    time.sleep(3)

    # Skip recovery email
    print("[→] Skipping recovery email (will set later via lockdown)...")
    pyautogui.press('tab')
    pyautogui.press('tab')
    pyautogui.press('enter')  # Skip
    time.sleep(2)

    # Accept terms
    print("[→] Accepting terms...")
    pyautogui.press('tab')
    pyautogui.press('enter')  # I agree
    time.sleep(3)

    screenshot_and_show()
    print("\n[?] Is the account created? Check if you see the Google Account page.")
    result = input("  Account created? [y/n]: ").strip().lower()

    if result == 'y':
        print(f"[✓] Account created!")
    else:
        print("[!] Something went wrong. The Chrome window stays open for manual fixes.")

    # Save to DB regardless
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
        status="active" if result == 'y' else "setup",
    )
    add_account(account)
    print(f"[✓] Saved to database.")
    print(f"\n  Next: python lockdown.py {channel_name}")
    return email, password


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        for name, defn in CHANNELS.items():
            print(f"  {name:25} ({defn['niche']})")
        sys.exit()
    create_account_gui(args[0])
