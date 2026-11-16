from __future__ import annotations

import json
import re

from .asr import Segment
from .config import Config, PROJECT_ROOT
from .llm import chat

PROMPT = PROJECT_ROOT / "prompts" / "extract.zh.txt"


def _parse_json(text: str) -> list[dict]:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.S)
    if fenced:
        text = fenced.group(1).strip()
    start, end = text.find("["), text.rfind("]")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    return json.loads(text)


def extract_units(segments: list[Segment], cfg: Config) -> list[dict]:
    """Turn a transcript into discrete information units."""
    template = PROMPT.read_text(encoding="utf-8")
    body = "\n".join(seg.text for seg in segments)
    units: list[dict] = []

    # chunk long transcripts so the model never truncates silently
    for offset in range(0, len(body), 6000):
        part = body[offset:offset + 6000]
        prompt = template.replace("{{TEXT}}", part)
        answer = chat([{"role": "user", "content": prompt}], cfg,
                      temperature=0.0, max_tokens=4096)
        try:
            units.extend(_parse_json(answer))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"extract returned invalid JSON: {exc}") from exc
    return units
