"""Trend radar input module.

Creates temporary source entries from a lightweight trend signal file.
This keeps the existing source config architecture intact while allowing
fast experimentation with trend-driven ingestion.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List


@dataclass
class TrendSignal:
    keyword: str
    platform: str = "youtube"
    priority_boost: int = -10


class TrendRadar:
    def __init__(self, signals_path: str = "data/trend_signals.json"):
        self.signals_path = Path(signals_path)

    def load_signals(self, channel_name: str) -> List[TrendSignal]:
        if not self.signals_path.exists():
            return []
        try:
            data = json.loads(self.signals_path.read_text(encoding="utf-8"))
        except Exception:
            return []

        channel_entries = data.get(channel_name, [])
        fallback_entries = data.get("*", [])
        entries = channel_entries + fallback_entries

        signals: List[TrendSignal] = []
        for item in entries:
            keyword = (item.get("keyword") or "").strip()
            if not keyword:
                continue
            signals.append(
                TrendSignal(
                    keyword=keyword,
                    platform=item.get("platform", "youtube"),
                    priority_boost=int(item.get("priority_boost", -10)),
                )
            )
        return signals

    def augment_sources(self, channel_name: str, base_sources: List[Dict]) -> List[Dict]:
        signals = self.load_signals(channel_name)
        if not signals:
            return base_sources

        extra: List[Dict] = []
        for sig in signals:
            extra.append(
                {
                    "platform": sig.platform,
                    "url": f"ytsearch20:{sig.keyword}",
                    "priority": sig.priority_boost,
                    "kind": "trend_radar",
                }
            )
        return base_sources + extra
