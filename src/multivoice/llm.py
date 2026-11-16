from __future__ import annotations

import json
import urllib.error
import urllib.request

from .config import Config


def chat(
    messages: list[dict],
    cfg: Config,
    *,
    temperature: float | None = None,
    max_tokens: int = 2048,
) -> str:
    """Call an OpenAI-compatible chat endpoint."""
    base = str(cfg.llm.get("base_url", "")).rstrip("/")
    if not base:
        raise RuntimeError("llm.base_url is not configured in configs/models.toml")

    payload = {
        "model": cfg.llm.get("model", "local"),
        "messages": messages,
        "temperature": cfg.llm.get("temperature", 0.2) if temperature is None else temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }
    request = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {cfg.llm.get('api_key', 'EMPTY')}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=cfg.llm.get("timeout_s", 180)) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise RuntimeError(f"LLM request failed: {exc}") from exc

    return body["choices"][0]["message"]["content"].strip()
