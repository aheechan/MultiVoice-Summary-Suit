"""Review dialog for terms that could not be confirmed automatically."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from .. import glossary, prefetch, research
from ..config import PROJECT_ROOT
from . import i18n

ASSETS = PROJECT_ROOT / "assets"

CATEGORIES = ["person", "slang", "theory", "product", "event", "other"]
KINDS = ["evergreen", "product", "current", "event", "other"]

CARD_STYLE = """
QFrame#card {
    background: #0a1220; border: 1px solid #1b3055; border-radius: 10px;
}
QLabel#summary { color: #cfe4ff; font-size: 12px; }
QLabel#titles { color: #7f93ad; font-size: 11px; }
QCheckBox#term { color: #eaf7ff; font-size: 13px; font-weight: 600; }
"""


class TermEditDialog(QDialog):
    """Fill in a pending term before writing it into the knowledge base."""

    def __init__(self, term: str, hint: str = "", topics: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.t("add_to_kb"))
        self.resize(480, 360)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.term = QLineEdit(term)
        self.term.setReadOnly(True)
        self.definition = QTextEdit()
        self.definition.setPlainText(hint)
        self.definition.setFixedHeight(90)
        self.en = QLineEdit()

        self.category = QComboBox()
        self.category.addItems(CATEGORIES)
        self.category.setCurrentText("other")
        self.kind = QComboBox()
        self.kind.addItems(KINDS)
        self.kind.setCurrentText("current")

        self.topic = QComboBox()
        self.topic.setEditable(True)
        self.topic.addItems(topics or ["deepseek", "网络热词"])

        form.addRow(i18n.t("term"), self.term)
        form.addRow(i18n.t("definition"), self.definition)
        form.addRow("English", self.en)
        form.addRow(i18n.t("category"), self.category)
        form.addRow(i18n.t("kind"), self.kind)
        form.addRow(i18n.t("topic"), self.topic)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> dict:
        return {
            "term": self.term.text().strip(),
            "definition": self.definition.toPlainText().strip(),
            "en": self.en.text().strip(),
            "category": self.category.currentText(),
            "kind": self.kind.currentText(),
            "topic": self.topic.currentText().strip(),
        }


class ReviewDialog(QDialog):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.lex = glossary.load()
        self._hints: dict[str, str] = {}
        self.checks: dict[str, QCheckBox] = {}

        self.setWindowTitle(i18n.t("review_title"))
        self.setWindowIcon(QIcon(str(ASSETS / "icon.png")))
        self.resize(760, 580)
        self.setStyleSheet(CARD_STYLE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 12)
        layout.setSpacing(10)

        self.hint = QLabel(i18n.t("review_hint"))
        self.hint.setWordWrap(True)
        layout.addWidget(self.hint)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.container = QWidget()
        self.cards = QVBoxLayout(self.container)
        self.cards.setContentsMargins(2, 2, 2, 2)
        self.cards.setSpacing(12)
        self.cards.addStretch(1)
        self.scroll.setWidget(self.container)
        layout.addWidget(self.scroll, 1)

        row = QDialogButtonBox()
        self.btn_add = QPushButton(i18n.t("add_to_kb"))
        self.btn_research = QPushButton(i18n.t("research_selected"))
        self.btn_drop = QPushButton(i18n.t("drop_selected"))
        row.addButton(self.btn_add, QDialogButtonBox.ButtonRole.ActionRole)
        row.addButton(self.btn_research, QDialogButtonBox.ButtonRole.ActionRole)
        row.addButton(self.btn_drop, QDialogButtonBox.ButtonRole.ActionRole)
        row.addButton(QDialogButtonBox.StandardButton.Close)
        row.rejected.connect(self.accept)
        layout.addWidget(row)

        self.btn_add.clicked.connect(self.add_selected)
        self.btn_research.clicked.connect(self.research_selected)
        self.btn_drop.clicked.connect(self.drop_selected)

        self._cache_mtime_seen = self._cache_mtime()
        self._timer = QTimer(self)
        self._timer.setInterval(1200)
        self._timer.timeout.connect(self._maybe_refresh)
        self._timer.start()

        self.reload()

    # ------------------------------------------------------------------ cards
    def _clear_cards(self) -> None:
        while self.cards.count():
            item = self.cards.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def reload(self) -> None:
        checked = {term for term, box in self.checks.items() if box.isChecked()}
        self._clear_cards()
        self.checks = {}

        if not self.lex.pending:
            label = QLabel(i18n.t("nothing_pending"))
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.cards.addWidget(label)
            self.cards.addStretch(1)
            return

        language = i18n.language()
        dropped: list[str] = []
        for entry in self.lex.pending:
            term = entry["term"]
            record = prefetch.cached(term)
            summary = ""
            titles: list[str] = []
            if record is None:
                summary = "…"
            elif record.get("empty"):
                dropped.append(term)
                continue
            else:
                summary = record.get("summary_zh" if language == "zh" else "summary_en") or ""
                titles = record.get("zh" if language == "zh" else "en") or []
                self._hints[term] = summary or " / ".join(titles[:2])

            card = QFrame()
            card.setObjectName("card")
            inner = QVBoxLayout(card)
            inner.setContentsMargins(14, 12, 14, 12)
            inner.setSpacing(6)

            box = QCheckBox(term)
            box.setObjectName("term")
            font = box.font()
            font.setBold(True)
            box.setFont(font)
            box.setChecked(term in checked)
            self.checks[term] = box
            inner.addWidget(box)

            if summary:
                label = QLabel(summary)
                label.setObjectName("summary")
                label.setWordWrap(True)
                inner.addWidget(label)

            if titles:
                meta = QLabel("· " + "  |  ".join(titles[:2]))
                meta.setObjectName("titles")
                meta.setWordWrap(True)
                inner.addWidget(meta)

            self.cards.addWidget(card)

        self.cards.addStretch(1)

        if dropped:
            self.lex.pending = [p for p in self.lex.pending if p["term"] not in dropped]
            self.lex.save()

    def _cache_mtime(self) -> float:
        try:
            return prefetch.CACHE_PATH.stat().st_mtime
        except OSError:
            return 0.0

    def _maybe_refresh(self) -> None:
        current = self._cache_mtime()
        if current != self._cache_mtime_seen:
            self._cache_mtime_seen = current
            self.reload()

    # ------------------------------------------------------------------ actions
    def selected_terms(self) -> list[str]:
        return [term for term, box in self.checks.items() if box.isChecked()]

    def add_selected(self) -> None:
        for term in self.selected_terms():
            dialog = TermEditDialog(term, self._hints.get(term, ""), list(self.lex.topics), self)
            if not dialog.exec():
                continue
            values = dialog.values()
            self.lex.add(
                values["term"],
                definition=values["definition"],
                en=values["en"],
                category=values["category"],
                kind=values["kind"],
                topic=values["topic"],
                confidence="medium",
            )
            self.lex.resolve_pending(term)
        self.reload()

    def research_selected(self) -> None:
        for term in self.selected_terms():
            entry, ambiguous = research.research_term(term, self.lex, self.cfg)
            if entry:
                self.lex.resolve_pending(term)
            elif ambiguous:
                self.lex.queue(term, reason="still unconfirmed")
        self.reload()

    def drop_selected(self) -> None:
        for term in self.selected_terms():
            self.lex.resolve_pending(term)
        self.reload()
