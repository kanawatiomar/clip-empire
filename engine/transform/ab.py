"""Auto A/B title and hook generation."""

from __future__ import annotations

import random
from typing import Optional

from engine.config.templates import get_title

# A/B test: two independently-drawn titles so batches don't repeat
# No "Watch this before scrolling:" prefix — it was appearing on 50% of ALL
# clips and when a batch runs in the same minute they all got the same variant.


def generate_title_pair(channel_name: str, creator: Optional[str] = None):
    """Return two distinct titles drawn from the template pool."""
    a = get_title(channel_name, creator=creator)
    b = get_title(channel_name, creator=creator)
    # Force them to differ (try up to 5 times)
    for _ in range(5):
        if b != a:
            break
        b = get_title(channel_name, creator=creator)
    return a, b


def choose_variant(channel_name: str, creator: Optional[str] = None) -> tuple[str, str, str]:
    a, b = generate_title_pair(channel_name, creator=creator)
    pick_a = random.random() < 0.5
    chosen = a if pick_a else b

    # Safety: substitute any leftover {creator} placeholder
    if creator and "{creator}" in chosen:
        chosen = chosen.replace("{creator}", creator.capitalize())
    elif "{creator}" in chosen:
        chosen = chosen.replace("{creator}", "")

    label = "A" if pick_a else "B"
    hook = chosen.split(":")[0].strip()[:80]
    return chosen, hook, label
