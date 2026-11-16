"""Daily review dialog for terms that could not be confirmed automatically."""
from __future__ import annotations

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

ASSETS = PROJECT_ROOT / "assets"


class ReviewDialog(QDialog):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.lex = glossary.load()

        self.setWindowTitle("Pending terms")
        self.setWindowIcon(QIcon(str(ASSETS / "icon.png")))
        self.resize(520, 380)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "These terms were found online but could not be confirmed.\n"
            "Research them again, or drop them from the queue."
        ))

        self.list = QListWidget()
        self.list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        for item in self.lex.pending:
            entry = QListWidgetItem(
                f"{item['term']}   x{item.get('count', 1)}   {item.get('reason', '')}"
            )
            entry.setData(1, item["term"])
            self.list.addItem(entry)
        layout.addWidget(self.list)

        row = QDialogButtonBox()
        self.btn_research = QPushButton("Research selected")
        self.btn_drop = QPushButton("Drop selected")
        row.addButton(self.btn_research, QDialogButtonBox.ButtonRole.ActionRole)
        row.addButton(self.btn_drop, QDialogButtonBox.ButtonRole.ActionRole)
        row.addButton(QDialogButtonBox.StandardButton.Close)
        row.rejected.connect(self.accept)
        layout.addWidget(row)

        self.btn_research.clicked.connect(self.research_selected)
        self.btn_drop.clicked.connect(self.drop_selected)

    def selected_terms(self) -> list[str]:
        return [i.data(1) for i in self.list.selectedItems()]

    def research_selected(self) -> None:
        for term in self.selected_terms():
            entry, ambiguous = research.research_term(term, self.lex, self.cfg)
            if entry:
                self.lex.resolve_pending(term)
                for i in range(self.list.count()):
                    if self.list.item(i).data(1) == term:
                        self.list.takeItem(i)
                        break
            elif ambiguous:
                self.lex.queue(term, reason="still unconfirmed")

    def drop_selected(self) -> None:
        for term in self.selected_terms():
            self.lex.resolve_pending(term)
            for i in range(self.list.count()):
                if self.list.item(i).data(1) == term:
                    self.list.takeItem(i)
                    break
