"""Knowledge-base manager: browse entries by category, edit or delete them."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
)

from .. import glossary
from . import i18n

CATEGORIES = [
    ("person", "q_person"),
    ("organization", "q_org"),
    ("product", "q_product"),
    ("tool", "q_tool"),
    ("instrument", "q_instrument"),
    ("work", "q_work"),
    ("concept", "q_concept"),
    ("slang", "q_slang"),
    ("theory", "q_theory"),
    ("event", "q_event"),
    ("place", "q_place"),
    ("other", "q_other"),
]
DOMAINS = [
    ("ai", "q_evergreen"),
    ("business", "q_product_ttl"),
    ("history", "q_current_ttl"),
    ("science", "q_event_ttl"),
    ("culture", "dom_culture"),
    ("life", "dom_life"),
    ("other", "dom_other"),
]

STYLE = """
QTableWidget { background: #0a1220; color: #eaf7ff; gridline-color: #1b3055; }
QHeaderView::section { background: #0b1a30; color: #9fe3ff; border: 0px; padding: 6px; }
QPushButton { padding: 7px 12px; }
"""


class EntryEditDialog(QDialog):
    def __init__(self, entry: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.t("edit"))
        self.resize(520, 460)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.term = QLineEdit(entry.get("term", ""))
        self.definition = QTextEdit()
        self.definition.setPlainText(entry.get("definition", ""))
        self.definition.setFixedHeight(110)
        self.en = QLineEdit(entry.get("en", ""))

        self.category = QComboBox()
        for value, label in CATEGORIES:
            self.category.addItem(i18n.t(label), value)
        self.category.setCurrentIndex(
            max(0, [v for v, _ in CATEGORIES].index(entry.get("category", "other")))
            if entry.get("category", "other") in [v for v, _ in CATEGORIES] else len(CATEGORIES) - 1
        )

        self.domain = QComboBox()
        for value, label in DOMAINS:
            self.domain.addItem(i18n.t(label), value)
        current = entry.get("domain", "other")
        self.domain.setCurrentIndex(
            [v for v, _ in DOMAINS].index(current) if current in [v for v, _ in DOMAINS]
            else len(DOMAINS) - 1
        )

        self.topic = QLineEdit(entry.get("topic", ""))

        form.addRow(i18n.t("term"), self.term)
        form.addRow(i18n.t("definition"), self.definition)
        form.addRow("English", self.en)
        form.addRow(i18n.t("category"), self.category)
        form.addRow(i18n.t("q_howlong"), self.domain)
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
            "category": self.category.currentData(),
            "domain": self.domain.currentData(),
            "topic": self.topic.text().strip(),
        }


class LibraryDialog(QDialog):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.lex = glossary.load()
        self.setWindowTitle(i18n.t("manage_terms"))
        self.resize(860, 560)
        self.setStyleSheet(STYLE)

        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText(i18n.t("search_terms"))
        self.search.textChanged.connect(self.reload)
        self.filter = QComboBox()
        self.filter.addItem(i18n.t("all_categories"), "")
        for value, label in CATEGORIES:
            self.filter.addItem(i18n.t(label), value)
        self.filter.currentIndexChanged.connect(self.reload)
        top.addWidget(self.search, 1)
        top.addWidget(self.filter)
        layout.addLayout(top)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels([
            "", i18n.t("term"), i18n.t("category"),
            i18n.t("q_howlong"), i18n.t("definition"),
        ])
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table, 1)

        self.status = QLabel("")
        self.status.setObjectName("titles")
        layout.addWidget(self.status)

        row = QHBoxLayout()
        for key, handler in (
            ("select_all", lambda: self.set_all(True)),
            ("invert", self.invert),
            ("edit", self.edit_current),
            ("delete", self.delete_checked),
        ):
            button = QPushButton(i18n.t(key))
            button.clicked.connect(handler)
            row.addWidget(button)
        row.addStretch(1)
        close = QPushButton(i18n.t("close"))
        close.clicked.connect(self.accept)
        row.addWidget(close)
        layout.addLayout(row)

        self.reload()

    def visible_entries(self) -> list[dict]:
        text = self.search.text().strip().lower()
        category = self.filter.currentData()
        result = []
        for entry in self.lex.entries:
            if category and entry.get("category") != category:
                continue
            if text and text not in (entry.get("term", "") + entry.get("definition", "")).lower():
                continue
            result.append(entry)
        return result

    def reload(self) -> None:
        entries = self.visible_entries()
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            check = QTableWidgetItem()
            check.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            check.setCheckState(Qt.CheckState.Unchecked)
            self.table.setItem(row, 0, check)
            self.table.setItem(row, 1, QTableWidgetItem(entry.get("term", "")))
            self.table.setItem(row, 2, QTableWidgetItem(entry.get("category", "")))
            self.table.setItem(row, 3, QTableWidgetItem(entry.get("domain", "")))
            self.table.setItem(row, 4, QTableWidgetItem(entry.get("definition", "")[:120]))
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.status.setText(i18n.t("entries_count", n=len(entries)))

    def set_all(self, checked: bool) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)

    def invert(self) -> None:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item:
                item.setCheckState(
                    Qt.CheckState.Unchecked if item.checkState() == Qt.CheckState.Checked
                    else Qt.CheckState.Checked
                )

    def checked_terms(self) -> list[str]:
        terms = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            if item and item.checkState() == Qt.CheckState.Checked:
                terms.append(self.table.item(row, 1).text())
        return terms

    def current_term(self) -> str:
        row = self.table.currentRow()
        if row < 0:
            return ""
        item = self.table.item(row, 1)
        return item.text() if item else ""

    def edit_current(self) -> None:
        term = self.current_term()
        entry = self.lex.find(term) if term else None
        if not entry:
            self.status.setText(i18n.t("select_one"))
            return
        dialog = EntryEditDialog(entry, self)
        if not dialog.exec():
            return
        values = dialog.values()
        if values["term"] and values["term"] != entry["term"]:
            entry["term"] = values["term"]
        for key in ("definition", "en", "category", "domain", "topic"):
            entry[key] = values[key]
        self.lex.save()
        self.lex = glossary.load()
        self.reload()
        self.status.setText(i18n.t("entry_updated"))

    def delete_checked(self) -> None:
        terms = self.checked_terms()
        if not terms:
            term = self.current_term()
            terms = [term] if term else []
        if not terms:
            self.status.setText(i18n.t("select_one"))
            return
        self.lex.entries = [e for e in self.lex.entries if e["term"] not in terms]
        self.lex.save()
        self.lex = glossary.load()
        self.reload()
        self.status.setText(i18n.t("entry_deleted", n=len(terms)))
