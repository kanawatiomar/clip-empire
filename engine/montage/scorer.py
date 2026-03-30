"""Score clips by audio energy — higher score = more exciting moment.

Uses RMS peak/mean ratio: a spiky audio profile (explosions, reactions, hype)
scores higher than flat calm gameplay or talking.
"""

from __future__ import annotations

from engine.ingest.longform import extract_pcm_audio, compute_rms_per_second


def score_clips(clips: list[dict]) -> list[dict]:
    """Add 'energy_score' to each clip dict and return sorted by score DESC.

    energy_score = peak_rms / mean_rms
    High ratio = the clip has at least one big audio spike (exciting moment).
    Low ratio  = flat audio (talking, idle gameplay).
    """
    for clip in clips:
        path = clip.get("path") or clip.get("render_path", "")
        try:
            pcm = extract_pcm_audio(path)
            rms_per_sec = compute_rms_per_second(pcm)
            if not rms_per_sec:
                clip["energy_score"] = 0.0
                continue
            mean_rms = sum(rms_per_sec) / len(rms_per_sec)
            peak_rms = max(rms_per_sec)
            if mean_rms < 1.0:
                clip["energy_score"] = 0.0
            else:
                clip["energy_score"] = round(peak_rms / mean_rms, 3)
        except Exception as e:
            print(f"[scorer] Failed to score {path}: {e}")
            clip["energy_score"] = 0.0

    clips.sort(key=lambda c: c["energy_score"], reverse=True)
    return clips
