from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request

USER_AGENT = "MultiVoice-Summary-Suit/0.1 (research prototype)"
API = "https://{lang}.wikipedia.org/w/api.php"
TAG_RE = re.compile(r"<[^>]+>")


def _get(url: str, timeout: float = 12.0) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def search(term: str, lang: str = "zh", limit: int = 3) -> list[dict]:
    """Return [{title, snippet}] for a term; empty list when nothing matches."""
    query = urllib.parse.urlencode({
        "action": "query",
        "list": "search",
        "srsearch": term,
        "format": "json",
        "srlimit": limit,
        "utf8": 1,
    })
    try:
        data = _get(f"{API.format(lang=lang)}?{query}")
    except Exception:
        return []
    items = data.get("query", {}).get("search", [])
    return [
        {"title": item["title"], "snippet": TAG_RE.sub("", item.get("snippet", ""))}
        for item in items
    ]


def evidence_for(terms: list[str], langs: list[str]) -> list[dict]:
    """Collect encyclopedia snippets for each candidate term."""
    collected: list[dict] = []
    for term in terms:
        term = term.strip()
        if not term:
            continue
        for lang in langs:
            hits = search(term, lang)
            if hits:
                collected.append({
                    "term": term,
                    "lang": lang,
                    "hits": hits,
                })
                break
    return collected


def format_evidence(items: list[dict], limit: int = 2) -> str:
    lines: list[str] = []
    for item in items:
        lines.append(f"[{item['term']}]")
        for hit in item["hits"][:limit]:
            lines.append(f"- {hit['title']}: {hit['snippet'][:220]}")
    return "\n".join(lines) if lines else "（无检索结果）"
