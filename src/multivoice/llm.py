from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request

from .config import Config


def _providers(cfg: Config) -> list[dict]:
    providers = cfg.llm.get("providers")
    if not providers:
        return [cfg.llm]
    enabled = {p["name"]: p for p in providers if p.get("enabled", True)}
    order = cfg.llm.get("order") or list(enabled)
    return [enabled[name] for name in order if name in enabled]


def _api_key(provider: dict) -> str:
    env = provider.get("api_key_env")
    if env:
        return os.environ.get(env, "")
    return provider.get("api_key", "EMPTY")


def _opener(url: str):
    """Loopback endpoints must bypass the system proxy (VPN clients set one)."""
    host = urllib.parse.urlparse(url).hostname or ""
    if host in ("127.0.0.1", "localhost", "::1", "0.0.0.0"):
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))
    return urllib.request.build_opener()


def _call(
    provider: dict,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    thinking: bool,
) -> str:
    base = str(provider.get("base_url", "")).rstrip("/")
    if not base:
        raise RuntimeError("provider.base_url is empty")

    payload = {
        "model": provider.get("model", "local"),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
        "chat_template_kwargs": {"enable_thinking": thinking},
    }
    request = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_api_key(provider)}",
        },
        method="POST",
    )
    with _opener(f"{base}/chat/completions").open(
        request, timeout=provider.get("timeout_s", 180)
    ) as resp:
        body = json.loads(resp.read().decode("utf-8"))

    choice = body["choices"][0]
    content = (choice.get("message", {}).get("content") or "").strip()
    if not content:
        reasoning = choice.get("message", {}).get("reasoning_content") or ""
        raise RuntimeError(
            "empty content"
            + (" (model spent the budget on reasoning; raise max_tokens or disable thinking)"
               if reasoning else "")
        )
    return content


def chat(
    messages: list[dict],
    cfg: Config,
    *,
    temperature: float | None = None,
    max_tokens: int = 2048,
) -> str:
    """Try providers in order; fall back on connection or protocol errors."""
    temp = cfg.llm.get("temperature", 0.2) if temperature is None else temperature
    thinking = bool(cfg.llm.get("thinking", False))
    errors: list[str] = []
    for provider in _providers(cfg):
        try:
            return _call(provider, messages, temp, max_tokens, thinking)
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError,
                RuntimeError) as exc:
            errors.append(f"{provider.get('name', '?')}: {exc}")
            continue
    raise RuntimeError("all LLM providers failed -> " + " | ".join(errors))


def available(cfg: Config) -> list[str]:
    return [p.get("name", "?") for p in _providers(cfg)]
