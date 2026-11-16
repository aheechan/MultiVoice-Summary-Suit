from __future__ import annotations

import csv
from pathlib import Path

from .asr import Segment
from .config import Config, PROJECT_ROOT
from .llm import chat

PROMPT = PROJECT_ROOT / "prompts" / "correct.zh.txt"


def load_glossary(path: Path | None = None) -> str:
    path = path or PROJECT_ROOT / "configs" / "glossary.csv"
    if not path.exists():
        return "（无）"
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            if row.get("term"):
                rows.append(f"{row['term']}（{row.get('note', '')}）")
    return "、".join(rows) if rows else "（无）"


def _chunks(segments: list[Segment], limit: int = 1200) -> list[list[Segment]]:
    chunks, current, size = [], [], 0
    for seg in segments:
        if size + len(seg.text) > limit and current:
            chunks.append(current)
            current, size = [], 0
        current.append(seg)
        size += len(seg.text)
    if current:
        chunks.append(current)
    return chunks


def correct_segments(segments: list[Segment], cfg: Config) -> list[Segment]:
    """Correct ASR errors paragraph by paragraph. Never rewrites content."""
    template = PROMPT.read_text(encoding="utf-8")
    glossary = load_glossary()

    corrected: list[Segment] = []
    for group in _chunks(segments):
        source = "\n".join(seg.text for seg in group)
        prompt = template.replace("{{GLOSSARY}}", glossary).replace("{{TEXT}}", source)
        answer = chat([{"role": "user", "content": prompt}], cfg, temperature=0.0,
                      max_tokens=max(512, len(source)))
        lines = [line.strip() for line in answer.splitlines() if line.strip()]
        for seg, line in zip(group, lines):
            corrected.append(Segment(seg.index, seg.start, seg.end, line, seg.lang))
        # keep any segment the model dropped, untouched
        for seg in group[len(lines):]:
            corrected.append(seg)
    return corrected
