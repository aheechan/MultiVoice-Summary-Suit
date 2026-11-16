from __future__ import annotations

import json
import os
import urllib.error
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


def _call(
    provider: dict,
    messages: list[dict],
    temperature: float,
    max_tokens: int,
    no_think: bool = False,
) -> str:
    base = str(provider.get("base_url", "")).rstrip("/")
    if not base:
        raise RuntimeError("provider.base_url is empty")

    if no_think and messages:
        last = dict(messages[-1])
        last["content"] = f"{last['content']}\n/no_think"
        messages = messages[:-1] + [last]

    payload = {
        "model": provider.get("model", "local"),
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
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
    with urllib.request.urlopen(request, timeout=provider.get("timeout_s", 180)) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"].strip()


def chat(
    messages: list[dict],
    cfg: Config,
    *,
    temperature: float | None = None,
    max_tokens: int = 2048,
) -> str:
    """Try providers in order; fall back on connection or protocol errors."""
    temp = cfg.llm.get("temperature", 0.2) if temperature is None else temperature
    no_think = bool(cfg.llm.get("no_think", False))
    errors: list[str] = []
    for provider in _providers(cfg):
        try:
            return _call(provider, messages, temp, max_tokens, no_think)
        except (urllib.error.URLError, TimeoutError, KeyError, json.JSONDecodeError) as exc:
            errors.append(f"{provider.get('name', '?')}: {exc}")
            continue
    raise RuntimeError("all LLM providers failed -> " + " | ".join(errors))


def available(cfg: Config) -> list[str]:
    return [p.get("name", "?") for p in _providers(cfg)]
