"""Auto A/B title and hook generation."""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Tuple

from engine.config.templates import get_title


def generate_title_pair(channel_name: str, creator: Optional[str] = None) -> Tuple[str, str]:
    base = get_title(channel_name, creator=creator)
    a = f"{base}"
    b = f"Watch this before scrolling: {base}"
    return a, b


def choose_variant(channel_name: str, creator: Optional[str] = None) -> tuple[str, str, str]:
    a, b = generate_title_pair(channel_name, creator=creator)
    pick_a = datetime.utcnow().minute % 2 == 0
    chosen = a if pick_a else b
    label = "A" if pick_a else "B"
    hook = chosen.split(":", 1)[0][:80]
    return chosen, hook, label
