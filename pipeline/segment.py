"""Segment detection — finds the best moments in a video for Shorts.

Strategy (v1): audio energy analysis
  1. Extract audio from video via ffmpeg
  2. Compute RMS energy in sliding windows
  3. Score windows by peak energy, sustained energy, and energy variance
  4. Filter overlapping segments, return top N

v2 (future): add speech density via Whisper word timestamps + motion detection
"""

from __future__ import annotations

import os
import uuid
import subprocess
import tempfile
import struct
import wave
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from pipeline.schemas import Source, Segment


# ── Config ────────────────────────────────────────────────────────────────────

WINDOW_SEC = 45          # candidate clip length (seconds)
STEP_SEC = 5             # sliding window step
MIN_CLIP_SEC = 25        # shortest acceptable clip
MAX_CLIP_SEC = 60        # longest acceptable clip
TOP_N = 5                # return up to N segments
MIN_GAP_SEC = 15         # minimum gap between segment starts to avoid overlap
SAMPLE_RATE = 16000      # audio sample rate for analysis


# ── Audio extraction ──────────────────────────────────────────────────────────

def extract_audio_wav(video_path: str, out_path: str, sample_rate: int = SAMPLE_RATE) -> bool:
    """Extract mono WAV from video using ffmpeg. Returns True on success."""
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-ac", "1",                    # mono
        "-ar", str(sample_rate),       # sample rate
        "-vn",                         # no video
        "-f", "wav",
        out_path,
        "-loglevel", "error",
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, timeout=120)
        return result.returncode == 0 and os.path.exists(out_path)
    except Exception as e:
        print(f"[segment] ffmpeg audio extract failed: {e}")
        return False


def read_wav_samples(wav_path: str) -> tuple[list[float], int]:
    """Read WAV file, return (samples_list, sample_rate)."""
    with wave.open(wav_path, "rb") as wf:
        sr = wf.getframerate()
        n_frames = wf.getnframes()
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        raw = wf.readframes(n_frames)

    # Parse raw bytes to float samples
    if sampwidth == 2:
        fmt = f"<{n_frames * n_channels}h"
        raw_samples = struct.unpack(fmt, raw)
        scale = 32768.0
    elif sampwidth == 1:
        fmt = f"{n_frames * n_channels}B"
        raw_samples = struct.unpack(fmt, raw)
        scale = 128.0
    else:
        # 32-bit
        fmt = f"<{n_frames * n_channels}i"
        raw_samples = struct.unpack(fmt, raw)
        scale = 2147483648.0

    # Mix down to mono if needed
    if n_channels > 1:
        samples = [
            sum(raw_samples[i:i + n_channels]) / (n_channels * scale)
            for i in range(0, len(raw_samples), n_channels)
        ]
    else:
        samples = [s / scale for s in raw_samples]

    return samples, sr


# ── Energy analysis ───────────────────────────────────────────────────────────

def compute_rms_energy(samples: list[float], sr: int, frame_sec: float = 0.05) -> list[float]:
    """Compute RMS energy in short frames. Returns energy per frame."""
    frame_size = int(sr * frame_sec)
    energy = []
    for i in range(0, len(samples) - frame_size, frame_size):
        frame = samples[i:i + frame_size]
        rms = (sum(x * x for x in frame) / len(frame)) ** 0.5
        energy.append(rms)
    return energy


def smooth(values: list[float], window: int = 10) -> list[float]:
    """Simple moving average smoothing."""
    result = []
    half = window // 2
    for i in range(len(values)):
        start = max(0, i - half)
        end = min(len(values), i + half + 1)
        result.append(sum(values[start:end]) / (end - start))
    return result


def score_window(
    energy: list[float],
    start_frame: int,
    end_frame: int,
) -> float:
    """Score a window of energy frames. Higher = better clip candidate.

    Scoring factors:
    - mean energy: sustained loud audio = talking, reactions
    - peak energy: exciting moments
    - energy variance: dynamic range = more interesting than flat
    """
    window = energy[start_frame:end_frame]
    if not window:
        return 0.0

    mean_e = sum(window) / len(window)
    peak_e = max(window)
    variance = sum((x - mean_e) ** 2 for x in window) / len(window)

    # Weighted score
    score = (mean_e * 0.5) + (peak_e * 0.3) + (variance ** 0.5 * 0.2)
    return round(score, 6)


# ── Main detection ────────────────────────────────────────────────────────────

