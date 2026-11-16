from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STORE = PROJECT_ROOT / "configs" / "providers.json"

FIELDS = ("name", "base_url", "model", "api_key", "api_key_env",
          "timeout_s", "enabled", "priority")


def _defaults(cfg) -> list[dict]:
    items = []
    for index, provider in enumerate(cfg.llm.get("providers", [])):
        item = {key: provider.get(key) for key in FIELDS}
        item.setdefault("name", f"provider{index + 1}")
        item["enabled"] = bool(provider.get("enabled", True))
        item["priority"] = int(provider.get("priority", (index + 1) * 10))
        item["timeout_s"] = int(provider.get("timeout_s", 180))
        items.append(item)
    return items


def load(cfg=None) -> list[dict]:
    if STORE.exists():
        try:
            data = json.loads(STORE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [item for item in data if item.get("name")]
        except json.JSONDecodeError:
            pass
    return _defaults(cfg) if cfg is not None else []


def save(items: list[dict]) -> None:
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")


def order(items: list[dict]) -> list[str]:
    enabled = [item for item in items if item.get("enabled", True)]
    enabled.sort(key=lambda item: int(item.get("priority", 100)))
    return [item["name"] for item in enabled]


def masked(item: dict) -> str:
    key = item.get("api_key") or ""
    if item.get("api_key_env"):
        return f"env:{item['api_key_env']}"
    return f"…{key[-4:]}" if key else "—"


def test(item: dict, timeout: float = 8.0) -> tuple[bool, str]:
    base = str(item.get("base_url", "")).rstrip("/")
    if not base:
        return False, "base_url is empty"
    key = item.get("api_key") or ""
    request = urllib.request.Request(
        f"{base}/models",
        headers={"Authorization": f"Bearer {key or 'EMPTY'}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
        return True, f"HTTP {resp.status}, {len(body)} bytes"
    except urllib.error.HTTPError as exc:
        # 401/403 still proves the endpoint is reachable and answering.
        return exc.code in (401, 403), f"HTTP {exc.code}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:120]
