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


def _now() -> str:
    from datetime import datetime

    return datetime.now().strftime("%H:%M")


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
        self.corrections_path = self.path.with_name("corrections.json")
        self.rejected_path = self.path.with_name("rejected.json")
        self.entries: list[dict] = []
        self.topics: dict[str, str] = {}
        self.pending: list[dict] = []
        self.corrections: dict[str, str] = {}
        self.rejected: set[str] = set()
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

        self.corrections = {}
        if self.corrections_path.exists():
            try:
                self.corrections = json.loads(
                    self.corrections_path.read_text(encoding="utf-8")
                )
            except json.JSONDecodeError:
                self.corrections = {}

        self.rejected = set()
        if self.rejected_path.exists():
            try:
                self.rejected = set(
                    json.loads(self.rejected_path.read_text(encoding="utf-8"))
                )
            except json.JSONDecodeError:
                self.rejected = set()

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
        self.corrections_path.write_text(
            json.dumps(self.corrections, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        self.rejected_path.write_text(
            json.dumps(sorted(self.rejected), ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def remember_correction(self, wrong: str, right: str) -> None:
        """Persist a mishearing fix so the wrong spelling never queues again."""
        if wrong and right and wrong != right:
            self.corrections[wrong] = right
            self.save()

    def reject(self, term: str) -> None:
        """Mark a term as not worth keeping; never queue or import it again."""
        if term:
            self.rejected.add(term)
            self.pending = [item for item in self.pending if item["term"] != term]
            self.save()

    def is_rejected(self, term: str) -> bool:
        return term in self.rejected

    # ------------------------------------------------------------------ pending
    def queue(self, term: str, reason: str = "unverified") -> None:
        """Remember a term we could not verify, so it can be reviewed later."""
        for item in self.pending:
            if item["term"] == term:
                item["count"] = item.get("count", 1) + 1
                item["attempts"] = item.get("attempts", 1) + 1
                item["last_seen"] = _today()
                item["seen_at"] = _now()
                item["reason"] = reason
                self.save()
                return
        self.pending.append({
            "term": term,
            "count": 1,
            "attempts": 1,
            "reason": reason,
            "first_seen": _today(),
            "last_seen": _today(),
            "seen_at": _now(),
        })
        self.save()

    def resolve_pending(self, term: str) -> None:
        before = len(self.pending)
        self.pending = [item for item in self.pending if item["term"] != term]
        if len(self.pending) != before:
            self.save()

    def prune_pending(self, max_age_days: int = 14, max_attempts: int = 3) -> list[str]:
        """Drop terms that never found a source: no evidence means no entry."""
        keep: list[dict] = []
        dropped: list[str] = []
        for item in self.pending:
            too_old = _age_days(item.get("first_seen", "")) > max_age_days
            too_many = item.get("attempts", 1) >= max_attempts
            if too_old or too_many:
                dropped.append(item["term"])
            else:
                keep.append(item)
        if dropped:
            self.pending = keep
            self.save()
        return dropped

    def export(self, target: Path) -> Path:
        """Write the whole knowledge base as one portable JSON file."""
        payload = {
            "exported_at": _today(),
            "topics": self.topics,
            "entries": self.entries,
            "pending": self.pending,
        }
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return target

    def stats(self) -> dict:
        categories: dict[str, int] = {}
        domains: dict[str, int] = {}
        for entry in self.entries:
            category = entry.get("category", "other")
            domain = entry.get("domain", "other")
            categories[category] = categories.get(category, 0) + 1
            domains[domain] = domains.get(domain, 0) + 1
        return {
            "entries": len(self.entries),
            "topics": len(self.topics),
            "pending": len(self.pending),
            "by_category": categories,
            "by_domain": domains,
        }

    # ------------------------------------------------------------------ freshness
    def is_stale(self, entry: dict) -> bool:
        """Entries never expire: a term is a fact, not a subscription."""
        return False

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
        domain: str = "",
        kind: str = "evergreen",
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
                "domain": domain,
                "kind": kind,
                "topic": topic,
                "related": [],
                "sources": [],
                "confidence": confidence,
                "auto": auto,
                "valid_from": _today(),
                "last_verified": _today(),
                "ttl_days": ttl_days or 36500,
            }
            self.entries.append(entry)

        for alias in aliases or []:
            if alias and alias not in entry["aliases"]:
                entry["aliases"].append(alias)
        for key, value in (("definition", definition), ("en", en),
                           ("topic", topic), ("category", category),
                           ("domain", domain), ("kind", kind),
                           ("confidence", confidence)):
            if value:
                entry[key] = value
        for name in related or []:
            if name not in entry["related"]:
                entry["related"].append(name)
        for url in sources or []:
            if url not in entry["sources"]:
                entry["sources"].append(url)

        entry["last_verified"] = _today()
        entry["ttl_days"] = int(ttl_days or 36500)
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
        for wrong, right in self.corrections.items():
            if wrong and wrong in text and wrong != right:
                mapping.append((wrong, right))
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
            tags = "/".join(t for t in (entry.get("category"), entry.get("domain")) if t)
            tag_text = f"［{tags}］" if tags else ""
            lines.append(f"- {entry['term']}{suffix}{tag_text}：{entry.get('definition', '')}")
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
