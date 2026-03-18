"""
service/extract/generate.py — Generate clip candidates from analyzed segments.
Each candidate = a cropped 9:16 clip with title/description/hashtags.
"""
import os
import uuid
import json
import subprocess
from datetime import datetime, timezone


NICHE_HASHTAGS = {
    "finance": ["#finance", "#money", "#investing", "#stocks", "#wealth"],
    "business": ["#business", "#entrepreneurship", "#startup", "#success"],
    "tech": ["#tech", "#ai", "#technology", "#innovation"],
    "fitness": ["#fitness", "#gym", "#health", "#workout"],
    "food": ["#food", "#cooking", "#recipe", "#foodie"],
    "truecrime": ["#truecrime", "#crime", "#mystery", "#documentary"],
    "default": ["#viral", "#shorts", "#trending", "#fyp"],
}


def _make_title(transcript: str, niche: str = "default") -> str:
    """Generate a short punchy title from transcript snippet."""
    snippet = transcript[:80].strip() if transcript else ""
    if snippet:
        return snippet.split(".")[0].strip()[:60] or f"{niche.title()} Clip"
    return f"{niche.title()} Clip"


def _get_hashtags(niche: str = "default") -> list[str]:
    return NICHE_HASHTAGS.get(niche, NICHE_HASHTAGS["default"])


def extract_clip(video_path: str, start: float, end: float, output_path: str) -> bool:
    """Extract and crop a 9:16 vertical clip using ffmpeg."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-ss", str(start), "-to", str(end),
        "-vf", (
            "scale=1920:1080,boxblur=luma_radius=min(h\\,w)/20:luma_power=1,"
            "scale=1080:1920:force_original_aspect_ratio=decrease,"
            "pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
            "[in]scale=iw*0.9:ih*0.9[fg];"
            "[0:v][fg]overlay=(W-w)/2:(H-h)/2"
        ),
        "-c:v", "libx264", "-preset", "fast", "-crf", "23",
        "-c:a", "aac", "-b:a", "128k",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True)
    return result.returncode == 0


def generate_candidates(
    video_path: str,
    segments: list[dict],
    job_id: str,
    client_id: str,
    niche: str = "default",
) -> list[dict]:
    """
    For each segment, extract a clip and build candidate metadata.
    Returns list of candidate dicts (also written to data/intake/<job_id>/candidates.json).
    """
    out_dir = os.path.join("data", "intake", job_id, "clips")
    os.makedirs(out_dir, exist_ok=True)

    candidates = []
    for seg in segments:
        candidate_id = str(uuid.uuid4())[:8]
        clip_filename = f"clip_{candidate_id}.mp4"
        clip_path = os.path.join(out_dir, clip_filename)

        print(f"[generate] Extracting clip {candidate_id} ({seg['start']}s–{seg['end']}s)...")
        ok = extract_clip(video_path, seg["start"], seg["end"], clip_path)
        if not ok:
            print(f"[generate] Skipping {candidate_id} (ffmpeg failed)")
            continue

        title = _make_title(seg.get("transcript", ""), niche)
        hashtags = _get_hashtags(niche)
        description = seg.get("transcript", "")[:200]

        candidates.append({
            "candidate_id": candidate_id,
            "job_id": job_id,
            "clip_path": os.path.abspath(clip_path),
            "title": title,
            "description": description,
            "hashtags": hashtags,
            "duration": seg["duration"],
            "start": seg["start"],
            "end": seg["end"],
            "transcript": seg.get("transcript", ""),
            "status": "pending_review",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    # Save candidates manifest
    manifest_path = os.path.join("data", "intake", job_id, "candidates.json")
    with open(manifest_path, "w") as f:
        json.dump(candidates, f, indent=2)
    print(f"[generate] {len(candidates)} candidates → {manifest_path}")

    return candidates
