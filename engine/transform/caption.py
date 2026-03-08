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

    def process(self, video_path: str, clip_id: str, channel_name: str = "") -> str:
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
        ass_content = self._build_ass(segments, channel_name=channel_name)

        with open(ass_path, "w", encoding="utf-8") as f:
            f.write(ass_content)

        print(f"[caption] ASS subtitles written: {ass_path}")
        return ass_path

    def _build_ass(self, segments: List[dict], channel_name: str = "") -> str:
        """Build ASS content from Whisper segments with per-channel styling."""
        from engine.config.styles import get_caption_style
        style = get_caption_style(channel_name) if channel_name else {}

        fontname    = style.get("fontname", "Impact")
        fontsize    = style.get("fontsize", 72)
        primary     = style.get("primary_color", "&H00FFFFFF")
        outline_col = style.get("outline_color", "&H00000000")
        back_col    = style.get("back_color", "&H80000000")
        bold        = style.get("bold", 0)
        outline_sz  = style.get("outline_size", 4)
        shadow      = style.get("shadow", 3)
        margin_v    = style.get("margin_v", 400)

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

        lines = [header]

        for seg in segments:
            words = seg.get("words", [])
            text = seg.get("text", "").strip()

            if not text:
                continue

            start = seg["start"]
            end = seg["end"]

            # Cap line length for readability (wrap at ~40 chars)
            wrapped_lines = self._wrap_text(text, max_chars=40)

            for line in wrapped_lines:
                dialogue = (
                    f"Dialogue: 0,{_seconds_to_ass(start)},{_seconds_to_ass(end)},"
                    f"Default,,0,0,0,,{{{self._fade_tag()}}}{self._escape_ass(line)}\n"
                )
                lines.append(dialogue)

                # Advance start proportionally for multi-line wraps
                if len(wrapped_lines) > 1:
                    dur = end - start
                    start += dur / len(wrapped_lines)

        return "".join(lines)

    @staticmethod
    def _fade_tag() -> str:
        """ASS fade-in/out: 150ms in, 100ms out."""
        return r"\fad(150,100)"

    @staticmethod
    def _escape_ass(text: str) -> str:
        """Escape special ASS characters."""
        return text.replace("{", "｛").replace("}", "｝")

    @staticmethod
    def _wrap_text(text: str, max_chars: int = 40) -> List[str]:
        """Wrap text into lines of at most max_chars characters."""
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
