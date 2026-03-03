"""Safety/policy filtering for raw clips."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, List

from engine.ingest.base import RawClip


DEFAULT_BLOCKED_TERMS = {
    "graphic violence",
    "self harm",
    "suicide tutorial",
    "hate speech",
    "extremist",
}


class ClipPolicyFilter:
    def __init__(self, policy_path: str = "data/policy_terms.json"):
        self.policy_path = Path(policy_path)
        self.blocked_terms = set(DEFAULT_BLOCKED_TERMS)
        self._load_custom_terms()

    def _load_custom_terms(self) -> None:
        if not self.policy_path.exists():
            return
        try:
            data = json.loads(self.policy_path.read_text(encoding="utf-8"))
            for term in data.get("blocked_terms", []):
                if term:
                    self.blocked_terms.add(str(term).lower().strip())
        except Exception:
            return

    def _text_for_clip(self, clip: RawClip) -> str:
        values: List[str] = [clip.title or "", clip.creator or "", clip.source_url or ""]
        description = clip.metadata.get("description") if clip.metadata else ""
        if description:
            values.append(str(description))
        return " ".join(values).lower()

    def allow(self, clip: RawClip) -> bool:
        haystack = self._text_for_clip(clip)
        return not any(term in haystack for term in self.blocked_terms)

    def filter(self, clips: Iterable[RawClip]) -> List[RawClip]:
        approved: List[RawClip] = []
        for clip in clips:
            if self.allow(clip):
                approved.append(clip)
            else:
                print(f"[policy] Skipping blocked clip: {clip.title[:60]}")
        return approved
