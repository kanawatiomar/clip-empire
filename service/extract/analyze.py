"""
service/extract/analyze.py — Detect scene boundaries and transcribe audio.
Produces a list of candidate segments: [{start, end, transcript}, ...]
"""
import subprocess
import json
import os


def get_duration(video_path: str) -> float:
    """Get video duration in seconds via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "json", video_path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    data = json.loads(result.stdout)
    return float(data["format"]["duration"])


def detect_scenes(video_path: str, min_scene_len: float = 15.0, max_scene_len: float = 60.0) -> list[dict]:
    """
    Use ffmpeg scene detection to find cut points.
    Returns list of {start, end} dicts (seconds).
    Falls back to fixed-interval chunking if ffmpeg scene detection is unavailable.
    """
    duration = get_duration(video_path)
    scenes = []

    try:
        # Try ffmpeg scene detection
        cmd = [
            "ffmpeg", "-i", video_path,
            "-vf", "select='gt(scene,0.3)',showinfo",
            "-f", "null", "-",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        timestamps = []
        for line in result.stderr.splitlines():
            if "pts_time:" in line:
                for part in line.split():
                    if part.startswith("pts_time:"):
                        try:
                            timestamps.append(float(part.split(":")[1]))
                        except ValueError:
                            pass
        if timestamps:
            boundaries = [0.0] + sorted(timestamps) + [duration]
            for i in range(len(boundaries) - 1):
                start = boundaries[i]
                end = boundaries[i + 1]
                if min_scene_len <= (end - start) <= max_scene_len:
                    scenes.append({"start": round(start, 2), "end": round(end, 2)})
    except Exception:
        pass

    # Fallback: fixed 30-second chunks
    if not scenes:
        chunk = 30.0
        t = 0.0
        while t < duration:
            end = min(t + chunk, duration)
            if (end - t) >= 10.0:
                scenes.append({"start": round(t, 2), "end": round(end, 2)})
            t += chunk

    return scenes


def transcribe_segment(video_path: str, start: float, end: float, work_dir: str) -> str:
    """
    Extract audio for a segment and transcribe via Whisper CLI.
    Returns transcript string (empty string on failure).
    """
    seg_audio = os.path.join(work_dir, f"seg_{int(start)}_{int(end)}.wav")
    # Extract audio segment
    subprocess.run([
        "ffmpeg", "-y",
        "-i", video_path,
        "-ss", str(start), "-to", str(end),
        "-ar", "16000", "-ac", "1", "-f", "wav",
        seg_audio,
    ], capture_output=True)

    if not os.path.exists(seg_audio):
        return ""

    try:
        result = subprocess.run(
            ["whisper", seg_audio, "--model", "base", "--output_format", "txt", "--output_dir", work_dir],
            capture_output=True, text=True, timeout=120,
        )
        txt_file = seg_audio.replace(".wav", ".txt")
        if os.path.exists(txt_file):
            with open(txt_file) as f:
                return f.read().strip()
    except Exception:
        pass
    return ""


def analyze_video(video_path: str, job_id: str) -> list[dict]:
    """
    Full analysis: scene detection + transcription per segment.
    Returns list of {start, end, transcript, duration} dicts.
    """
    work_dir = os.path.join("data", "intake", job_id, "segments")
    os.makedirs(work_dir, exist_ok=True)

    scenes = detect_scenes(video_path)
    print(f"[analyze] {len(scenes)} scenes detected in {os.path.basename(video_path)}")

    segments = []
    for scene in scenes[:30]:  # cap at 30 candidates
        transcript = transcribe_segment(video_path, scene["start"], scene["end"], work_dir)
        segments.append({
            "start": scene["start"],
            "end": scene["end"],
            "duration": round(scene["end"] - scene["start"], 2),
            "transcript": transcript,
        })

    return segments
