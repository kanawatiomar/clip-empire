"""
Clip Empire - Account Setup Wizard
Onboards a new account: saves credentials, creates Chrome profile folder.

Usage:
  python setup_wizard.py <channel_name>
  python setup_wizard.py market_meltdowns

Available channels:
  market_meltdowns, crypto_confessions, rich_or_ruined,
  startup_graveyard, self_made_clips, ai_did_what,
  gym_moments, kitchen_chaos, cases_unsolved, unfiltered_clips
"""
import sys
import os
import secrets
import string
from pathlib import Path
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from db import add_account, get_account
from schema import Account
from channel_definitions import CHANNELS

PROFILES_DIR = Path(__file__).parent.parent / "profiles"
RECOVERY_EMAIL = "empirerecovery2025@gmail.com"  # master recovery email — change this


def generate_password(length=16) -> str:
    chars = string.ascii_letters + string.digits + "!@#$%"
    return ''.join(secrets.choice(chars) for _ in range(length))


def setup_account(channel_name: str, email: str, password: str, phone: str):
    if channel_name not in CHANNELS:
        print(f"Unknown channel: {channel_name}")
        print(f"Available: {', '.join(CHANNELS.keys())}")
        return

    # Check if already exists
    existing = get_account(channel_name)
    if existing:
        print(f"[!] Account '{channel_name}' already exists. Use manager.py update to modify.")
        return

    defn = CHANNELS[channel_name]
    profile_path = str(PROFILES_DIR / channel_name)

    # Create Chrome profile folder
    Path(profile_path).mkdir(parents=True, exist_ok=True)
    print(f"[✓] Chrome profile folder created: {profile_path}")

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
        status="setup",
    )

    add_account(account)
    print(f"[✓] Account '{channel_name}' saved to database.")
    print(f"\n{'='*50}")
    print(f"  Next Steps for: {defn['display_name']}")
    print(f"{'='*50}")
    print(f"  1. Open Chrome with this profile:")
    print(f"     chrome.exe --user-data-dir=\"{profile_path}\"")
    print(f"  2. Go to: https://accounts.google.com")
    print(f"     Log in as: {email}")
    print(f"  3. Come back and run lockdown:")
    print(f"     python lockdown.py {channel_name}")
    print(f"{'='*50}\n")


def main():
    args = sys.argv[1:]

    if not args:
        print(__doc__)
        return

    channel_name = args[1] if len(args) > 1 else args[0]

    if channel_name not in CHANNELS:
        print(f"Unknown channel: {channel_name}")
        print(f"Available: {', '.join(CHANNELS.keys())}")
        return

    defn = CHANNELS[channel_name]
    print(f"\n{'='*50}")
    print(f"  Setup: {defn['display_name']} ({defn['niche']})")
    print(f"{'='*50}")

    email = input("  Gmail address: ").strip()
    if not email:
        print("Email required.")
        return

    use_generated = input("  Generate password? [Y/n]: ").strip().lower()
    if use_generated in ("", "y", "yes"):
        password = generate_password()
        print(f"  Generated password: {password}")
        print(f"  (save this — it will be stored encrypted)")
    else:
        password = input("  Password: ").strip()

    phone = input("  Phone number used for signup (for records): ").strip()

    confirm = input(f"\n  Save account '{channel_name}' with email '{email}'? [Y/n]: ").strip().lower()
    if confirm in ("", "y", "yes"):
        setup_account(channel_name, email, password, phone)
    else:
        print("Cancelled.")


if __name__ == "__main__":
    main()
