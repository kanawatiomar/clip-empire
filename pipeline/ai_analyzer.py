"""AI-powered clip analysis — uses Whisper + Claude to find viral moments.

Pipeline:
  1. Whisper transcribes video → word-level timestamps
  2. Energy analysis finds candidate windows
  3. Claude scores each window's transcript + generates titles/hooks
  4. Returns enriched Segment objects with AI metadata

Usage:
    analyzer = AIAnalyzer()
    segments = analyzer.analyze(source, category)
"""

from __future__ import annotations

import os
import json
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from pipeline.schemas import Source, Segment
from pipeline.segment import (
    detect_and_score_segments,
    extract_audio_wav,
    WINDOW_SEC,
)


# ── Category keyword signals ──────────────────────────────────────────────────
# These boost the score when found in a segment's transcript.
# Add more as you learn what performs in each niche.

CATEGORY_SIGNALS: Dict[str, Dict[str, float]] = {
    "Finance": {
        # High-value triggers
        "i lost everything": 3.0,
        "turned $100": 2.5,
        "nobody talks about": 2.5,
        "biggest mistake": 2.0,
        "made me rich": 2.0,
        "this is illegal": 2.0,
        "they don't want you to know": 2.0,
        "i made $": 1.8,
        "passive income": 1.5,
        "going to zero": 2.0,
        "all in": 1.5,
        "hedge fund": 1.3,
        "insider": 1.5,
        "manipulation": 1.5,
        "recession": 1.3,
        "collapse": 1.8,
        "warning": 1.3,
        # Crypto specific
        "100x": 2.0,
        "rug pull": 2.0,
        "whale": 1.5,
        "liquidated": 2.0,
        "pump": 1.3,
        "rekt": 1.8,
    },
    "Business": {
        "fired me": 2.5,
        "quit my job": 2.0,
        "billion dollar": 2.0,
        "went bankrupt": 2.5,
        "startup failed": 2.0,
        "secret": 1.8,
        "rejected by": 1.5,
        "from zero": 1.5,
        "acquisition": 1.3,
        "lawsuit": 1.8,
    },
    "Tech/AI": {
        "ai is going to": 2.0,
        "replace": 1.5,
        "jailbreak": 2.5,
        "banned": 2.0,
        "leaked": 2.5,
        "hacked": 2.0,
        "open source": 1.3,
        "this changes everything": 2.0,
        "censored": 2.0,
    },
    "Fitness": {
        "lost 100 pounds": 3.0,
        "doctors were wrong": 2.5,
        "this destroyed my": 2.0,
        "secret exercise": 2.0,
        "stopped working out": 1.8,
        "transformation": 1.5,
        "gains": 1.3,
        "natty": 1.5,
        "steroids": 2.0,
    },
    "True Crime": {
        "was never caught": 2.5,
        "confessed": 2.0,
        "they found": 1.8,
        "disappeared": 1.8,
        "cover up": 2.0,
        "evidence": 1.3,
        "convicted": 1.5,
        "escaped": 2.0,
    },
}

# Universal high-value phrases (any category)
UNIVERSAL_SIGNALS: Dict[str, float] = {
    "wait what": 2.0,
    "no way": 1.8,
    "i can't believe": 1.8,
    "this is insane": 2.0,
    "you won't believe": 2.0,
    "plot twist": 2.5,
    "breaking news": 1.5,
    "exclusive": 1.5,
    "shocking": 1.5,
    "exposed": 2.0,
    "controversial": 1.5,
    "unpopular opinion": 1.8,
    "they lied": 2.0,
    "the truth is": 1.5,
    "actually": 1.0,
}


# ── Whisper transcription ─────────────────────────────────────────────────────

def transcribe_video(
    video_path: str,
    model: str = "base",
    language: str = "en",
) -> Optional[Dict[str, Any]]:
    """Run Whisper on a video file. Returns dict with 'text', 'segments', 'words'.

    Each segment has: start, end, text
    Each word has: start, end, word
    """
    try:
        import whisper
    except ImportError:
        print("[ai_analyzer] Whisper not installed. Run: pip install openai-whisper")
        return None

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        wav_path = tmp.name

    try:
        if not extract_audio_wav(video_path, wav_path):
            return None

        print(f"[ai_analyzer] Transcribing with Whisper ({model})...")
        model_obj = whisper.load_model(model)
        result = model_obj.transcribe(
            wav_path,
            language=language,
            word_timestamps=True,
            verbose=False,
        )

        # Flatten word-level timestamps
        words = []
        for seg in result.get("segments", []):
            for w in seg.get("words", []):
                words.append({
                    "word": w["word"].strip(),
                    "start": w["start"],
                    "end": w["end"],
                })

        return {
            "text": result["text"],
            "segments": result["segments"],
            "words": words,
        }
    finally:
        try:
            os.unlink(wav_path)
        except Exception:
            pass


