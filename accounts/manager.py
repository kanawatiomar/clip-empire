"""
Clip Empire - Account Manager CLI

Usage:
  python manager.py list               # show all accounts (passwords masked)
  python manager.py show <name>        # reveal full credentials
  python manager.py stats              # subs/views/uploads/monetized summary
  python manager.py update <name> <field> <value>
  python manager.py export             # export to CSV (no sensitive fields)
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from db import list_accounts, get_account, update_account, export_csv
from tabulate import tabulate
from datetime import datetime


def cmd_list():
    accounts = list_accounts()
    if not accounts:
        print("No accounts yet. Run setup_wizard.py to add one.")
        return
    rows = []
    for a in accounts:
        rows.append([
            a.channel_name,
            a.niche,
            a.email,
            "***" if a.password else "-",
            "✓" if a.locked_down else "✗",
            a.youtube_channel_url[:40] + "..." if a.youtube_channel_url and len(a.youtube_channel_url) > 40 else (a.youtube_channel_url or "-"),
            a.status,
        ])
    print(tabulate(rows,
        headers=["Channel", "Niche", "Email", "Password", "Locked", "YouTube URL", "Status"],
        tablefmt="rounded_grid"))
    print(f"\nTotal: {len(accounts)} accounts")


def cmd_show(channel_name: str):
    a = get_account(channel_name)
    if not a:
        print(f"Account '{channel_name}' not found.")
        return
    print(f"\n{'='*50}")
    print(f"  {a.display_name} ({a.channel_name})")
    print(f"{'='*50}")
    print(f"  Niche:          {a.niche}")
    print(f"  Email:          {a.email}")
    print(f"  Password:       {a.password}")
    print(f"  Recovery Email: {a.recovery_email or '-'}")
    print(f"  Phone Used:     {a.phone_used or '-'}")
    print(f"  TOTP Secret:    {a.totp_secret or '-'}")
    print(f"  Google Voice:   {a.google_voice or '-'}")
    print(f"  Locked Down:    {'Yes' if a.locked_down else 'No'}")
    print(f"  Status:         {a.status}")
    print(f"  Chrome Profile: {a.chrome_profile_path or '-'}")
    print(f"  YouTube URL:    {a.youtube_channel_url or '-'}")
    print(f"  Channel ID:     {a.youtube_channel_id or '-'}")
    print(f"  Subs/Views:     {a.subs:,} / {a.views:,}")
    print(f"  Uploads:        {a.uploads}")
    print(f"  Monetized:      {'Yes' if a.monetized else 'No'}")
    print(f"  Created:        {a.created_at or '-'}")
    print(f"  Notes:          {a.notes or '-'}")
    if a.backup_codes:
        print(f"\n  Backup Codes:")
        for i, code in enumerate(a.backup_codes, 1):
            print(f"    {i:2}. {code}")
    print(f"{'='*50}\n")


def cmd_stats():
    accounts = list_accounts()
    if not accounts:
        print("No accounts yet.")
        return
    rows = []
    total_subs = total_views = total_uploads = 0
    for a in accounts:
        rows.append([
            a.channel_name,
            a.niche,
            f"{a.subs:,}",
            f"{a.views:,}",
            a.uploads,
            "✓ YPP" if a.monetized else "✗",
            a.status,
        ])
        total_subs += a.subs
        total_views += a.views
        total_uploads += a.uploads

    print(tabulate(rows,
        headers=["Channel", "Niche", "Subs", "Views", "Uploads", "Monetized", "Status"],
        tablefmt="rounded_grid"))

    monetized_count = sum(1 for a in accounts if a.monetized)
    print(f"\nTotals: {total_subs:,} subs | {total_views:,} views | {total_uploads} uploads | {monetized_count}/{len(accounts)} monetized")


def cmd_update(channel_name: str, field: str, value: str):
    a = get_account(channel_name)
    if not a:
        print(f"Account '{channel_name}' not found.")
        return
    # Type coerce common fields
    int_fields = {"subs", "views", "uploads"}
    bool_fields = {"monetized", "locked_down"}
    if field in int_fields:
        value = int(value)
    elif field in bool_fields:
        value = value.lower() in ("true", "1", "yes")
    update_account(channel_name, field, value)
    print(f"[✓] Updated {channel_name}.{field} = {value}")


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    cmd = args[0].lower()

    if cmd == "list":
        cmd_list()
    elif cmd == "show":
        if len(args) < 2:
            print("Usage: python manager.py show <channel_name>")
        else:
            cmd_show(args[1])
    elif cmd == "stats":
        cmd_stats()
    elif cmd == "update":
        if len(args) < 4:
            print("Usage: python manager.py update <channel_name> <field> <value>")
        else:
            cmd_update(args[1], args[2], args[3])
    elif cmd == "export":
        export_csv()
    else:
        print(f"Unknown command: {cmd}")
        print(__doc__)


if __name__ == "__main__":
    main()
