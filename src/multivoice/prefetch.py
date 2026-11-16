from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path

from . import search
from .config import Config, PROJECT_ROOT
from .glossary import Glossary, DEFAULT_PATH
from .llm import chat

PROMPT = PROJECT_ROOT / "prompts" / "review_summary.zh.txt"
CACHE_PATH = Path(DEFAULT_PATH).with_name("review_cache.json")
TTL_DAYS = 7


def _read_cache() -> dict:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _write_cache(data: dict) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def cached(term: str) -> dict | None:
    entry = _read_cache().get(term)
    if not entry:
        return None
    try:
        age = (date.today() - datetime.fromisoformat(entry["at"]).date()).days
    except (KeyError, ValueError):
        return None
    return entry if age <= TTL_DAYS else None


def _summary(term: str, cfg: Config, zh: list[dict], en: list[dict]) -> tuple[str, str]:
    template = PROMPT.read_text(encoding="utf-8")
    prompt = (
        template.replace("{{TERM}}", term)
        .replace("{{ZH}}", search.format_results(zh) or "（无）")
        .replace("{{EN}}", search.format_results(en) or "（无）")
    )
    try:
        answer = chat([{"role": "user", "content": prompt}], cfg,
                      temperature=0.0, max_tokens=512)
        start, end = answer.find("{"), answer.rfind("}")
        data = json.loads(answer[start:end + 1])
        return data.get("zh", "").strip(), data.get("en", "").strip()
    except Exception:
        return "", ""


def build(term: str, cfg: Config) -> dict | None:
    """Search zh and en in parallel, then produce a synchronized bilingual summary."""
    with ThreadPoolExecutor(max_workers=2) as pool:
        zh_future = pool.submit(search.bing, term, 4, "zh")
        en_future = pool.submit(search.bing, term, 4, "en")
        zh = zh_future.result()
        en = en_future.result()

    if zh is None and en is None:
        return None  # network failure: keep the term, learn nothing

    zh = zh or []
    en = en or []
    if not zh and not en:
        return {"zh": [], "en": [], "summary_zh": "", "summary_en": "",
                "empty": True, "at": date.today().isoformat()}

    summary_zh, summary_en = _summary(term, cfg, zh, en)
    record = {
        "zh": [item["title"] for item in zh[:3]],
        "en": [item["title"] for item in en[:3]],
        "summary_zh": summary_zh,
        "summary_en": summary_en,
        "empty": False,
        "at": date.today().isoformat(),
    }
    data = _read_cache()
    data[term] = record
    _write_cache(data)
    return record


def pending_terms(glossary: Glossary) -> list[str]:
    return [item["term"] for item in glossary.pending]


def warm(glossary: Glossary, cfg: Config, limit: int = 6) -> int:
    """Fill the cache for terms that do not have a fresh entry yet."""
    done = 0
    for term in pending_terms(glossary):
        if done >= limit:
            break
        if cached(term) is not None:
            continue
        if build(term, cfg) is not None:
            done += 1
    return done
