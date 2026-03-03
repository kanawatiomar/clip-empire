
import os
import shutil
import uuid
from datetime import datetime
from typing import List, Dict, Any

from pipeline.schemas import ClipAsset, PlatformVariant
from pipeline.templates import get_template_config

def generate_platform_variants(clip_asset: ClipAsset) -> List[PlatformVariant]:
    print(f"Generating platform variants for ClipAsset {clip_asset.clip_id}")

    variants = []
    platforms = ["youtube", "tiktok", "instagram"]

    # Fetch template config for platform-specific adjustments
    template_config = get_template_config(clip_asset.channel_name.split('_')[0] + "_v1", clip_asset.template_id)
    
    for platform in platforms:
        variant_id = str(uuid.uuid4())
        platform_render_dir = os.path.join("renders", platform, clip_asset.channel_name, datetime.now().strftime("%Y-%m-%d"))
        os.makedirs(platform_render_dir, exist_ok=True)
        render_path = os.path.join(platform_render_dir, f"{variant_id}.mp4")

        # Simulate platform-specific rendering/copying
        # In a real scenario, this might involve resizing, re-encoding, adding platform-specific overlays/logos
        if clip_asset.master_render_path:
            shutil.copy(clip_asset.master_render_path, render_path)
        else:
            with open(render_path, 'w') as f:
                f.write("dummy platform render content")

        # Platform-specific caption and hashtag generation (simplified)
        base_caption = f"Check out this {clip_asset.clip_type} from {clip_asset.channel_name}! #shorts"
        base_hashtags = ["shorts", clip_asset.channel_name.replace("_", "")]

        if platform == "youtube":
            caption_text = base_caption
            hashtags = base_hashtags + ["youtubeclips", "viralvideo"]
            first_frame_hook = """Don't Miss This!"""
        elif platform == "tiktok":
            caption_text = f"{base_caption} #fyp"
            hashtags = base_hashtags + ["fyp", "tiktokviral", "trending"]
            first_frame_hook = """WAIT FOR IT!"""
        elif platform == "instagram":
            caption_text = f"{base_caption} #reels"
            hashtags = base_hashtags + ["reels", "instaviral", "explore"]
            first_frame_hook = """Tap to see more!"""
        
        # Apply template-specific overrides if they exist for caption/hashtags for this platform
        if template_config and "platform_overrides" in template_config and platform in template_config["platform_overrides"]:
            platform_override = template_config["platform_overrides"][platform]
            if "caption_text" in platform_override: caption_text = platform_override["caption_text"]
            if "hashtags" in platform_override: hashtags = platform_override["hashtags"]
            if "first_frame_hook" in platform_override: first_frame_hook = platform_override["first_frame_hook"]

        variant = PlatformVariant(
            variant_id=variant_id,
            clip_id=clip_asset.clip_id,
            platform=platform,
            render_path=render_path,
            caption_text=caption_text,
            hashtags=hashtags,
            first_frame_hook=first_frame_hook,
            created_at=datetime.now().isoformat()
        )
        variants.append(variant)
        print(f"  Generated {platform} variant: Path={render_path}")

    return variants

if __name__ == '__main__':
    # Example usage with dummy data
    from pipeline.schemas import Segment
    from pipeline.edit import process_segment_to_clip

    dummy_segment = Segment(
        segment_id=str(uuid.uuid4()),
        source_id=str(uuid.uuid4()),
        start_ms=0, end_ms=30000,
        overall_score=0.8
    )
    dummy_channel_name = "market_meltdowns"
    dummy_clip_asset = process_segment_to_clip(dummy_segment, dummy_channel_name, "clipped", "pnl_shock")

    if dummy_clip_asset:
        platform_variants = generate_platform_variants(dummy_clip_asset)
        print(f"\nGenerated {len(platform_variants)} platform variants.")
