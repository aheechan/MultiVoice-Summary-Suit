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
        return ""
    if len(text) > max(floor, int(len(source) * ratio)):
        return ""
    return text


def _fallback_brief(units: list[dict]) -> str:
    lines = ["**要点**", ""]
    for unit in units[:8]:
        title = (unit.get("title") or unit.get("detail") or "").strip()
        if title:
            lines.append(f"- {title[:60]}")
    return "\n".join(lines)


def _fallback_report(units: list[dict]) -> str:
    blocks = ["# 知识点清单", ""]
    for index, unit in enumerate(units, 1):
        blocks.append(f"## {index}. {(unit.get('title') or '未命名').strip()}")
        detail = (unit.get("detail") or "").strip()
        if detail:
            blocks.append(detail)
        evidence = unit.get("evidence") or []
        if evidence:
            blocks.append("")
            blocks.append("原文依据：" + "；".join(str(e) for e in evidence[:2]))
        blocks.append("")
    return "\n".join(blocks)


def clean_script(segments: list[Segment], cfg: Config) -> str:
    body = "\n".join(seg.text for seg in segments)
    prompt = _prompt("clean.zh.txt").replace("{{TEXT}}", body)
    answer = chat([{"role": "user", "content": prompt}], cfg, max_tokens=4096)
    return _guard(answer, body, ratio=1.3) or body.strip()


def report(units: list[dict], cfg: Config, transcript: str = "") -> str:
    payload = json.dumps(units, ensure_ascii=False, indent=2)
    prompt = _prompt("report.zh.txt").replace("{{UNITS}}", payload)
    answer = chat([{"role": "user", "content": prompt}], cfg, max_tokens=6000)
    return _guard(answer, transcript or payload, ratio=1.6) or _fallback_report(units)


def brief(units: list[dict], cfg: Config, transcript: str = "") -> str:
    payload = json.dumps(units, ensure_ascii=False, indent=2)
    prompt = _prompt("brief.zh.txt").replace("{{UNITS}}", payload)
    answer = chat([{"role": "user", "content": prompt}], cfg, max_tokens=2000)
    return _guard(answer, transcript or payload, ratio=1.0) or _fallback_brief(units)


def expand_draft(segments: list[Segment], units: list[dict], cfg: Config) -> str:
    """Rewrite the script with background added for non-common-sense points."""
    body = "\n".join(seg.text for seg in segments)
    payload = json.dumps(units, ensure_ascii=False, indent=2)
    prompt = (
        _prompt("expand.zh.txt")
        .replace("{{TEXT}}", body)
        .replace("{{UNITS}}", payload)
    )
    answer = chat([{"role": "user", "content": prompt}], cfg, max_tokens=8000)
    return _guard(answer, body, ratio=2.08) or body.strip()
