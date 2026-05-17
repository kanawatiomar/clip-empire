"""Processing pipeline: RawClip → publish-ready 1080x1920 MP4.

Steps:
  1. Crop to 9:16 (1080x1920) with blurred background fill
  2. Generate captions (Whisper — skipped gracefully if not installed)
  3. Final encode: burn captions, normalize audio, NVENC if available

Usage:
    from pipeline.process import process_clip
    from engine.ingest.base import RawClip

    result = process_clip(clip, channel_name="market_meltdowns")
    # result = {"render_path": "...", "clip_id": "...", "title": "..."}
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.ingest.base import RawClip
from engine.transform.crop import CropTransform
from engine.transform.caption import CaptionTransform
from engine.transform.encode import EncodeTransform


# Shared transform instances (reused across clips to avoid re-init overhead)
_crop: Optional[CropTransform] = None
_caption: Optional[CaptionTransform] = None
_encode: Optional[EncodeTransform] = None


def _get_transforms(renders_dir: str = "renders") -> tuple:
    global _crop, _caption, _encode
    if _crop is None:
        _crop = CropTransform(output_dir="intermediate/cropped")
    if _encode is None:
        _encode = EncodeTransform(output_dir=renders_dir)
    return _crop, _caption, _encode


def process_clip(
    clip: RawClip,
    channel_name: str,
    use_captions: bool = True,
    renders_dir: str = "renders",
) -> Optional[Dict[str, Any]]:
    """Transform a raw downloaded clip into a publish-ready Shorts MP4.

    Args:
        clip:          RawClip with a valid download_path
        channel_name:  Target channel (used for output folder organization)
        use_captions:  If True, attempt Whisper captioning (skips if not installed)
        renders_dir:   Root dir for final rendered output

    Returns:
        Dict with render_path, clip_id, title, duration_s — or None on failure.
    """
    if not clip.download_path or not Path(clip.download_path).exists():
        print(f"[process] SKIP {clip.clip_id}: download_path missing or file not found")
        return None

    crop_xform, _, encode_xform = _get_transforms(renders_dir)

    # Re-init encode per channel dir
    channel_render_dir = str(Path(renders_dir) / channel_name)
    encode_xform = EncodeTransform(output_dir=channel_render_dir)

    print(f"[process:{channel_name}] Processing: {clip.title[:60]}")

    # ── Step 1: Crop to 9:16 ──────────────────────────────────────────────
    try:
        cropped_path = crop_xform.process(
            input_path=clip.download_path,
            clip_id=clip.clip_id,
        )
        print(f"[process:{channel_name}]   ✓ Cropped → {Path(cropped_path).name}")
    except Exception as e:
        print(f"[process:{channel_name}]   ✗ Crop failed: {e}")
        return None

    # ── Step 2: Captions (optional) ───────────────────────────────────────
    global _caption
    ass_path: Optional[str] = None
    if use_captions:
        try:
            if _caption is None:
                # Lazy-create caption transform only when first needed
                _caption = CaptionTransform(output_dir="intermediate/captions")
            ass_path = _caption.process(video_path=cropped_path, clip_id=clip.clip_id)
            print(f"[process:{channel_name}]   ✓ Captions → {Path(ass_path).name}")
        except RuntimeError as e:
            # Whisper not installed — skip captions silently
            print(f"[process:{channel_name}]   ~ Captions skipped: {e}")
        except Exception as e:
            print(f"[process:{channel_name}]   ~ Caption error (skipping): {e}")

    # ── Step 3: Final encode ──────────────────────────────────────────────
    try:
        render_path = encode_xform.process(
            video_path=cropped_path,
            clip_id=clip.clip_id,
            channel_name=channel_name,
            ass_path=ass_path,
        )
        print(f"[process:{channel_name}]   ✓ Encoded → {Path(render_path).name}")
    except Exception as e:
        print(f"[process:{channel_name}]   ✗ Encode failed: {e}")
        return None

    return {
        "render_path": render_path,
        "clip_id": clip.clip_id,
        "title": clip.title,
        "duration_s": clip.duration_s,
        "source_url": clip.source_url,
        "platform": clip.platform,
        "creator": clip.creator,
    }
