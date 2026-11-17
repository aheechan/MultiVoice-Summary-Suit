from __future__ import annotations

import json
import re

from .asr import Segment
from .config import Config, PROJECT_ROOT
from .llm import chat

PROMPT = PROJECT_ROOT / "prompts" / "extract.zh.txt"


def _objects_from_text(text: str) -> list[dict]:
    """Parse JSONL output, still accepting a plain JSON array."""
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()

    if text.startswith("["):
        start, end = text.find("["), text.rfind("]")
        if start >= 0 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass

    units: list[dict] = []
    decoder = json.JSONDecoder()
    for line in text.splitlines():
        line = line.strip().rstrip(",")
        if not line.startswith("{"):
            continue
        try:
            value, _ = decoder.raw_decode(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            units.append(value)
    return units


def _fallback_units(segments: list[Segment]) -> list[dict]:
    """Never fail a job: degrade to paragraph-level units."""
    units: list[dict] = []
    for index, segment in enumerate(segments, 1):
        text = segment.text.strip()
        if not text:
            continue
        units.append({
            "id": f"k{index}",
            "type": "claim",
            "title": text[:24],
            "detail": text,
            "evidence": [text],
            "confidence": "low",
        })
    return units


def extract_units(segments: list[Segment], cfg: Config) -> list[dict]:
    """Turn a transcript into discrete information units."""
    template = PROMPT.read_text(encoding="utf-8")
    body = "\n".join(seg.text for seg in segments)
    units: list[dict] = []

    for offset in range(0, len(body), 3000):
        part = body[offset:offset + 3000]
        prompt = template.replace("{{TEXT}}", part)
        try:
            answer = chat([{"role": "user", "content": prompt}], cfg,
                          temperature=0.0, max_tokens=4096)
        except Exception:
            continue
        units.extend(_objects_from_text(answer))

    if not units:
        units = _fallback_units(segments)
    return units
