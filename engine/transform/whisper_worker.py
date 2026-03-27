"""Standalone Whisper transcription worker.

Run as a subprocess: python -m engine.transform.whisper_worker <video_path> <model_size> <language>
Outputs JSON to stdout: {"segments": [...]} on success, or exits with code 1 + error to stderr.

This isolation ensures any Whisper/PyTorch crash kills only this subprocess,
not the main engine process.
"""

import sys
import json
import os


def _find_ffmpeg_bin():
    import shutil
    if shutil.which("ffmpeg"):
        return os.path.dirname(shutil.which("ffmpeg"))
    base = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe")
    if os.path.exists(base):
        for d in sorted(os.listdir(base), reverse=True):
            candidate = os.path.join(base, d, "bin")
            if os.path.exists(os.path.join(candidate, "ffmpeg.exe")):
                return candidate
    return "."


def main():
    if len(sys.argv) < 4:
        print("Usage: python -m engine.transform.whisper_worker <video_path> <model_size> <language>", file=sys.stderr)
        sys.exit(1)

    video_path = sys.argv[1]
    model_size = sys.argv[2]
    language = sys.argv[3]

    # Inject ffmpeg into PATH
    ffmpeg_bin = _find_ffmpeg_bin()
    if ffmpeg_bin and ffmpeg_bin not in os.environ.get("PATH", ""):
        os.environ["PATH"] = ffmpeg_bin + os.pathsep + os.environ.get("PATH", "")

    try:
        import whisper
    except ImportError:
        print("openai-whisper not installed", file=sys.stderr)
        sys.exit(1)

    try:
        model = whisper.load_model(model_size)
        result = model.transcribe(
            video_path,
            language=language,
            task="transcribe",
            verbose=False,
            word_timestamps=True,
        )
        # Output only segments (all we need)
        output = {"segments": result.get("segments", [])}
        print(json.dumps(output))
        sys.exit(0)
    except Exception as e:
        print(f"Whisper transcription error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
