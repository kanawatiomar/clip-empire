
from dataclasses import dataclass, field
from typing import Optional, List, Dict
from datetime import datetime
import json

@dataclass
class Source:
    source_id: str
    type: str  # e.g., 'streamer_vod', 'youtube_video', 'original'
    url: Optional[str] = None
    creator: Optional[str] = None
    title: Optional[str] = None
    download_path: Optional[str] = None
    duration_s: Optional[float] = None
    ingested_at: str = field(default_factory=lambda: datetime.now().isoformat())
    notes: Optional[str] = None

@dataclass
class Segment:
    segment_id: str
    source_id: str
    start_ms: int
    end_ms: int
    hook_score: Optional[float] = None
    story_score: Optional[float] = None
    novelty_score: Optional[float] = None
    category_fit_score: Optional[float] = None
    overall_score: Optional[float] = None
    language: Optional[str] = None
    transcript_path: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class ClipAsset:
    clip_id: str
    segment_id: str
    channel_name: str
    clip_type: str  # e.g., 'clipped', 'remixed', 'original'
    template_id: Optional[str] = None  # e.g., 'finance_pnl_shock'
    template_version: Optional[str] = None  # e.g., 'finance_v1'
    target_length_s: Optional[float] = None
    master_render_path: Optional[str] = None
    audio_lufs: Optional[float] = None
    qa_status: str = 'unknown'  # e.g., 'pass', 'fail', 'needs_review'
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

@dataclass
class PlatformVariant:
    variant_id: str
    clip_id: str
    platform: str  # e.g., 'youtube', 'tiktok', 'instagram'
    render_path: Optional[str] = None
    caption_text: Optional[str] = None
    hashtags: List[str] = field(default_factory=list)
    first_frame_hook: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self):
        d = self.__dict__.copy()
        d['hashtags'] = json.dumps(d['hashtags'])
        return d

    @classmethod
    def from_dict(cls, d):
        d_copy = d.copy()
        if 'hashtags' in d_copy and isinstance(d_copy['hashtags'], str):
            d_copy['hashtags'] = json.loads(d_copy['hashtags'])
        return cls(**d_copy)