def detect_and_score_segments(
    source: Source,
    category: str,
    window_sec: float = WINDOW_SEC,
    step_sec: float = STEP_SEC,
    top_n: int = TOP_N,
    min_gap_sec: float = MIN_GAP_SEC,
) -> List[Segment]:
    """Detect and score candidate segments from a video.

    Args:
        source:     Source object with download_path pointing to video file
        category:   Content category (used for future category-specific tuning)
        window_sec: Length of each candidate clip
        step_sec:   Sliding window step size
        top_n:      Max number of segments to return
        min_gap_sec: Minimum gap between segment start times

    Returns:
        List of Segment objects sorted by overall_score descending
    """
    video_path = source.download_path
    if not video_path or not os.path.exists(video_path):
        print(f"[segment] Video not found: {video_path}")
        return _fallback_segments(source, top_n)

    print(f"[segment] Analyzing: {os.path.basename(video_path)}")

    # Extract audio to temp WAV
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = tmp.name

    try:
        if not extract_audio_wav(video_path, wav_path):
            print("[segment] Audio extraction failed, using fallback segments")
            return _fallback_segments(source, top_n)

        samples, sr = read_wav_samples(wav_path)
        duration_s = len(samples) / sr
        print(f"[segment] Duration: {duration_s:.1f}s | SR: {sr}Hz")

        if duration_s < MIN_CLIP_SEC:
            print(f"[segment] Video too short ({duration_s:.1f}s), using whole video")
            return [_make_segment(source, 0, duration_s * 1000, score=0.5)]

        # Compute energy
        energy = compute_rms_energy(samples, sr)
        energy = smooth(energy, window=20)

        frames_per_sec = len(energy) / duration_s
        window_frames = int(window_sec * frames_per_sec)
        step_frames = int(step_sec * frames_per_sec)
        gap_frames = int(min_gap_sec * frames_per_sec)

        # Slide window across entire video
        candidates = []
        i = 0
        while i + window_frames <= len(energy):
            score = score_window(energy, i, i + window_frames)
            start_s = i / frames_per_sec
            end_s = (i + window_frames) / frames_per_sec
            candidates.append((score, start_s, end_s))
            i += step_frames

        if not candidates:
            return _fallback_segments(source, top_n)

        # Sort by score descending
        candidates.sort(key=lambda x: x[0], reverse=True)

        # Greedy non-overlapping selection
        selected = []
        used_starts = []
        for score, start_s, end_s in candidates:
            # Check minimum gap from already selected segments
            too_close = any(abs(start_s - used) < min_gap_sec for used in used_starts)
            if not too_close:
                selected.append((score, start_s, end_s))
                used_starts.append(start_s)
            if len(selected) >= top_n:
                break

        # Normalize scores to 0-1 range
        max_score = max(s[0] for s in selected) if selected else 1.0
        min_score = min(s[0] for s in selected) if selected else 0.0
        score_range = max_score - min_score if max_score != min_score else 1.0

        segments = []
        for raw_score, start_s, end_s in selected:
            normalized = (raw_score - min_score) / score_range
            seg = _make_segment(source, start_s * 1000, end_s * 1000, score=normalized)
            segments.append(seg)

        print(f"[segment] Found {len(segments)} segments")
        for seg in segments:
            print(f"  [{seg.start_ms/1000:.1f}s → {seg.end_ms/1000:.1f}s] score={seg.overall_score:.3f}")

        return segments

    finally:
        try:
            os.unlink(wav_path)
        except Exception:
            pass


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_segment(
    source: Source,
    start_ms: float,
    end_ms: float,
    score: float = 0.5,
) -> Segment:
    """Create a Segment dataclass from timestamps and score."""
    return Segment(
        segment_id=str(uuid.uuid4()),
        source_id=source.source_id,
        start_ms=int(start_ms),
        end_ms=int(end_ms),
        hook_score=round(score, 3),
        story_score=round(score * 0.9, 3),
        novelty_score=round(score * 0.85, 3),
        category_fit_score=round(score * 0.95, 3),
        overall_score=round(score, 3),
        created_at=datetime.now().isoformat(),
    )


def _fallback_segments(source: Source, n: int = 3) -> List[Segment]:
    """Return evenly spaced fallback segments when analysis fails."""
    print("[segment] Using fallback: evenly spaced segments")
    # Try to get duration from source metadata
    duration_ms = 180_000  # default 3 min if unknown
    segments = []
    for i in range(min(n, 3)):
        start_ms = i * (duration_ms // n)
        end_ms = start_ms + WINDOW_SEC * 1000
        segments.append(_make_segment(source, start_ms, end_ms, score=0.4 + i * 0.05))
    return segments


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m pipeline.segment <video_path>")
        sys.exit(1)

    from pipeline.schemas import Source

    video = sys.argv[1]
    dummy_source = Source(
        source_id=str(uuid.uuid4()),
        url=video,
        platform="local",
        creator="test",
        title=os.path.basename(video),
        download_path=video,
        duration_s=0,
        view_count=0,
        upload_date="",
        fetched_at=datetime.now().isoformat(),
        metadata={},
    )
    segs = detect_and_score_segments(dummy_source, "Finance")
    print(f"\n✅ {len(segs)} segments detected")
