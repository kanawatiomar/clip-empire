"""Optional Sora lane scaffold.

Feature-flag only. Does not run by default and does not change publisher flow.
"""

from __future__ import annotations

from typing import List

from engine.ingest.base import RawClip


class SoraLane:
    def __init__(self, enabled: bool = False):
        self.enabled = enabled

    def fetch_candidates(self, channel_name: str, limit: int = 1) -> List[RawClip]:
        # Placeholder hook for future Sora generation integration.
        # Returning [] keeps current pipeline behavior unchanged.
        if not self.enabled:
            return []
        return []
