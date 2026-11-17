"""Multi-source evidence gathering for a term (Wikipedia + Bing, zh/en)."""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from . import search

USER_AGENT = "MultiVoice-Summary-Suit/0.1 (local research tool)"


def _get_json(url: str, timeout: float = 12.0) -> dict | None:
    for attempt in range(2):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8", errors="ignore"))
        except Exception:
            if attempt == 0:
                continue
    return None


def _page_extract(lang: str, title: str) -> dict | None:
    variant = "zh-cn" if lang.startswith("zh") else lang
    url = (
        f"https://{lang}.wikipedia.org/w/api.php?action=query&format=json"
        f"&prop=extracts&exintro=1&explaintext=1&redirects=1&variant={variant}"
        f"&titles={urllib.parse.quote(title)}"
    )
    data = _get_json(url)
    try:
        pages = data["query"]["pages"]
        page = next(iter(pages.values()))
    except (KeyError, TypeError, StopIteration):
        return None
    extract = (page.get("extract") or "").strip()
    if not extract or "missing" in page:
        return None
    return {"title": page.get("title", title), "extract": extract}


def _search_title(lang: str, term: str) -> str | None:
    url = (
        f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&format=json"
        f"&srlimit=1&srsearch={urllib.parse.quote(term)}"
    )
    data = _get_json(url)
    try:
        return data["query"]["search"][0]["title"]
    except (KeyError, IndexError, TypeError):
        return None


def wikipedia(term: str, lang: str = "zh") -> dict | None:
    """Wikipedia intro extract, with zh-CN conversion and a search fallback."""
    page = _page_extract(lang, term)
    if page is None:
        title = _search_title(lang, term)
        if not title:
            return None
        page = _page_extract(lang, title)
        if page is None:
            return None

    title = page["title"]
    head = page["extract"][:30]
    normalized_title = title.replace(" ", "").strip()
    normalized_term = term.replace(" ", "").strip()
    return {
        "source": f"Wikipedia ({lang})",
        "title": title,
        "snippet": page["extract"],
        "url": f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(title)}",
        # Titles differ between traditional and simplified Chinese, so also
        # accept a page whose opening sentence names the term.
        "exact": normalized_title == normalized_term
                 or term in head
                 or title in head,
    }


def collect(term: str) -> list[dict]:
    """Gather evidence from Wikipedia (zh/en) and Bing (zh/en) concurrently."""
    jobs = [
        (wikipedia, (term, "zh")),
        (wikipedia, (term, "en")),
        (search.bing, (term, 4, "zh")),
        (search.bing, (term, 4, "en")),
    ]
    evidence: list[dict] = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = [pool.submit(fn, *args) for fn, args in jobs]
        results = []
        for future in futures:
            try:
                results.append(future.result())
            except Exception:
                results.append(None)

    for item in results[:2]:
        if item:
            evidence.append(item)

    for items, lang in ((results[2], "zh"), (results[3], "en")):
        if not items:
            continue
        for hit in items[:2]:
            evidence.append({
                "source": f"Bing ({lang})",
                "title": hit["title"],
                "snippet": hit["snippet"],
                "url": hit["url"],
                "exact": term in hit["title"],
            })
    return evidence


def has_exact(evidence: list[dict]) -> dict | None:
    """Return the first source whose title matches the term exactly."""
    for item in evidence:
        if item.get("exact"):
            return item
    return None
