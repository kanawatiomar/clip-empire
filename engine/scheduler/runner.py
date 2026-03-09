"""Main orchestrator for the Clip Empire engine.

Runs the full pipeline for one or all channels:
  1. Check daily budget (skip if full)
  2. Pick next source from channel config
  3. Download clips via yt-dlp
  4. Dedup filter
  5. Transform: crop → caption → overlay → encode
  6. Enqueue to publish_jobs
  7. Mark source as used in dedup

Usage:
  python -m engine.cli --channel market_meltdowns
  python -m engine.cli --all
  python -m engine.cli --channel gym_moments --count 2 --dry-run
"""

from __future__ import annotations

import os
import shutil
import traceback
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from accounts.channel_definitions import CHANNELS
from engine.config.sources import CHANNEL_SOURCES, SOURCE_DEFAULTS
from engine.ingest.ytdlp import YtDlpIngester
from engine.ingest.dedup import DedupTracker
from engine.ingest.base import RawClip
from engine.ingest.trend_radar import TrendRadar
from engine.ingest.safety import ClipPolicyFilter
from engine.ingest.fingerprint import url_fingerprint, visual_fingerprint
from engine.ingest.sora_lane import SoraLane
from engine.transform.crop import CropTransform
from engine.transform.caption import CaptionTransform
from engine.transform.overlay import OverlayTransform
from engine.transform.encode import EncodeTransform
from engine.scheduler.budget import BudgetManager
from engine.scheduler.queue_writer import QueueWriter
from engine.ops.feedback import PerformanceFeedback
from engine.ops.source_health import SourceHealthMonitor


# Directories (relative to repo root)
RAW_DIR = "raw_clips"
INTERMEDIATE_DIR = "intermediate"
RENDERS_DIR = "renders"
COOKIES_DIR = "cookies"


