"""Review dialog for terms that could not be confirmed automatically."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from .. import glossary, research
from ..config import PROJECT_ROOT
from . import i18n

ASSETS = PROJECT_ROOT / "assets"


class ReviewDialog(QDialog):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.lex = glossary.load()

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
        self.btn_research = QPushButton(i18n.t("research_selected"))
        self.btn_drop = QPushButton(i18n.t("drop_selected"))
        row.addButton(self.btn_research, QDialogButtonBox.ButtonRole.ActionRole)
        row.addButton(self.btn_drop, QDialogButtonBox.ButtonRole.ActionRole)
        row.addButton(QDialogButtonBox.StandardButton.Close)
        row.rejected.connect(self.accept)
        layout.addWidget(row)

        self.btn_research.clicked.connect(self.research_selected)
        self.btn_drop.clicked.connect(self.drop_selected)

    def reload(self) -> None:
        self.list.clear()
        if not self.lex.pending:
            item = QListWidgetItem(i18n.t("nothing_pending"))
            item.setFlags(Qt.ItemFlag.NoItemFlags)
            self.list.addItem(item)
            return
        for entry in self.lex.pending:
            item = QListWidgetItem(
                f"{entry['term']}   x{entry.get('count', 1)}   {entry.get('reason', '')}"
            )
            item.setData(1, entry["term"])
            self.list.addItem(item)

    def selected_terms(self) -> list[str]:
        return [i.data(1) for i in self.list.selectedItems() if i.data(1)]

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