def get_transcript_window(
    words: List[Dict],
    start_s: float,
    end_s: float,
) -> str:
    """Get transcript text for a time window."""
    window_words = [
        w["word"] for w in words
        if start_s <= w["start"] <= end_s
    ]
    return " ".join(window_words).strip()


def compute_speech_density(words: List[Dict], start_s: float, end_s: float) -> float:
    """Words per second in a time window. Higher = more active speech."""
    duration = end_s - start_s
    if duration <= 0:
        return 0.0
    count = sum(1 for w in words if start_s <= w["start"] <= end_s)
    return count / duration


# ── Keyword scoring ───────────────────────────────────────────────────────────

def score_transcript_keywords(text: str, category: str) -> float:
    """Score a transcript snippet based on category signals + universal signals.

    Returns a bonus score (add to energy score).
    """
    text_lower = text.lower()
    bonus = 0.0

    # Universal signals
    for phrase, weight in UNIVERSAL_SIGNALS.items():
        if phrase in text_lower:
            bonus += weight

    # Category-specific signals
    cat_signals = CATEGORY_SIGNALS.get(category, {})
    for phrase, weight in cat_signals.items():
        if phrase in text_lower:
            bonus += weight

    return bonus


# ── Claude AI analysis ────────────────────────────────────────────────────────

