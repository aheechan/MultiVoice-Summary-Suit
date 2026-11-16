from __future__ import annotations

import json

from .asr import Segment
from .config import Config, PROJECT_ROOT
from .llm import chat


def _prompt(name: str) -> str:
    return (PROJECT_ROOT / "prompts" / name).read_text(encoding="utf-8")


def _guard(text: str, source: str, ratio: float, floor: int = 60) -> str:
    """Reject output that grew far beyond its source: that is fabrication, not editing."""
    if not text.strip():
        return source.strip()
    if len(text) > max(floor, int(len(source) * ratio)):
        return source.strip()
    return text


def clean_script(segments: list[Segment], cfg: Config) -> str:
    body = "\n".join(seg.text for seg in segments)
    prompt = _prompt("clean.zh.txt").replace("{{TEXT}}", body)
    answer = chat([{"role": "user", "content": prompt}], cfg, max_tokens=4096)
    return _guard(answer, body, ratio=1.3)


def report(units: list[dict], cfg: Config, transcript: str = "") -> str:
    payload = json.dumps(units, ensure_ascii=False, indent=2)
    prompt = _prompt("report.zh.txt").replace("{{UNITS}}", payload)
    answer = chat([{"role": "user", "content": prompt}], cfg, max_tokens=6000)
    return _guard(answer, transcript or payload, ratio=1.6)


def brief(units: list[dict], cfg: Config, transcript: str = "") -> str:
    payload = json.dumps(units, ensure_ascii=False, indent=2)
    prompt = _prompt("brief.zh.txt").replace("{{UNITS}}", payload)
    answer = chat([{"role": "user", "content": prompt}], cfg, max_tokens=2000)
    return _guard(answer, transcript or payload, ratio=0.8)
