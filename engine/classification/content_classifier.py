from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from typing import Iterable

from engine.ingest.base import RawClip


CLASSIFIER_VERSION = "v1"

GAME_ALIASES: dict[str, tuple[str, ...]] = {
    "fortnite": ("fortnite", "fncs", "box fight", "victory royale"),
    "warzone": ("warzone", "verdansk", "rebirth", "gulag", "cod wz", "call of duty warzone"),
    "valorant": ("valorant", "vct", "ace", "clove", "jett diff"),
    "apex_legends": ("apex", "apex legends", "respawn beacon"),
    "counter_strike": ("counter-strike", "counter strike", "cs2", "csgo", "dust2"),
    "league_of_legends": ("league of legends", "league", "lol", "summoner's rift", "pentakill"),
    "minecraft": ("minecraft", "creeper", "ender dragon", "netherite"),
    "gta": ("gta", "gta v", "grand theft auto", "rp", "roleplay"),
    "rocket_league": ("rocket league", "rlcs", "flip reset"),
    "overwatch": ("overwatch", "ow2", "play of the game"),
    "rainbow_six": ("rainbow six", "r6", "siege"),
    "escape_from_tarkov": ("tarkov", "escape from tarkov", "labs keycard"),
    "pubg": ("pubg", "battlegrounds"),
    "roblox": ("roblox",),
    "marvel_rivals": ("marvel rivals",),
}

MODE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "just_chatting": ("just chatting", "q&a", "chatting", "storytime", "rant", "talking to chat"),
    "irl": ("irl", "in real life", "vlog", "outside", "at the gym", "at the store", "on stream outside"),
    "reaction": ("reacts to", "reaction", "watching", "responding to", "he saw", "she saw"),
    "podcast": ("podcast", "interview", "episode", "guest", "conversation"),
    "gameplay": ("gameplay", "match", "ranked", "scrim", "solo queue", "duo", "trios", "squad", "wkey"),
    "clutch": ("clutch", "1v1", "1v2", "1v3", "1v4", "1v5", "ace", "last alive", "wins this", "wins the round"),
    "rage": ("rage", "rages", "mad", "angry", "slams", "loses it", "tilted", "screaming"),
    "funny": ("funny", "laugh", "laughing", "meme", "wtf", "what is happening", "no way bro", "fails", "fail"),
}

CREATOR_GAME_HINTS: dict[str, str] = {
    "tfue": "fortnite",
    "cloakzy": "warzone",
    "taxi2g": "fortnite",
    "ninja": "fortnite",
    "bugha": "fortnite",
    "benjyfishy": "fortnite",
    "nickmercs": "warzone",
    "shroud": "valorant",
    "timthetatman": "warzone",
    "myth": "fortnite",
    "sinatraa": "valorant",
    "tenz": "valorant",
}

NON_GAME_CHANNEL_HINTS: dict[str, tuple[str | None, str | None]] = {
    "unfiltered_clips": (None, "funny"),
    "fomo_highlights": (None, "reaction"),
    "viral_recaps": (None, "funny"),
}

_WORD_RE = re.compile(r"\b[a-z0-9][a-z0-9'_-]*\b")


@dataclass
class ClipContentProfile:
    primary_game: str | None = None
    primary_mode: str | None = None
    game_scores: dict[str, float] = field(default_factory=dict)
    mode_scores: dict[str, float] = field(default_factory=dict)
    labels: list[str] = field(default_factory=list)
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)
    classifier_version: str = CLASSIFIER_VERSION

    def to_metadata(self) -> dict:
        return asdict(self)


