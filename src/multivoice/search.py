from __future__ import annotations

import html
import re
import urllib.parse
import urllib.request

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
TAG = re.compile(r"<[^>]+>")
RESULT = re.compile(
    r'<li class="b_algo".*?<h2>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>.*?'
    r"<p[^>]*>(.*?)</p>",
    re.S,
)


def bing(query: str, limit: int = 5) -> list[dict] | None:
    """Scrape Bing's HTML results.

    Returns None when the request itself failed (network, rate limit), and an
    empty list when the request succeeded but matched nothing. Callers must not
    treat a failed request as "this term does not exist".
    """
    url = "https://www.bing.com/search?" + urllib.parse.urlencode({"q": query})
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
    except Exception:
        return None

    results: list[dict] = []
    for href, title, snippet in RESULT.findall(body):
        results.append({
            "title": html.unescape(TAG.sub("", title)).strip(),
            "snippet": html.unescape(TAG.sub("", snippet)).strip(),
            "url": html.unescape(href),
        })
        if len(results) >= limit:
            break
    return results


def format_results(results: list[dict]) -> str:
    lines = []
    for item in results:
        lines.append(f"- {item['title']}: {item['snippet'][:220]}")
    return "\n".join(lines) if lines else "（无搜索结果）"
