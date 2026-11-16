from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Span:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


SILENCE_RE = re.compile(r"silence_(start|end):\s*(-?[\d.]+)")


def detect_speech_spans(
    audio: Path,
    ffmpeg: str = "ffmpeg",
    noise_db: float = -32.0,
    min_silence: float = 0.45,
) -> list[Span]:
    """Return speech spans using ffmpeg's silencedetect (no extra dependencies)."""
    cmd = [
        ffmpeg, "-hide_banner", "-i", str(audio),
        "-af", f"silencedetect=noise={noise_db}dB:d={min_silence}",
        "-f", "null", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, errors="ignore")
    text = proc.stderr

    events: list[tuple[str, float]] = []
    for kind, value in SILENCE_RE.findall(text):
        events.append((kind, float(value)))

    total = _duration(audio, ffmpeg)
    if not events:
        return [Span(0.0, total)] if total > 0 else []

    spans: list[Span] = []
    cursor = 0.0
    for kind, value in events:
        if kind == "start" and value > cursor:
            spans.append(Span(cursor, value))
            cursor = value
        elif kind == "end":
            cursor = max(cursor, value)

    if cursor < total:
        spans.append(Span(cursor, total))

    return [s for s in spans if s.duration > 0.05]


def _duration(audio: Path, ffmpeg: str) -> float:
    probe = ffmpeg.replace("ffmpeg", "ffprobe")
    proc = subprocess.run(
        [probe, "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(audio)],
        capture_output=True, text=True,
    )
    try:
        return float(proc.stdout.strip())
    except ValueError:
        return 0.0


def merge_spans(
    spans: list[Span],
    max_seconds: float = 30.0,
    min_seconds: float = 1.0,
    gap: float = 0.35,
) -> list[Span]:
    """Merge adjacent speech spans into chunks that fit the VRAM budget.

    A 16 GB card handles a 0.6B ASR model plus ~30 s of audio comfortably;
    longer chunks only add latency and peak memory, never accuracy.
    """
    if not spans:
        return []

    merged: list[Span] = []
    current = Span(spans[0].start, spans[0].end)
    for span in spans[1:]:
        grows = span.end - current.start
        if grows <= max_seconds and span.start - current.end <= gap:
            current = Span(current.start, span.end)
        else:
            merged.append(current)
            current = Span(span.start, span.end)
    merged.append(current)

    # absorb tiny leftovers into the previous chunk
    cleaned: list[Span] = []
    for span in merged:
        if cleaned and span.duration < min_seconds:
            prev = cleaned[-1]
            cleaned[-1] = Span(prev.start, span.end)
        else:
            cleaned.append(span)
    return cleaned


def cut(audio: Path, span: Span, target: Path, ffmpeg: str = "ffmpeg") -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg, "-y", "-ss", f"{span.start:.3f}", "-to", f"{span.end:.3f}",
        "-i", str(audio), "-ac", "1", "-ar", "16000",
        "-c:a", "pcm_s16le", str(target),
    ]
    subprocess.run(cmd, check=True, capture_output=True)
    return target
