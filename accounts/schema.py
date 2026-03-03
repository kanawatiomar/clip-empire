"""
Clip Empire - Account Schema
"""
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class Account:
    channel_name: str                          # slug: market_meltdowns
    display_name: str                          # Market Meltdowns
    niche: str                                 # Finance
    email: str
    password: str
    recovery_email: Optional[str] = None
    phone_used: Optional[str] = None           # number used for signup
    totp_secret: Optional[str] = None          # Google Authenticator secret
    backup_codes: Optional[List[str]] = None   # 10 backup codes
    google_voice: Optional[str] = None
    youtube_channel_id: Optional[str] = None
    youtube_channel_url: Optional[str] = None
    chrome_profile_path: Optional[str] = None
    created_at: Optional[str] = None
    locked_down: bool = False
    status: str = "setup"                      # setup / active / suspended / banned
    subs: int = 0
    views: int = 0
    uploads: int = 0
    monetized: bool = False
    notes: Optional[str] = None
