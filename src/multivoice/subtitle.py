"""Sentence-level subtitle export (zh/en) with per-cue timings."""
from __future__ import annotations

import re

from .config import Config
from .llm import chat

SPLIT = re.compile(r"(?<=[。！？!?；;])")


def cues_from_segments(segments) -> list[tuple[float, float, str]]:
    """Split each ASR segment into sentences and share its time span by length."""
    cues: list[tuple[float, float, str]] = []
    for segment in segments:
        text = (segment.text or "").strip()
        if not text:
            continue
        parts = [p.strip() for p in SPLIT.split(text) if p.strip()]
        if not parts:
            continue
        total = sum(len(p) for p in parts) or 1
        start = float(segment.start)
        span = max(0.2, float(segment.end) - start)
        cursor = start
        for part in parts:
            share = span * (len(part) / total)
            cues.append((cursor, cursor + share, part))
            cursor += share
    return cues


def _fmt(seconds: float) -> str:
    seconds = max(0.0, seconds)
    whole = int(seconds)
    millis = int(round((seconds - whole) * 1000))
    hours, rest = divmod(whole, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def to_srt(cues: list[tuple[float, float, str]]) -> str:
    blocks = []
    for index, (start, end, text) in enumerate(cues, 1):
        blocks.append(f"{index}\n{_fmt(start)} --> {_fmt(end)}\n{text}\n")
    return "\n".join(blocks)


def _translate_batch(lines: list[str], cfg: Config, target: str) -> list[str]:
    body = "\n".join(lines)
    prompt = (
        f"把下面每一行翻译成{target}。必须逐行对应：输入几行，输出几行，"
        "不要合并、不要增删、不要编号、不要解释。\n\n" + body
    )
    answer = chat([{"role": "user", "content": prompt}], cfg,
                  temperature=0.0, max_tokens=4000)
    out = [line.strip() for line in answer.strip().splitlines() if line.strip()]
    return out if len(out) == len(lines) else []


def translate_cues(cues: list[tuple[float, float, str]], cfg: Config,
                   target: str = "English") -> list[str]:
    texts = [cue[2] for cue in cues]
    result: list[str] = []
    for offset in range(0, len(texts), 20):
        batch = texts[offset:offset + 20]
        translated = _translate_batch(batch, cfg, target)
        if translated:
            result.extend(translated)
            continue
        # Fallback: translate line by line so timing stays aligned.
        for line in batch:
            single = _translate_batch([line], cfg, target)
            result.append(single[0] if single else line)
    return result


def write_pair(out_dir, cues, cfg: Config) -> None:
    """Write subtitle.zh.srt and subtitle.en.srt next to the other text exports."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "subtitle.zh.srt").write_text(to_srt(cues), encoding="utf-8")
    english = translate_cues(cues, cfg)
    en_cues = [(start, end, text) for (start, end, _), text in zip(cues, english)]
    (out_dir / "subtitle.en.srt").write_text(to_srt(en_cues), encoding="utf-8")
