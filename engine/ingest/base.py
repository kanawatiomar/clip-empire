"""Base dataclass and ABC for all ingesters."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import uuid


@dataclass
class RawClip:
    """A clip downloaded from a source and ready for transformation."""
    clip_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_url: str = ""            # Original URL that was downloaded
    download_path: str = ""         # Local path to the raw video file
    duration_s: float = 0.0         # Duration in seconds
    title: str = ""                 # Original title from the source
    platform: str = ""              # "youtube" | "tiktok" | "reddit" | "twitter"
    creator: str = ""               # Channel/username from source
    view_count: int = 0             # Original view count (for ranking)
    upload_date: str = ""           # YYYYMMDD from yt-dlp
    width: int = 0                  # Video width
    height: int = 0                 # Video height
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_vertical(self) -> bool:
        """True if the video is already in portrait/vertical orientation."""
        return self.height > self.width

    @property
    def aspect_ratio(self) -> float:
        if self.width == 0:
            return 0
        return self.height / self.width
