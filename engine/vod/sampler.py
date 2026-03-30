"""Grid audio sampling for Twitch VODs.

Instead of downloading the full audio (~900MB for a 9h stream),
downloads N short 30-second windows evenly spaced across the VOD,
analyzes their RMS energy, and returns the top moments.

Typical cost: 20 samples × 30s × 223kbps = ~17MB, ~1-2 minutes.
Compare to full audio download: ~900MB, 4+ hours.
"""

from __future__ import annotations

import os
import struct
import subprocess
import tempfile
import wave
from pathlib import Path

import yt_dlp

# ffmpeg path (mirrors encode.py)
_FFMPEG_BIN_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / (
    "Microsoft/WinGet/Packages/"
    "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/"
    "ffmpeg-8.1-full_build/bin"
)
FFMPEG_BIN  = str(_FFMPEG_BIN_DIR / "ffmpeg.exe")  if (_FFMPEG_BIN_DIR / "ffmpeg.exe").exists()  else "ffmpeg"
FFPROBE_BIN = str(_FFMPEG_BIN_DIR / "ffprobe.exe") if (_FFMPEG_BIN_DIR / "ffprobe.exe").exists() else "ffprobe"

SAMPLE_WINDOW_S = 30   # seconds per sample
N_SAMPLES       = 20   # number of evenly-spaced samples
MERGE_GAP_S     = 120  # merge top picks closer than this


def _ensure_ffmpeg_in_path() -> None:
    ffmpeg_dir = str(_FFMPEG_BIN_DIR)
    if ffmpeg_dir not in os.environ.get("PATH", ""):
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + os.environ.get("PATH", "")


def _rms_of_wav(wav_path: str) -> float:
    """Return RMS energy of a WAV file."""
    try:
        with wave.open(wav_path, "rb") as wf:
            sampwidth = wf.getsampwidth()
            n_channels = wf.getnchannels()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)
            if sampwidth == 2:
                samples = struct.unpack(f"<{len(raw)//2}h", raw)
            elif sampwidth == 1:
                samples = tuple(b - 128 for b in raw)
            else:
                return 0.0
            if n_channels > 1:
                samples = [sum(samples[i::n_channels]) / n_channels
                           for i in range(n_channels)]
            return (sum(s * s for s in samples) / max(len(samples), 1)) ** 0.5
    except Exception:
        return 0.0


def _download_sample(
    vod_url: str,
    start_s: float,
    out_wav: str,
    window_s: int = SAMPLE_WINDOW_S,
) -> bool:
    """Download a single audio sample from a VOD timestamp."""
    _ensure_ffmpeg_in_path()
    end_s = start_s + window_s

    def _ts(s: float) -> str:
        h, r = divmod(int(s), 3600)
        m, sec = divmod(r, 60)
        return f"{h:02d}:{m:02d}:{sec:02d}"

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "format": "Audio_Only/bestaudio/best",
        "outtmpl": out_wav.replace(".wav", ".%(ext)s"),
        "download_ranges": yt_dlp.utils.download_range_func(None, [(start_s, end_s)]),
        "force_keyframes_at_cuts": True,
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
            "preferredquality": "0",
        }],
        "postprocessor_args": {"ffmpeg": ["-ac", "1", "-ar", "16000"]},
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([vod_url])
        # Handle extension mismatch
        if not os.path.exists(out_wav):
            base = out_wav.replace(".wav", "")
            for ext in [".wav", ".m4a", ".mp3", ".opus", ".webm", ".mp4"]:
                p = base + ext
                if os.path.exists(p):
                    if ext != ".wav":
                        subprocess.run(
                            [FFMPEG_BIN, "-y", "-i", p, "-ac", "1", "-ar", "16000", out_wav],
                            capture_output=True, timeout=30,
                        )
                    else:
                        os.rename(p, out_wav)
                    break
        return os.path.exists(out_wav)
    except Exception:
        return False


def sample_vod_peaks(
    vod_url: str,
    vod_duration_s: float,
    top_n: int = 10,
    n_samples: int = N_SAMPLES,
) -> list[tuple[float, float]]:
    """Sample N evenly-spaced 30s windows from a VOD, return top moments by RMS energy.

    Returns list of (timestamp_s, energy_score) sorted by score descending.
    """
    if vod_duration_s < SAMPLE_WINDOW_S * 2:
        return []

    # Skip first and last 5% of VOD (intros/outros have high audio but boring)
    skip = vod_duration_s * 0.05
    usable = vod_duration_s - 2 * skip

    step = usable / (n_samples + 1)
    sample_times = [skip + step * (i + 1) for i in range(n_samples)]

    print(f"[sampler] Sampling {n_samples} windows from {vod_duration_s/3600:.1f}h VOD...")

    rms_scores: list[tuple[float, float]] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        for i, t in enumerate(sample_times):
            out_wav = os.path.join(tmpdir, f"sample_{i:03d}.wav")
            ok = _download_sample(vod_url, t, out_wav)
            if ok:
                rms = _rms_of_wav(out_wav)
                rms_scores.append((t, rms))
                if (i + 1) % 5 == 0:
                    print(f"[sampler]   {i+1}/{n_samples} samples done...")
            else:
                print(f"[sampler]   Sample {i+1} at {t:.0f}s failed (skipped)")

    if not rms_scores:
        print("[sampler] No samples collected")
        return []

    # Normalize scores
    mean_rms = sum(r for _, r in rms_scores) / len(rms_scores)
    if mean_rms == 0:
        return []

    normalized = [(t, rms / mean_rms) for t, rms in rms_scores]
    normalized.sort(key=lambda x: x[1], reverse=True)

    # Greedy merge: skip peaks within MERGE_GAP_S of a higher one
    peaks: list[tuple[float, float]] = []
    used: list[float] = []
    for t, score in normalized:
        if any(abs(t - u) < MERGE_GAP_S for u in used):
            continue
        peaks.append((t, score))
        used.append(t)
        if len(peaks) >= top_n:
            break

    print(f"[sampler] Top {len(peaks)} peak moment(s):")
    for t, score in peaks[:5]:
        h, m = divmod(int(t), 3600)
        m, s = divmod(m, 60)
        print(f"  {h:02d}:{m:02d}:{s:02d}  (energy={score:.2f}×mean)")

    return peaks
