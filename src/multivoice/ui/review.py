"""Review dialog for terms that could not be confirmed automatically."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from .. import glossary, research, search
from ..config import PROJECT_ROOT
from . import i18n

ASSETS = PROJECT_ROOT / "assets"

CATEGORIES = ["person", "slang", "theory", "product", "event", "other"]
KINDS = ["evergreen", "product", "current", "event", "other"]


class TermEditDialog(QDialog):
    """Fill in a pending term before writing it into the knowledge base."""

    def __init__(self, term: str, hint: str = "", topics: list[str] | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.t("add_to_kb"))
        self.resize(460, 340)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.term = QLineEdit(term)
        self.term.setReadOnly(True)
        self.definition = QTextEdit()
        self.definition.setPlainText(hint)
        self.definition.setFixedHeight(80)
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
        self._searched = False
        self._hints: dict[str, list[str]] = {}

        self.setWindowTitle(i18n.t("review_title"))
        self.setWindowIcon(QIcon(str(ASSETS / "icon.png")))
        self.resize(560, 400)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(i18n.t("review_hint")))

        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        self.reload()
        layout.addWidget(self.list)

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

    def reload(self) -> None:
        self.list.clear()
        if not self.lex.pending:
            item = QListWidgetItem(i18n.t("nothing_pending"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list.addItem(item)
            return

        if not self._searched:
            import time

            kept = []
            for entry in self.lex.pending:
                hits = search.bing(entry["term"], limit=3)
                if hits is None:
                    # Network problem: keep the term, we learned nothing.
                    kept.append(entry)
                    continue
                if not hits:
                    # Request succeeded and found nothing: treat as mis-transcription.
                    continue
                self._hints[entry["term"]] = [h["title"] for h in hits[:2]]
                kept.append(entry)
                time.sleep(0.4)
            if len(kept) != len(self.lex.pending):
                self.lex.pending = kept
                self.lex.save()
            self._searched = True

        for entry in self.lex.pending:
            hints = self._hints.get(entry["term"], [])
            text = f"{entry['term']}   x{entry.get('count', 1)}   {entry.get('reason', '')}"
            if hints:
                text += "\n    " + "  |  ".join(hints)
            item = QListWidgetItem(text)
            item.setData(1, entry["term"])
            self.list.addItem(item)

    def selected_terms(self) -> list[str]:
        return [i.data(1) for i in self.list.selectedItems() if i.data(1)]

    def add_selected(self) -> None:
        for term in self.selected_terms():
            hint = " / ".join(self._hints.get(term, []))
            dialog = TermEditDialog(term, hint, list(self.lex.topics), self)
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
