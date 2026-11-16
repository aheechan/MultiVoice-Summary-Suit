from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

DEFAULT_PATH = Path(
    r"D:/Local Repositories/MultiVoice-Summary-Suit/glossary/terms.jsonl"
)

# How long an entry stays trustworthy before it must be re-checked.
DEFAULT_TTL = {
    "evergreen": 3650,   # stable facts: people, places, institutions
    "product": 120,      # product names, versions, releases
    "current": 30,       # memes, hot words, this-month slang
    "event": 90,         # incidents and news
    "other": 180,
}


def _today() -> str:
    return date.today().isoformat()


def _age_days(stamp: str) -> int:
    try:
        then = datetime.fromisoformat(stamp).date()
    except (TypeError, ValueError):
        return 10_000
    return (date.today() - then).days


class Glossary:
    """Bilingual lexicon of slang, nicknames and products, with freshness rules."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path or DEFAULT_PATH)
        self.topics_path = self.path.with_name("topics.json")
        self.pending_path = self.path.with_name("pending.jsonl")
        self.entries: list[dict] = []
        self.topics: dict[str, str] = {}
        self.pending: list[dict] = []
        self.load()

    # ------------------------------------------------------------------ storage
    def load(self) -> None:
        self.entries = []
        if self.path.exists():
            with self.path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        self.entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        if self.topics_path.exists():
            try:
                self.topics = json.loads(self.topics_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self.topics = {}

        self.pending = []
        if self.pending_path.exists():
            with self.pending_path.open("r", encoding="utf-8") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        self.pending.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as handle:
            for entry in self.entries:
                handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self.topics_path.write_text(
            json.dumps(self.topics, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        with self.pending_path.open("w", encoding="utf-8") as handle:
            for item in self.pending:
                handle.write(json.dumps(item, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------ pending
    def queue(self, term: str, reason: str = "unverified") -> None:
        """Remember a term we could not verify, so it can be reviewed later."""
        for item in self.pending:
            if item["term"] == term:
                item["count"] = item.get("count", 1) + 1
                item["last_seen"] = _today()
                item["reason"] = reason
                self.save()
                return
        self.pending.append({
            "term": term,
            "count": 1,
            "reason": reason,
            "first_seen": _today(),
            "last_seen": _today(),
        })
        self.save()

    def stats(self) -> dict:
        kinds: dict[str, int] = {}
        stale = 0
        for entry in self.entries:
            kinds[entry.get("kind", "other")] = kinds.get(entry.get("kind", "other"), 0) + 1
            if self.is_stale(entry):
                stale += 1
        return {
            "entries": len(self.entries),
            "topics": len(self.topics),
            "pending": len(self.pending),
            "stale": stale,
            "by_kind": kinds,
        }

    # ------------------------------------------------------------------ freshness
    def is_stale(self, entry: dict) -> bool:
        kind = entry.get("kind", "other")
        ttl = int(entry.get("ttl_days") or DEFAULT_TTL.get(kind, 180))
        return _age_days(entry.get("last_verified", "")) > ttl

    def find(self, term: str) -> dict | None:
        for entry in self.entries:
            if entry["term"] == term:
                return entry
        return None

    def needs_research(self, term: str) -> bool:
        entry = self.find(term)
        return entry is None or self.is_stale(entry)

    # ------------------------------------------------------------------ writing
    def add(
        self,
        term: str,
        *,
        aliases: list[str] | None = None,
        definition: str = "",
        en: str = "",
        category: str = "slang",
        kind: str = "other",
        topic: str = "",
        ttl_days: int | None = None,
        confidence: str = "medium",
        related: list[str] | None = None,
        sources: list[str] | None = None,
        auto: bool = False,
    ) -> dict:
        entry = self.find(term)
        if entry is None:
            entry = {
                "term": term,
                "aliases": [],
                "definition": "",
                "en": "",
                "category": category,
                "kind": kind,
                "topic": topic,
                "related": [],
                "sources": [],
                "confidence": confidence,
                "auto": auto,
                "valid_from": _today(),
                "last_verified": _today(),
                "ttl_days": ttl_days or DEFAULT_TTL.get(kind, 180),
            }
            self.entries.append(entry)

        for alias in aliases or []:
            if alias and alias not in entry["aliases"]:
                entry["aliases"].append(alias)
        for key, value in (("definition", definition), ("en", en),
                           ("topic", topic), ("category", category),
                           ("kind", kind), ("confidence", confidence)):
            if value:
                entry[key] = value
        for name in related or []:
            if name not in entry["related"]:
                entry["related"].append(name)
        for url in sources or []:
            if url not in entry["sources"]:
                entry["sources"].append(url)

        entry["last_verified"] = _today()
        entry["ttl_days"] = int(ttl_days or DEFAULT_TTL.get(entry.get("kind", "other"), 180))
        self.save()
        return entry

    def mark_verified(self, term: str) -> None:
        entry = self.find(term)
        if entry:
            entry["last_verified"] = _today()
            self.save()

    def set_topic_summary(self, name: str, summary: str) -> None:
        self.topics[name] = summary
        self.save()

    # ------------------------------------------------------------------ reading
    def match(self, text: str) -> list[dict]:
        hits = []
        for entry in self.entries:
            names = [entry["term"], *entry.get("aliases", [])]
            if any(name and name in text for name in names):
                hits.append(entry)
        return hits

    def apply(self, text: str) -> tuple[str, list[tuple[str, str]]]:
        mapping: list[tuple[str, str]] = []
        for entry in self.entries:
            for alias in entry.get("aliases", []):
                if alias and alias != entry["term"] and alias in text:
                    mapping.append((alias, entry["term"]))
        mapping.sort(key=lambda pair: len(pair[0]), reverse=True)

        changes: list[tuple[str, str]] = []
        for alias, term in mapping:
            if alias in text:
                text = text.replace(alias, term)
                changes.append((alias, term))
        return text, changes

    def prompt_block(self, entries: list[dict]) -> str:
        if not entries:
            return "（无）"
        lines = []
        for entry in entries:
            alias = "、".join(entry.get("aliases", []))
            suffix = f"（曾被识别为：{alias}）" if alias else ""
            stale = "（该词条已过期，需现场核实）" if self.is_stale(entry) else ""
            kind = entry.get("kind", "other")
            lines.append(
                f"- {entry['term']}{suffix}［{kind}，{entry.get('last_verified', '')} 核实］"
                f"{stale}：{entry.get('definition', '')}"
            )
        return "\n".join(lines)

    def context_for(self, text: str) -> tuple[str, list[dict]]:
        hits = self.match(text)
        if not hits:
            return "（无）", []

        topics = {entry.get("topic") for entry in hits if entry.get("topic")}
        blocks: list[str] = []
        for topic in sorted(topics):
            summary = self.topics.get(topic, "")
            members = [e for e in self.entries if e.get("topic") == topic]
            blocks.append(f"【主题：{topic}】{summary}".rstrip())
            blocks.append(self.prompt_block(members))

        loose = [e for e in hits if not e.get("topic")]
        if loose:
            blocks.append("【其他词条】")
            blocks.append(self.prompt_block(loose))
        return "\n".join(blocks), hits


def load(path: str | Path | None = None) -> Glossary:
    return Glossary(Path(path) if path else None)
