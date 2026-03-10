"""Whisper-based caption generator.

Transcribes audio using OpenAI Whisper (GPU if CUDA available, CPU fallback).
Generates a styled ASS subtitle file optimized for YouTube Shorts:
  - Large, bold, centered captions
  - Word-level timing for kinetic effect (if word timestamps available)
  - Drop shadow + outline for readability on any background

Model selection (balance quality vs speed):
  - On GPU (RTX 3070+): "medium" model, ~real-time
  - On CPU only:         "base" model, ~2-3x real-time
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import List, Tuple, Optional

# Inject ffmpeg into PATH so Whisper can find it for audio loading
_FFMPEG_BIN = (
    Path(os.environ.get("LOCALAPPDATA", ""))
    / "Microsoft/WinGet/Packages"
    / "Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe"
    / "ffmpeg-8.0.1-full_build/bin"
)
if _FFMPEG_BIN.exists() and str(_FFMPEG_BIN) not in os.environ.get("PATH", ""):
    os.environ["PATH"] = str(_FFMPEG_BIN) + os.pathsep + os.environ.get("PATH", "")


ASS_HEADER = """\
[Script Info]
ScriptType: v4.00+
Collisions: Normal
PlayResX: 1080
PlayResY: 1920
Timer: 100.0000

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Impact,72,&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,4,3,2,20,20,400,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _seconds_to_ass(seconds: float) -> str:
    """Convert seconds to ASS timestamp format H:MM:SS.cc"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


class CaptionTransform:
    """Generate ASS subtitle file from a video using Whisper."""

    def __init__(
        self,
        model_size: str = "auto",
        output_dir: str = "intermediate",
        language: str = "en",
    ):
        self.model_size = model_size  # "auto" | "tiny" | "base" | "small" | "medium" | "large"
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.language = language
        self._whisper = None  # lazy-loaded

    def _get_model_size(self) -> str:
        if self.model_size != "auto":
            return self.model_size
        # Detect CUDA availability
        try:
            import torch
            if torch.cuda.is_available():
                return "medium"  # Fast on GPU
        except ImportError:
            pass
        return "base"  # Safe on CPU

    def _load_whisper(self):
        if self._whisper is None:
            try:
                import whisper
                size = self._get_model_size()
                print(f"[caption] Loading Whisper '{size}' model...")
                self._whisper = whisper.load_model(size)
            except ImportError:
                raise RuntimeError(
                    "openai-whisper not installed. Run: pip install openai-whisper"
                )
        return self._whisper

    def process(self, video_path: str, clip_id: str, channel_name: str = "", creator: str = "") -> str:
        """Transcribe video and write an ASS subtitle file.

        Returns:
            Path to the .ass file.
        """
        ass_path = str(self.output_dir / f"{clip_id}.ass")

        if os.path.exists(ass_path):
            return ass_path  # already generated

        print(f"[caption] Transcribing {os.path.basename(video_path)}...")

        model = self._load_whisper()

        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"

        result = model.transcribe(
            video_path,
            language=self.language,
            task="transcribe",
            verbose=False,
            word_timestamps=True,
        )

        segments = result.get("segments", [])
        ass_content = self._build_ass(segments, channel_name=channel_name, creator=creator)

        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(ass_content)

        print(f"[caption] ASS subtitles written: {ass_path}")
        return ass_path

    def _build_ass(self, segments: List[dict], channel_name: str = "", creator: str = "") -> str:
        """Build TikTok-style word-highlight ASS captions.

        Each dialogue event shows a group of words (words_per_line).
        Within each group, the currently spoken word is highlighted in
        word_highlight_color while the rest stay in primary_color.
        One event fires per word — no overlapping, no flicker.
        """
        from engine.config.styles import get_caption_style
        style = get_caption_style(channel_name, creator) if (channel_name or creator) else {}

        fontname    = style.get("fontname", "Impact")
        fontsize    = style.get("fontsize", 72)
        primary     = style.get("primary_color", "&H00FFFFFF")
        highlight   = style.get("word_highlight_color", "&H0000FFFF")
        outline_col = style.get("outline_color", "&H00000000")
        back_col    = style.get("back_color", "&H80000000")
        bold        = style.get("bold", 0)
        outline_sz  = style.get("outline_size", 4)
        shadow      = style.get("shadow", 3)
        margin_v    = style.get("margin_v", 400)
        wpl         = style.get("words_per_line", 3)

        header = (
            "[Script Info]\n"
            "ScriptType: v4.00+\n"
            "Collisions: Normal\n"
            "PlayResX: 1080\n"
            "PlayResY: 1920\n"
            "Timer: 100.0000\n\n"
            "[V4+ Styles]\n"
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
            "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
            "Alignment, MarginL, MarginR, MarginV, Encoding\n"
            f"Style: Default,{fontname},{fontsize},{primary},&H000000FF,{outline_col},{back_col},"
            f"{bold},0,0,0,100,100,0,0,1,{outline_sz},{shadow},2,20,20,{margin_v},1\n\n"
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
        )

        events: List[str] = []

        # Collect all words with timestamps across all segments
        all_words: List[dict] = []
        for seg in segments:
            seg_words = seg.get("words", [])
            if seg_words:
                for w in seg_words:
                    if w.get("word", "").strip():
                        all_words.append({
                            "word":  w["word"].strip(),
                            "start": float(w.get("start", seg["start"])),
                            "end":   float(w.get("end",   seg["end"])),
                        })
            else:
                # No word timestamps — fall back to segment-level line
                text = seg.get("text", "").strip()
                if text:
                    line = self._escape_ass(text)
                    events.append(
                        f"Dialogue: 0,{_seconds_to_ass(seg['start'])},"
                        f"{_seconds_to_ass(seg['end'])},Default,,0,0,0,,{line}\n"
                    )

        if not all_words:
            return header + "".join(events)

        # Group words into chunks of `wpl` words
        chunks: List[List[dict]] = []
        for i in range(0, len(all_words), wpl):
            chunks.append(all_words[i : i + wpl])

        # For each chunk, emit one dialogue event per word
        # Each event shows the full chunk but highlights one word
        for chunk in chunks:
            chunk_end = chunk[-1]["end"]

            for active_idx, active_word in enumerate(chunk):
                t_start = active_word["start"]
                # End = start of next word in chunk, or end of last word
                if active_idx + 1 < len(chunk):
                    t_end = chunk[active_idx + 1]["start"]
                else:
                    t_end = chunk_end

                # Skip zero-duration events
                if t_end <= t_start:
                    t_end = t_start + 0.05

                # Build the text: non-active words in primary, active in highlight
                parts = []
                for idx, w in enumerate(chunk):
                    clean = self._escape_ass(w["word"])
                    if idx == active_idx:
                        parts.append(f"{{\\1c{highlight}}}{clean}{{\\1c{primary}}}")
                    else:
                        parts.append(clean)

                line_text = " ".join(parts)
                events.append(
                    f"Dialogue: 0,{_seconds_to_ass(t_start)},"
                    f"{_seconds_to_ass(t_end)},Default,,0,0,0,,{line_text}\n"
                )

        return header + "".join(events)

    @staticmethod
    def _escape_ass(text: str) -> str:
        """Escape special ASS characters."""
        return text.replace("{", "｛").replace("}", "｝").replace("\\", "")

    @staticmethod
    def _wrap_text(text: str, max_chars: int = 40) -> List[str]:
        """Wrap text into lines of at most max_chars characters (fallback only)."""
        words = text.split()
        lines = []
        current = ""
        for word in words:
            if len(current) + len(word) + 1 <= max_chars:
                current = (current + " " + word).strip()
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines or [text[:max_chars]]
