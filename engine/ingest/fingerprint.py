"""Duplicate detector v2 scaffold.

Provides light-weight URL/visual/transcript fingerprint helpers.
Visual and transcript implementations are placeholders designed for easy
future replacement with perceptual hash + embedding based methods.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def url_fingerprint(url: str) -> str:
    return hashlib.sha256((url or "").encode("utf-8")).hexdigest()[:24]


def visual_fingerprint(video_path: str) -> str:
    path = Path(video_path)
    if not path.exists():
        return ""
    # Scaffold: hash small head+tail chunks as a cheap proxy.
    data = path.read_bytes()
    sample = data[:32768] + data[-32768:]
    return hashlib.sha256(sample).hexdigest()[:24]


def transcript_fingerprint(text: str) -> str:
    normalized = " ".join((text or "").lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24] if normalized else ""
