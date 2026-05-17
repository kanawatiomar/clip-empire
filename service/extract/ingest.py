"""
service/extract/ingest.py — Download or locate the source video for an intake job.
Returns a local file path ready for analysis.
"""
import os
import subprocess
import tempfile


def download_url(url: str, output_dir: str) -> str:
    """
    Download a video from URL using yt-dlp.
    Returns the path to the downloaded file.
    """
    os.makedirs(output_dir, exist_ok=True)
    out_template = os.path.join(output_dir, "%(id)s.%(ext)s")
    cmd = [
        "yt-dlp",
        "--format", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "--merge-output-format", "mp4",
        "--output", out_template,
        "--no-playlist",
        url,
    ]
    print(f"[ingest] Downloading: {url}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"yt-dlp failed:\n{result.stderr}")

    # Find the downloaded file
    files = [f for f in os.listdir(output_dir) if f.endswith(".mp4")]
    if not files:
        raise FileNotFoundError(f"No mp4 found in {output_dir} after download")
    return os.path.join(output_dir, sorted(files)[-1])


def resolve_file(file_path: str) -> str:
    """Validate and return the absolute path to a local file."""
    path = os.path.abspath(file_path)
    if not os.path.exists(path):
        raise FileNotFoundError(f"File not found: {path}")
    return path


def get_source_video(source_type: str, source_path: str, job_id: str) -> str:
    """
    Given a source_type ('url' or 'file') and source_path,
    return the local file path ready for analysis.
    """
    work_dir = os.path.join("data", "intake", job_id)
    os.makedirs(work_dir, exist_ok=True)

    if source_type == "url":
        return download_url(source_path, work_dir)
    elif source_type == "file":
        return resolve_file(source_path)
    else:
        raise ValueError(f"Unknown source_type: {source_type}")
