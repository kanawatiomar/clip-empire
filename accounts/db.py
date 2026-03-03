"""
Clip Empire - Encrypted Account Database
Sensitive fields (password, totp_secret, backup_codes) are Fernet-encrypted.
"""
import sqlite3
import json
import os
import csv
from pathlib import Path
from cryptography.fernet import Fernet
from schema import Account

DB_PATH = Path(__file__).parent / "accounts.db"
KEY_PATH = Path(__file__).parent / ".master_key"


def _load_or_create_key() -> Fernet:
    if not KEY_PATH.exists():
        key = Fernet.generate_key()
        KEY_PATH.write_bytes(key)
        KEY_PATH.chmod(0o600)
        print(f"[!] Master key created at {KEY_PATH}")
        print("[!] BACK THIS UP — losing it means losing access to all credentials.")
    return Fernet(KEY_PATH.read_bytes())


def _enc(fernet: Fernet, value: str) -> str:
    if not value:
        return ""
    return fernet.encrypt(value.encode()).decode()


def _dec(fernet: Fernet, value: str) -> str:
    if not value:
        return ""
    try:
        return fernet.decrypt(value.encode()).decode()
    except Exception:
        return value  # already plaintext (legacy)


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS accounts (
            channel_name TEXT PRIMARY KEY,
            display_name TEXT,
            niche TEXT,
            email TEXT,
            password TEXT,
            recovery_email TEXT,
            phone_used TEXT,
            totp_secret TEXT,
            backup_codes TEXT,
            google_voice TEXT,
            youtube_channel_id TEXT,
            youtube_channel_url TEXT,
            chrome_profile_path TEXT,
            created_at TEXT,
            locked_down INTEGER DEFAULT 0,
            status TEXT DEFAULT 'setup',
            subs INTEGER DEFAULT 0,
            views INTEGER DEFAULT 0,
            uploads INTEGER DEFAULT 0,
            monetized INTEGER DEFAULT 0,
            notes TEXT
        )
    """)
    conn.commit()
    conn.close()


def add_account(account: Account):
    fernet = _load_or_create_key()
    conn = get_connection()
    backup_json = json.dumps(account.backup_codes or [])
    conn.execute("""
        INSERT OR REPLACE INTO accounts VALUES (
            ?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?
        )
    """, (
        account.channel_name,
        account.display_name,
        account.niche,
        account.email,
        _enc(fernet, account.password),
        account.recovery_email or "",
        account.phone_used or "",
        _enc(fernet, account.totp_secret or ""),
        _enc(fernet, backup_json),
        account.google_voice or "",
        account.youtube_channel_id or "",
        account.youtube_channel_url or "",
        account.chrome_profile_path or "",
        account.created_at or "",
        int(account.locked_down),
        account.status,
        account.subs,
        account.views,
        account.uploads,
        int(account.monetized),
        account.notes or "",
    ))
    conn.commit()
    conn.close()


def get_account(channel_name: str) -> Account | None:
    fernet = _load_or_create_key()
    conn = get_connection()
    row = conn.execute("SELECT * FROM accounts WHERE channel_name=?", (channel_name,)).fetchone()
    conn.close()
    if not row:
        return None
    backup_codes = json.loads(_dec(fernet, row["backup_codes"]) or "[]")
    return Account(
        channel_name=row["channel_name"],
        display_name=row["display_name"],
        niche=row["niche"],
        email=row["email"],
        password=_dec(fernet, row["password"]),
        recovery_email=row["recovery_email"],
        phone_used=row["phone_used"],
        totp_secret=_dec(fernet, row["totp_secret"]),
        backup_codes=backup_codes,
        google_voice=row["google_voice"],
        youtube_channel_id=row["youtube_channel_id"],
        youtube_channel_url=row["youtube_channel_url"],
        chrome_profile_path=row["chrome_profile_path"],
        created_at=row["created_at"],
        locked_down=bool(row["locked_down"]),
        status=row["status"],
        subs=row["subs"],
        views=row["views"],
        uploads=row["uploads"],
        monetized=bool(row["monetized"]),
        notes=row["notes"],
    )


def list_accounts() -> list[Account]:
    fernet = _load_or_create_key()
    conn = get_connection()
    rows = conn.execute("SELECT * FROM accounts ORDER BY niche, channel_name").fetchall()
    conn.close()
    accounts = []
    for row in rows:
        backup_codes = json.loads(_dec(fernet, row["backup_codes"]) or "[]")
        accounts.append(Account(
            channel_name=row["channel_name"],
            display_name=row["display_name"],
            niche=row["niche"],
            email=row["email"],
            password=_dec(fernet, row["password"]),
            recovery_email=row["recovery_email"],
            phone_used=row["phone_used"],
            totp_secret=_dec(fernet, row["totp_secret"]),
            backup_codes=backup_codes,
            google_voice=row["google_voice"],
            youtube_channel_id=row["youtube_channel_id"],
            youtube_channel_url=row["youtube_channel_url"],
            chrome_profile_path=row["chrome_profile_path"],
            created_at=row["created_at"],
            locked_down=bool(row["locked_down"]),
            status=row["status"],
            subs=row["subs"],
            views=row["views"],
            uploads=row["uploads"],
            monetized=bool(row["monetized"]),
            notes=row["notes"],
        ))
    return accounts


def update_account(channel_name: str, field: str, value):
    """Update a single field. Encrypts sensitive fields automatically."""
    fernet = _load_or_create_key()
    sensitive = {"password", "totp_secret", "backup_codes"}
    if field in sensitive:
        if field == "backup_codes":
            value = _enc(fernet, json.dumps(value))
        else:
            value = _enc(fernet, str(value))
    conn = get_connection()
    conn.execute(f"UPDATE accounts SET {field}=? WHERE channel_name=?", (value, channel_name))
    conn.commit()
    conn.close()


def export_csv(output_path: str = "accounts_export.csv"):
    accounts = list_accounts()
    fields = [
        "channel_name", "display_name", "niche", "email", "status",
        "youtube_channel_url", "subs", "views", "uploads", "monetized",
        "locked_down", "created_at", "notes"
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for a in accounts:
            writer.writerow({
                "channel_name": a.channel_name,
                "display_name": a.display_name,
                "niche": a.niche,
                "email": a.email,
                "status": a.status,
                "youtube_channel_url": a.youtube_channel_url or "",
                "subs": a.subs,
                "views": a.views,
                "uploads": a.uploads,
                "monetized": "Yes" if a.monetized else "No",
                "locked_down": "Yes" if a.locked_down else "No",
                "created_at": a.created_at or "",
                "notes": a.notes or "",
            })
    print(f"[✓] Exported {len(accounts)} accounts to {output_path}")


# Auto-init on import
init_db()