def analyze_with_claude(
    transcript_window: str,
    category: str,
    duration_s: float,
    api_key: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Ask Claude to analyze a transcript window and generate metadata.

    Returns dict with:
        viral_score: 0-10 float
        reason: why this is or isn't viral
        hook: best opening sentence (first 3 seconds)
        titles: list of 3 title options
        thumbnail_moment: description of best thumbnail frame
    """
    if not transcript_window.strip():
        return None

    key = api_key or os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        print("[ai_analyzer] No Anthropic API key found, skipping Claude analysis")
        return None

    try:
        import anthropic
    except ImportError:
        print("[ai_analyzer] anthropic package not installed. Run: pip install anthropic")
        return None

    prompt = f"""You are a viral short-form video expert for YouTube Shorts and TikTok.

Category: {category}
Clip duration: {duration_s:.0f} seconds
Transcript:
\"\"\"
{transcript_window[:2000]}
\"\"\"

Analyze this clip transcript and respond with ONLY valid JSON (no markdown):
{{
  "viral_score": <0-10 float, how viral this clip could be>,
  "reason": "<1-2 sentences why it is or isn't viral>",
  "hook": "<best 1 sentence to use as opening hook (first 3 seconds)>",
  "titles": [
    "<title option 1: curiosity gap style>",
    "<title option 2: shocking/bold claim>",
    "<title option 3: how-to or value-based>"
  ],
  "thumbnail_moment": "<describe the best visual moment for a thumbnail>",
  "best_quote": "<the single most quotable/shareable line>"
}}"""

    try:
        client = anthropic.Anthropic(api_key=key)
        response = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=500,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as e:
        print(f"[ai_analyzer] Claude analysis failed: {e}")
        return None


# ── Main analyzer ─────────────────────────────────────────────────────────────

class AIAnalyzer:
    """Full AI-powered segment analyzer.

    Combines:
    - Energy-based segment detection (fast, no ML)
    - Whisper speech density scoring
    - Keyword signal matching
    - Claude viral scoring + title generation
    """

    def __init__(
        self,
        whisper_model: str = "base",
        use_claude: bool = True,
        api_key: Optional[str] = None,
    ):
        self.whisper_model = whisper_model
        self.use_claude = use_claude
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")

    def analyze(
        self,
        source: Source,
        category: str,
        top_n: int = 5,
    ) -> List[Segment]:
        """Full analysis pipeline. Returns enriched segments sorted by final score."""

        video_path = source.download_path
        if not video_path or not os.path.exists(video_path):
            print(f"[ai_analyzer] Video not found: {video_path}")
            return []

        print(f"\n[ai_analyzer] Starting analysis: {os.path.basename(video_path)}")
        print(f"[ai_analyzer] Category: {category}")

        # Step 1: Energy-based candidate detection
        print("[ai_analyzer] Step 1/3: Energy analysis...")
        energy_segments = detect_and_score_segments(source, category, top_n=top_n * 2)

        if not energy_segments:
            return []

        # Step 2: Whisper transcription
        print("[ai_analyzer] Step 2/3: Transcribing...")
        transcript_data = transcribe_video(video_path, model=self.whisper_model)
        words = transcript_data["words"] if transcript_data else []

        # Step 3: Enrich each segment
        print("[ai_analyzer] Step 3/3: AI scoring...")
        enriched = []

        for seg in energy_segments:
            start_s = seg.start_ms / 1000
            end_s = seg.end_ms / 1000
            duration_s = end_s - start_s

            # Get transcript for this window
            transcript_window = get_transcript_window(words, start_s, end_s) if words else ""

            # Speech density bonus (0-3 wps is normal, 3+ is fast/energetic)
            speech_density = compute_speech_density(words, start_s, end_s) if words else 0.0
            density_bonus = min(speech_density / 3.0, 1.0) * 0.3  # max 0.3 bonus

            # Keyword signal bonus
            keyword_bonus = 0.0
            if transcript_window:
                raw_bonus = score_transcript_keywords(transcript_window, category)
                keyword_bonus = min(raw_bonus / 10.0, 1.0)  # normalize to 0-1

            # Claude analysis
            ai_meta = None
            viral_score_normalized = 0.0
            if self.use_claude and transcript_window and len(transcript_window) > 50:
                ai_meta = analyze_with_claude(
                    transcript_window,
                    category,
                    duration_s,
                    self.api_key,
                )
                if ai_meta:
                    viral_score_normalized = ai_meta.get("viral_score", 5.0) / 10.0

            # Final composite score
            # Weights: energy 30% | speech density 15% | keywords 20% | AI viral score 35%
            if ai_meta:
                final_score = (
                    seg.overall_score * 0.30 +
                    density_bonus * 0.15 +
                    keyword_bonus * 0.20 +
                    viral_score_normalized * 0.35
                )
            else:
                # No Claude — redistribute weight
                final_score = (
                    seg.overall_score * 0.50 +
                    density_bonus * 0.20 +
                    keyword_bonus * 0.30
                )

            # Build enriched metadata
            ai_metadata = {
                "transcript": transcript_window,
                "speech_density_wps": round(speech_density, 2),
                "keyword_bonus": round(keyword_bonus, 3),
                "energy_score": seg.overall_score,
            }
            if ai_meta:
                ai_metadata.update({
                    "viral_score": ai_meta.get("viral_score"),
                    "viral_reason": ai_meta.get("reason"),
                    "hook": ai_meta.get("hook"),
                    "titles": ai_meta.get("titles", []),
                    "thumbnail_moment": ai_meta.get("thumbnail_moment"),
                    "best_quote": ai_meta.get("best_quote"),
                })

            # Create enriched segment
            enriched_seg = Segment(
                segment_id=seg.segment_id,
                source_id=seg.source_id,
                start_ms=seg.start_ms,
                end_ms=seg.end_ms,
                hook_score=round(min(final_score + keyword_bonus * 0.2, 1.0), 3),
                story_score=round(density_bonus + seg.story_score * 0.5, 3),
                novelty_score=round(keyword_bonus, 3),
                category_fit_score=round(viral_score_normalized if ai_meta else seg.category_fit_score, 3),
                overall_score=round(final_score, 3),
                created_at=seg.created_at,
                metadata=ai_metadata,
            )
            enriched.append(enriched_seg)

        # Sort by final score, return top N
        enriched.sort(key=lambda s: s.overall_score, reverse=True)
        top = enriched[:top_n]

        print(f"\n[ai_analyzer] Top {len(top)} segments:")
        for i, seg in enumerate(top, 1):
            meta = seg.metadata or {}
            titles = meta.get("titles", [])
            title_preview = titles[0] if titles else "(no title)"
            print(f"  #{i} [{seg.start_ms/1000:.1f}s→{seg.end_ms/1000:.1f}s] "
                  f"score={seg.overall_score:.3f} | {title_preview[:60]}")

        return top


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python -m pipeline.ai_analyzer <video_path> <category>")
        print("Categories: Finance, Business, Tech/AI, Fitness, True Crime")
        sys.exit(1)

    from pipeline.schemas import Source
    import uuid

    video = sys.argv[1]
    category = sys.argv[2]

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

    analyzer = AIAnalyzer(whisper_model="base", use_claude=True)
    segments = analyzer.analyze(dummy_source, category, top_n=3)

    print(f"\n{'='*60}")
    print(f"RESULTS: {len(segments)} segments")
    print('='*60)
    for i, seg in enumerate(segments, 1):
        meta = seg.metadata or {}
        print(f"\n#{i} [{seg.start_ms/1000:.0f}s → {seg.end_ms/1000:.0f}s] Score: {seg.overall_score:.3f}")
        if meta.get("titles"):
            print("  Titles:")
            for t in meta["titles"]:
                print(f"    - {t}")
        if meta.get("hook"):
            print(f"  Hook: {meta['hook']}")
        if meta.get("best_quote"):
            print(f"  Quote: {meta['best_quote']}")
        if meta.get("viral_reason"):
            print(f"  Why viral: {meta['viral_reason']}")
