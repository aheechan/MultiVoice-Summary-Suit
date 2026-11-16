from __future__ import annotations

import json

from .asr import Segment
from .config import Config, PROJECT_ROOT
from .llm import chat


def _prompt(name: str) -> str:
    return (PROJECT_ROOT / "prompts" / name).read_text(encoding="utf-8")


def clean_script(segments: list[Segment], cfg: Config) -> str:
    body = "\n".join(seg.text for seg in segments)
    prompt = _prompt("clean.zh.txt").replace("{{TEXT}}", body)
    return chat([{"role": "user", "content": prompt}], cfg, max_tokens=4096)


def report(units: list[dict], cfg: Config) -> str:
    payload = json.dumps(units, ensure_ascii=False, indent=2)
    prompt = _prompt("report.zh.txt").replace("{{UNITS}}", payload)
    return chat([{"role": "user", "content": prompt}], cfg, max_tokens=6000)


def brief(units: list[dict], cfg: Config) -> str:
    payload = json.dumps(units, ensure_ascii=False, indent=2)
    prompt = _prompt("brief.zh.txt").replace("{{UNITS}}", payload)
    return chat([{"role": "user", "content": prompt}], cfg, max_tokens=2000)