def _normalize(text: str) -> str:
    text = (text or "").lower()
    text = text.replace("_", " ")
    text = re.sub(r"[^a-z0-9\s'/-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _match_keywords(text: str, mapping: dict[str, tuple[str, ...]], weight: float) -> tuple[dict[str, float], list[str]]:
    scores: dict[str, float] = {}
    evidence: list[str] = []
    if not text:
        return scores, evidence
    for label, keywords in mapping.items():
        for kw in keywords:
            if kw in text:
                scores[label] = scores.get(label, 0.0) + weight
                evidence.append(f"{label}:{kw}")
    return scores, evidence


def _merge_scores(dst: dict[str, float], src: dict[str, float]) -> None:
    for key, value in src.items():
        dst[key] = round(dst.get(key, 0.0) + value, 3)


def _top_label(scores: dict[str, float], minimum: float) -> str | None:
    if not scores:
        return None
    label, score = max(scores.items(), key=lambda item: item[1])
    return label if score >= minimum else None


def _token_labels(text: str) -> set[str]:
    return set(_WORD_RE.findall(text))


def classify_clip(clip: RawClip, channel_name: str = "") -> ClipContentProfile:
    title = _normalize(getattr(clip, "title", "") or "")
    creator = _normalize(getattr(clip, "creator", "") or "")
    source_url = _normalize(getattr(clip, "source_url", "") or "")
    metadata = getattr(clip, "metadata", {}) or {}

    description = _normalize(str(metadata.get("description", ""))[:1000])
    transcript_hint = _normalize(" ".join(
        str(metadata.get(key, "")) for key in (
            "transcript_text",
            "ocr_text",
            "frame_text",
            "segment_reason",
            "source_video_title",
        )
    ))

    game_scores: dict[str, float] = {}
    mode_scores: dict[str, float] = {}
    evidence: list[str] = []

    for text, weight, source in (
        (title, 3.0, "title"),
        (description, 1.5, "description"),
        (transcript_hint, 2.0, "hint"),
        (source_url, 1.0, "url"),
    ):
        scores, hits = _match_keywords(text, GAME_ALIASES, weight)
        _merge_scores(game_scores, scores)
        evidence.extend(f"{source}:{hit}" for hit in hits)
        scores, hits = _match_keywords(text, MODE_KEYWORDS, weight)
        _merge_scores(mode_scores, scores)
        evidence.extend(f"{source}:{hit}" for hit in hits)

    creator_hint = CREATOR_GAME_HINTS.get(creator)
    if creator_hint:
        game_scores[creator_hint] = round(game_scores.get(creator_hint, 0.0) + 2.0, 3)
        evidence.append(f"creator:{creator}->{creator_hint}")

    hinted_game, hinted_mode = NON_GAME_CHANNEL_HINTS.get(channel_name, (None, None))
    if hinted_game:
        game_scores[hinted_game] = round(game_scores.get(hinted_game, 0.0) + 0.75, 3)
        evidence.append(f"channel:{channel_name}->{hinted_game}")
    if hinted_mode:
        mode_scores[hinted_mode] = round(mode_scores.get(hinted_mode, 0.0) + 0.5, 3)
        evidence.append(f"channel:{channel_name}->{hinted_mode}")

    title_tokens = _token_labels(title)
    if any(token.startswith("1v") for token in title_tokens):
        mode_scores["clutch"] = round(mode_scores.get("clutch", 0.0) + 2.0, 3)
        evidence.append("title:clutch:1vX")

    if creator and "podcast" in creator:
        mode_scores["podcast"] = round(mode_scores.get("podcast", 0.0) + 2.0, 3)
        evidence.append("creator:podcast")

    if metadata.get("transcript_selected"):
        mode_scores["reaction"] = round(mode_scores.get("reaction", 0.0) + 0.5, 3)
        evidence.append("meta:transcript_selected")

    if not game_scores and channel_name in {"arc_highlightz"}:
        game_scores["fortnite"] = 0.75
        evidence.append("channel:arc_highlightz->fortnite_default")
    if not game_scores and channel_name in {"fomo_highlights"}:
        game_scores["warzone"] = 0.5
        evidence.append("channel:fomo_highlights->warzone_soft")

    primary_game = _top_label(game_scores, minimum=1.5)
    primary_mode = _top_label(mode_scores, minimum=1.0)

    if not primary_mode and primary_game:
        primary_mode = "gameplay"
        mode_scores["gameplay"] = round(mode_scores.get("gameplay", 0.0) + 0.5, 3)
        evidence.append("fallback:gameplay_from_game")

    labels: list[str] = []
    if primary_game:
        labels.append(primary_game)
    if primary_mode:
        labels.append(primary_mode)

    for label, score in sorted(mode_scores.items(), key=lambda item: item[1], reverse=True):
        if label not in labels and score >= 2.0:
            labels.append(label)
    for label, score in sorted(game_scores.items(), key=lambda item: item[1], reverse=True):
        if label not in labels and score >= 2.5:
            labels.append(label)

    top_game_score = max(game_scores.values(), default=0.0)
    top_mode_score = max(mode_scores.values(), default=0.0)
    confidence = min(1.0, round((top_game_score + top_mode_score) / 8.0, 3))

    return ClipContentProfile(
        primary_game=primary_game,
        primary_mode=primary_mode,
        game_scores=game_scores,
        mode_scores=mode_scores,
        labels=labels,
        confidence=confidence,
        evidence=evidence[:12],
    )


def content_summary(profile: ClipContentProfile) -> str:
    parts = [part for part in (profile.primary_game, profile.primary_mode) if part]
    if not parts and profile.labels:
        parts = profile.labels[:2]
    return ", ".join(parts)


def profile_to_json(profile: ClipContentProfile) -> str:
    return json.dumps(profile.to_metadata(), ensure_ascii=False, sort_keys=True)
