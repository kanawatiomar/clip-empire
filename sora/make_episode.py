import os
import time
import requests
import subprocess
from pathlib import Path
from datetime import datetime

ROOT = Path(r"C:\Users\kanaw\.openclaw\workspace\ventures\clip_empire")
SORA_DIR = ROOT / "sora"
OUT_DIR = SORA_DIR / "footage" / "episodes"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Load .env
for line in (ROOT / ".env").read_text().splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

API_KEY = os.environ.get("OPENAI_API_KEY")
if not API_KEY:
    raise RuntimeError("OPENAI_API_KEY missing")

HEADERS = {
    "Authorization": f"Bearer {API_KEY}",
    "Content-Type": "application/json",
}

MODEL = "sora-2"
SIZE = "720x1280"
SECONDS = "8"

SCENES = [
    "Colorful 2D cartoon animation, cheerful fox character in blue hoodie walking into a bright futuristic city at sunrise, smooth camera pan, family friendly",
    "Colorful 2D cartoon animation, same cheerful fox character in blue hoodie looking at a giant glowing digital map in a plaza, gentle camera push in, family friendly",
    "Colorful 2D cartoon animation, same cheerful fox character in blue hoodie running across rooftop bridges with neon lights, energetic motion, family friendly",
    "Colorful 2D cartoon animation, same cheerful fox character in blue hoodie standing on rooftop overlooking city sunset, hopeful ending, slow cinematic zoom out, family friendly",
]


def create_video(prompt: str) -> str:
    r = requests.post(
        "https://api.openai.com/v1/videos",
        headers=HEADERS,
        json={"model": MODEL, "prompt": prompt, "size": SIZE, "seconds": SECONDS},
        timeout=60,
    )
    r.raise_for_status()
    return r.json()["id"]


def wait_complete(video_id: str) -> dict:
    for _ in range(80):
        r = requests.get(f"https://api.openai.com/v1/videos/{video_id}", headers=HEADERS, timeout=30)
        r.raise_for_status()
        data = r.json()
        st = data.get("status")
        pr = data.get("progress", 0)
        print(video_id[-8:], st, pr)
        if st == "completed":
            return data
        if st in ("failed", "cancelled"):
            raise RuntimeError(data)
        time.sleep(15)
    raise TimeoutError(video_id)


def download(video_id: str, out: Path):
    with requests.get(f"https://api.openai.com/v1/videos/{video_id}/content", headers=HEADERS, stream=True, timeout=180) as r:
        r.raise_for_status()
        with open(out, "wb") as f:
            for c in r.iter_content(8192):
                if c:
                    f.write(c)


def main():
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    parts = []
    for i, prompt in enumerate(SCENES, 1):
        print(f"\nScene {i}: generating")
        try:
            vid = create_video(prompt)
            wait_complete(vid)
            part = OUT_DIR / f"episode_{ts}_scene{i}.mp4"
            download(vid, part)
            print("saved", part.name, part.stat().st_size)
            parts.append(part)
        except Exception as e:
            print(f"Scene {i} failed: {e}")
            return 1

    list_file = OUT_DIR / f"episode_{ts}_concat.txt"
    list_file.write_text("\n".join([f"file '{p.as_posix()}'" for p in parts]), encoding="utf-8")

    out = OUT_DIR / f"episode_{ts}_full.mp4"
    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(list_file),
        "-vf", "fps=30,format=yuv420p",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-an",
        str(out),
    ]
    subprocess.run(cmd, check=True)
    print("FULL_EPISODE", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
