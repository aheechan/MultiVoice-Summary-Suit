"""Multi-source evidence gathering for a term (Wikipedia + Baidu + Bing)."""
from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from html import unescape
from urllib.parse import unquote

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


def _get_text(url: str, timeout: float = 12.0) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _relevant(term: str, title: str, snippet: str) -> bool:
    """A source only counts when the term actually appears in it."""
    return term in title or term in snippet


# ---------------------------------------------------------------- Wikipedia
def _page_extract(lang: str, title: str) -> dict | None:
    variant = "zh-cn" if lang.startswith("zh") else lang
    url = (
        f"https://{lang}.wikipedia.org/w/api.php?action=query&format=json"
        f"&prop=extracts&exintro=1&explaintext=1&redirects=1&variant={variant}"
        f"&titles={urllib.parse.quote(title)}"
    )
    data = _get_json(url)
    try:
        page = next(iter(data["query"]["pages"].values()))
    except (KeyError, TypeError, StopIteration):
        return None
    extract = (page.get("extract") or "").strip()
    if not extract or "missing" in page:
        return None
    return {"title": page.get("title", title), "extract": extract}


def wikipedia(term: str, lang: str = "zh") -> dict | None:
    page = _page_extract(lang, term)
    if page is None:
        data = _get_json(
            f"https://{lang}.wikipedia.org/w/api.php?action=query&list=search&format=json"
            f"&srlimit=1&srsearch={urllib.parse.quote(term)}"
        )
        try:
            title = data["query"]["search"][0]["title"]
        except (KeyError, IndexError, TypeError):
            return None
        page = _page_extract(lang, title)
        if page is None:
            return None

    title, extract = page["title"], page["extract"]
    head = extract[:40]
    normalized = title.replace(" ", "").strip()
    if not (term in title or term in head or normalized == term.replace(" ", "")):
        return None
    return {
        "source": f"Wikipedia ({lang})",
        "title": title,
        "snippet": extract[:600],
        "url": f"https://{lang}.wikipedia.org/wiki/{urllib.parse.quote(title)}",
        "exact": term in title or term in head,
    }


# ---------------------------------------------------------------- Baidu Baike
def baike(term: str) -> dict | None:
    """Baidu Baike lemma card API, falling back to the lemma page."""
    api = (
        "https://baike.baidu.com/api/openapi/BaikeLemmaCardApi"
        f"?scope=103&format=json&appid=379020&bk_length=600&bk_key={urllib.parse.quote(term)}"
    )
    data = _get_json(api)
    if data:
        result = data.get("result") or {}
        abstract = (result.get("abstract") or "").strip()
        title = result.get("lemmaTitle") or term
        if abstract and _relevant(term, title, abstract):
            return {
                "source": "Baidu Baike",
                "title": title,
                "snippet": abstract[:600],
                "url": f"https://baike.baidu.com/item/{urllib.parse.quote(title)}",
                "exact": term in title,
            }

    html = _get_text(f"https://baike.baidu.com/item/{urllib.parse.quote(term)}")
    if not html:
        return None
    start = html.find('class="lemma-summary"')
    if start < 0:
        return None
    chunk = html[start:start + 2500]
    text = unescape("".join(ch for ch in chunk if ch not in "<>"))
    text = " ".join(text.split())
    if not _relevant(term, term, text):
        return None
    return {
        "source": "Baidu Baike",
        "title": term,
        "snippet": text[:600],
        "url": f"https://baike.baidu.com/item/{urllib.parse.quote(term)}",
        "exact": True,
    }


# ---------------------------------------------------------------- Bing
def _best_bing(term: str, hits: list[dict] | None) -> dict | None:
    if not hits:
        return None
    for hit in hits:
        if not _relevant(term, hit["title"], hit["snippet"]):
            continue
        return {
            "source": "Bing (zh)",
            "title": hit["title"],
            "snippet": hit["snippet"][:600],
            "url": hit["url"],
            "exact": term in hit["title"],
        }
    return None


# ---------------------------------------------------------------- Google
def google(term: str, lang: str = "zh") -> dict | None:
    """Google Custom Search JSON API (needs GOOGLE_API_KEY + GOOGLE_CX)."""
    import os

    key = os.environ.get("GOOGLE_API_KEY", "")
    cx = os.environ.get("GOOGLE_CX", "")
    if not key or not cx:
        return None
    params = urllib.parse.urlencode({
        "key": key, "cx": cx, "q": term,
        "num": "5", "hl": "zh-CN" if lang == "zh" else "en",
    })
    data = _get_json(f"https://www.googleapis.com/customsearch/v1?{params}")
    try:
        items = data["items"]
    except (KeyError, TypeError):
        return None
    for hit in items:
        title = hit.get("title", "")
        snippet = hit.get("snippet", "")
        if not _relevant(term, title, snippet):
            continue
        return {
            "source": f"Google ({lang})",
            "title": title[:120],
            "snippet": snippet[:600],
            "url": hit.get("link", ""),
            "exact": term in title,
        }
    return None


def duckduckgo(term: str, lang: str = "zh") -> dict | None:
    """No-key HTML endpoint, used when Google has no API credentials."""
    params = urllib.parse.urlencode({"q": term, "kl": "cn-zh" if lang == "zh" else "us-en"})
    html = _get_text(f"https://html.duckduckgo.com/html/?{params}", timeout=12)
    if not html:
        return None
    pattern = re.compile(
        r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>.*?'
        r'class="result__snippet"[^>]*>(.*?)</a>',
        re.S,
    )
    for href, inner, snippet_html in pattern.findall(html):
        title = _strip_tags(inner)
        snippet = _strip_tags(snippet_html)
        if not _relevant(term, title, snippet):
            continue
        return {
            "source": f"DuckDuckGo ({lang})",
            "title": title[:120],
            "snippet": snippet[:600],
            "url": unquote(href),
            "exact": term in title,
        }
    return None


def _strip_tags(text: str) -> str:
    return " ".join(unescape(re.sub(r"<[^>]+>", " ", text)).split())


# ---------------------------------------------------------------- aggregate
def collect(term: str) -> list[dict]:
    """One best, term-relevant result per source; irrelevant sources are dropped."""
    evidence: list[dict] = []
    has_cjk = any("\u4e00" <= char <= "\u9fff" for char in term)

    wiki_zh = wikipedia(term, "zh")
    if wiki_zh:
        evidence.append(wiki_zh)

    if has_cjk:
        page = baike(term)
        if page:
            evidence.append(page)

    g = google(term, "zh" if has_cjk else "en")
    if g:
        evidence.append(g)
    else:
        ddg = duckduckgo(term, "zh" if has_cjk else "en")
        if ddg:
            evidence.append(ddg)

    bing = _best_bing(term, search.bing(term, 8, "zh" if has_cjk else "en"))
    if bing:
        evidence.append(bing)

    if not has_cjk:
        wiki_en = wikipedia(term, "en")
        if wiki_en:
            evidence.append(wiki_en)
    elif len(evidence) < 2:
        wiki_en = wikipedia(term, "en")
        if wiki_en:
            evidence.append(wiki_en)

    # Deduplicate by url, keep order.
    seen: set[str] = set()
    unique: list[dict] = []
    for item in evidence:
        if item["url"] in seen:
            continue
        seen.add(item["url"])
        unique.append(item)
    return unique


def has_exact(evidence: list[dict]) -> dict | None:
    for item in evidence:
        if item.get("exact"):
            return item
    return None
