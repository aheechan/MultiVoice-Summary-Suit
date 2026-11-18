"""Bilingual SRT export: short cues (13–26 chars) with per-cue timings."""
from __future__ import annotations

import re

from .config import Config
from .llm import chat

SENTENCE = re.compile(r"(?<=[。！？!?；;])")
PUNCT = set("，,。.！!？?；;：:、 ")
LO, HI = 13, 26


def _fmt(seconds: float) -> str:
    seconds = max(0.0, seconds)
    whole = int(seconds)
    millis = int(round((seconds - whole) * 1000))
    hours, rest = divmod(whole, 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def _chunk_zh(text: str) -> list[str]:
    """Split Chinese into 13–26 character pieces, preferring punctuation."""
    text = text.strip()
    pieces: list[str] = []
    current = ""
    for char in text:
        current += char
        if len(current) >= LO and char in PUNCT:
            pieces.append(current.strip())
            current = ""
        elif len(current) >= HI:
            pieces.append(current.strip())
            current = ""
    if current.strip():
        pieces.append(current.strip())
    return pieces


def _chunk_en(text: str) -> list[str]:
    """Split English into 13–26 character pieces on word boundaries."""
    words = text.split()
    pieces: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) <= HI:
            current = candidate
            continue
        if current:
            pieces.append(current)
        current = word
        while len(current) > HI:  # pathological single word
            pieces.append(current[:HI])
            current = current[HI:]
    if current:
        pieces.append(current)

    # Merge pieces that are too short into their neighbour.
    merged: list[str] = []
    for piece in pieces:
        if merged and len(piece) < LO:
            merged[-1] = f"{merged[-1]} {piece}".strip()
        else:
            merged.append(piece)
    return merged


def _chunk(text: str, english: bool) -> list[str]:
    return _chunk_en(text) if english else _chunk_zh(text)


def base_cues(segments) -> list[tuple[float, float, str]]:
    """Sentence-level cues straight from the ASR segments."""
    cues: list[tuple[float, float, str]] = []
    for segment in segments:
        text = (segment.text or "").strip()
        if not text:
            continue
        parts = [p.strip() for p in SENTENCE.split(text) if p.strip()]
        if not parts:
            continue
        total = sum(len(p) for p in parts) or 1
        cursor = float(segment.start)
        span = max(0.2, float(segment.end) - cursor)
        for part in parts:
            share = span * (len(part) / total)
            cues.append((cursor, cursor + share, part))
            cursor += share
    return cues


def refine(cues, english: bool) -> list[tuple[float, float, str]]:
    """Split every sentence cue into 13–26 char pieces, sharing its time span."""
    result: list[tuple[float, float, str]] = []
    for start, end, text in cues:
        pieces = _chunk(text, english)
        if not pieces:
            continue
        total = sum(len(p) for p in pieces) or 1
        span = max(0.2, end - start)
        cursor = start
        for piece in pieces:
            share = span * (len(piece) / total)
            result.append((cursor, cursor + share, piece))
            cursor += share
    return result


def to_srt(cues) -> str:
    return "\n".join(
        f"{index}\n{_fmt(start)} --> {_fmt(end)}\n{text}\n"
        for index, (start, end, text) in enumerate(cues, 1)
    )


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


def translate_lines(lines: list[str], cfg: Config, target: str) -> list[str]:
    result: list[str] = []
    for offset in range(0, len(lines), 20):
        batch = lines[offset:offset + 20]
        translated = _translate_batch(batch, cfg, target)
        if translated:
            result.extend(translated)
            continue
        for line in batch:  # keep alignment even if the batch call failed
            single = _translate_batch([line], cfg, target)
            result.append(single[0] if single else line)
    return result


def _merge_short(cues):
    """Merge under-13-character cues with their neighbour, up to the 26 limit."""
    merged = []
    for start, end, text in cues:
        if merged and len(text) < LO and len(merged[-1][2]) + len(text) <= HI:
            prev_start, _, prev_text = merged[-1]
            merged[-1] = (prev_start, end, prev_text + text)
        else:
            merged.append((start, end, text))
    return merged


def write_pair(out_dir, cues, cfg: Config, source_lang: str = "zh") -> None:
    """Write subtitle.zh.srt and subtitle.en.srt for either source language."""
    out_dir.mkdir(parents=True, exist_ok=True)
    english_source = source_lang.lower().startswith("en")

    if english_source:
        zh_sentences = translate_lines([cue[2] for cue in cues], cfg, "中文")
        zh_base = [(s, e, t) for (s, e, _), t in zip(cues, zh_sentences)]
        en_cues = refine(cues, english=True)
        zh_cues = _merge_short(refine(zh_base, english=False))
    else:
        en_sentences = translate_lines([cue[2] for cue in cues], cfg, "English")
        en_base = [(s, e, t) for (s, e, _), t in zip(cues, en_sentences)]
        zh_cues = _merge_short(refine(cues, english=False))
        en_cues = refine(en_base, english=True)

    (out_dir / "subtitle.zh.srt").write_text(to_srt(zh_cues), encoding="utf-8")
    (out_dir / "subtitle.en.srt").write_text(to_srt(en_cues), encoding="utf-8")