class Runner:
    """Full pipeline runner for one or all channels."""

    def __init__(
        self,
        dry_run: bool = False,
        skip_caption: bool = False,
        keep_intermediate: bool = False,
        model_size: str = "auto",
        db_path: str = "data/clip_empire.db",
        trend_radar_enabled: bool = False,
        policy_filter_enabled: bool = True,
        sora_lane_enabled: bool = False,
    ):
        self.dry_run = dry_run
        self.skip_caption = skip_caption
        self.keep_intermediate = keep_intermediate
        self.trend_radar_enabled = trend_radar_enabled
        self.policy_filter_enabled = policy_filter_enabled
        self.sora_lane_enabled = sora_lane_enabled

        # Init all pipeline components
        self.budget = BudgetManager(db_path=db_path)
        self.dedup = DedupTracker(db_path=db_path)
        self.ingester = YtDlpIngester(
            download_dir=RAW_DIR,
            cookies_dir=COOKIES_DIR,
        )
        self.trend_radar = TrendRadar()
        self.policy_filter = ClipPolicyFilter()
        self.sora_lane = SoraLane(enabled=sora_lane_enabled)
        self.crop = CropTransform(output_dir=INTERMEDIATE_DIR)
        self.caption = CaptionTransform(
            model_size=model_size,
            output_dir=INTERMEDIATE_DIR,
        ) if not skip_caption else None
        self.overlay = OverlayTransform(output_dir=INTERMEDIATE_DIR)
        self.encode = EncodeTransform(output_dir=RENDERS_DIR)
        self.queue_writer = QueueWriter(db_path=db_path)
        self.feedback = PerformanceFeedback(db_path=db_path)
        self.source_health = SourceHealthMonitor(db_path=db_path)

    def run_all(self, count_per_channel: int = 1) -> dict:
        """Run the pipeline for every active channel.

        Args:
            count_per_channel: Max new clips to produce per channel.

        Returns:
            Dict mapping channel_name → list of job_ids created.
        """
        results = {}
        channels = list(CHANNELS.keys())
        print(f"\n[runner] Starting empire run: {len(channels)} channels, "
              f"{count_per_channel} clips each")

        for channel_name in channels:
            try:
                jobs = self.run_channel(channel_name, count=count_per_channel)
                results[channel_name] = jobs
            except Exception as e:
                print(f"[runner] ERROR on {channel_name}: {e}")
                traceback.print_exc()
                results[channel_name] = []

        total = sum(len(v) for v in results.values())
        print(f"\n[runner] Empire run complete: {total} jobs queued across "
              f"{len([k for k,v in results.items() if v])} channels")
        return results

    def run_channel(self, channel_name: str, count: int = 1) -> List[str]:
        """Run the pipeline for a single channel.

        Args:
            channel_name: Channel to process.
            count:        Number of clips to produce (respects daily budget).

        Returns:
            List of job_ids created.
        """
        if channel_name not in CHANNELS:
            raise ValueError(f"Unknown channel: {channel_name}")

        # Check budget
        slots = self.budget.slots_remaining(channel_name)
        if slots == 0:
            print(f"[runner] {channel_name}: daily budget full, skipping")
            return []

        effective_count = min(count, slots)
        print(f"\n[runner] {channel_name}: {slots} slots available, "
              f"producing {effective_count} clip(s)")

        # Get sources for this channel
        sources = CHANNEL_SOURCES.get(channel_name, [])
        if self.trend_radar_enabled:
            sources = self.trend_radar.augment_sources(channel_name, list(sources))
        if not sources:
            print(f"[runner] {channel_name}: no sources configured")
            return []

        # Sort by priority + performance feedback (better sources first)
        sources = sorted(
            sources,
            key=lambda s: (
                s.get("priority", 99),
                -self.feedback.get_source_score(s.get("url", "")),
            ),
        )

        job_ids = []
        clips_produced = 0

        if self.sora_lane_enabled:
            sora_candidates = self.sora_lane.fetch_candidates(channel_name, limit=effective_count)
            if sora_candidates:
                print(f"[runner] Sora lane provided {len(sora_candidates)} candidate clip(s)")

        for source_config in sources:
            if clips_produced >= effective_count:
                break

            source_key = source_config.get("url", "")
            if not self.source_health.is_healthy(source_key):
                print(f"[runner] Skipping unhealthy source: {source_key[:60]}")
                continue

            needed = effective_count - clips_produced
            per_source = SOURCE_DEFAULTS["max_per_run"]

            try:
                raw_clips = self.ingester.fetch(
                    source_config=source_config,
                    limit=per_source + 2,  # fetch extra to account for dedup losses
                    channel_name=channel_name,
                )
            except Exception as e:
                self.source_health.record_failure(source_key, str(e))
                print(f"[runner] Ingest error from {source_config.get('url','?')[:60]}: {e}")
                continue

            if not raw_clips:
                self.source_health.record_failure(source_key, "no clips returned")
                print(f"[runner] No clips from {source_config.get('url','?')[:60]}")
                continue

            self.source_health.record_success(source_key)

            for clip in raw_clips:
                clip.url_fingerprint = url_fingerprint(clip.source_url)
                clip.visual_fingerprint = visual_fingerprint(clip.download_path)
                # Pass crop_anchor from source config into clip metadata
                if not hasattr(clip, "metadata") or clip.metadata is None:
                    clip.metadata = {}
                clip.metadata["crop_anchor"] = source_config.get("crop_anchor", "center")

            # Filter deduplication
            fresh_clips = self.dedup.filter_unused(raw_clips, channel_name=channel_name)
            fresh_clips = [c for c in fresh_clips if not self.dedup.is_near_duplicate(c)]
            if not fresh_clips:
                print(f"[runner] All clips already used, trying next source")
                continue

            if self.policy_filter_enabled:
                fresh_clips = self.policy_filter.filter(fresh_clips)
                if not fresh_clips:
                    print("[runner] No policy-safe clips from source, trying next source")
                    continue

            # Process each clip
            for clip in fresh_clips[:needed]:
                try:
                    job_id = self._process_clip(clip, channel_name)
                    if job_id:
                        job_ids.append(job_id)
                        self.dedup.mark_used(clip, channel_name)
                        self.feedback.record_source_outcome(source_key, success=True)
                        clips_produced += 1
                except Exception as e:
                    self.feedback.record_source_outcome(source_key, success=False)
                    self.source_health.record_failure(source_key, str(e))
                    print(f"[runner] Pipeline error on clip {clip.clip_id[:8]}: {e}")
                    traceback.print_exc()

        print(f"[runner] {channel_name}: {clips_produced} clip(s) queued")
        return job_ids

    def _process_clip(self, clip: RawClip, channel_name: str) -> Optional[str]:
        """Run a single clip through the full transform pipeline.

        crop → caption → overlay → encode → enqueue

        Returns:
            job_id if successfully queued, None otherwise.
        """
        cid = clip.clip_id[:8]
        print(f"\n[pipeline] Processing clip {cid}: '{clip.title[:50]}'")
        print(f"           Source: {clip.source_url[:70]}")
        print(f"           Duration: {clip.duration_s:.1f}s | {clip.width}x{clip.height}")

        if self.dry_run:
            print(f"[pipeline] DRY RUN — skipping actual processing")
            return None

        try:
            # 1. Crop to 9:16 — use crop_anchor from source config if available
            crop_anchor = clip.metadata.get("crop_anchor", "center")
            cropped = self.crop.process(
                input_path=clip.download_path,
                clip_id=clip.clip_id,
                trim_to_s=55.0,
                crop_anchor=crop_anchor,
            )

            # 2. Caption (optional — skip if no Whisper or --skip-caption)
            ass_path = None
            if self.caption:
                try:
                    ass_path = self.caption.process(
                        video_path=cropped,
                        clip_id=clip.clip_id,
                        channel_name=channel_name,
                    )
                except Exception as e:
                    print(f"[pipeline] Caption failed (non-fatal): {e}")

            # 3. Overlay (hook text + CTA)
            import subprocess
            from pathlib import Path as _Path
            import os as _os
            _ffbin = _Path(_os.environ.get("LOCALAPPDATA","")) / "Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-8.0.1-full_build/bin"
            _ffprobe = str(_ffbin / "ffprobe.exe") if (_ffbin / "ffprobe.exe").exists() else "ffprobe"
            result = subprocess.run(
                [_ffprobe, "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "csv=p=0", cropped],
                capture_output=True, text=True,
            )
            try:
                duration_s = float(result.stdout.strip())
            except Exception:
                duration_s = clip.duration_s or 30.0

            overlaid = self.overlay.process(
                input_path=cropped,
                clip_id=clip.clip_id,
                channel_name=channel_name,
                duration_s=duration_s,
                creator=getattr(clip, "creator", None),
            )

            # 4. Final encode (burns captions + normalizes audio)
            final = self.encode.process(
                video_path=overlaid,
                clip_id=clip.clip_id,
                channel_name=channel_name,
                ass_path=ass_path,
            )

            print(f"[pipeline] Render complete: {final}")

            # 5. Enqueue to publish_jobs
            job_id = self.queue_writer.enqueue(
                channel_name=channel_name,
                render_path=final,
                creator=getattr(clip, "creator", None),
                clip_title=getattr(clip, "title", None),
            )

            # 6. Clean up intermediate files if not keeping
            if not self.keep_intermediate:
                for path in [cropped, overlaid, ass_path]:
                    if path and os.path.exists(path) and path != final:
                        try:
                            os.remove(path)
                        except Exception:
                            pass

            return job_id

        except Exception as e:
            print(f"[pipeline] Failed to process clip {cid}: {e}")
            raise
