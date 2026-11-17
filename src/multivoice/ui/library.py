"""Knowledge-base manager: collapsible category groups, edit, delete, import/export."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

from .. import glossary
from ..config import PROJECT_ROOT
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
QTreeWidget { background: #0a1220; color: #eaf7ff; border: 1px solid #1b3055; border-radius: 10px; }
QTreeWidget::item { padding: 5px 2px; }
QTreeView::indicator { width: 14px; height: 14px; }
QTreeView::indicator:unchecked { border: 1px solid #4a6fa5; background: #0a1220; border-radius: 3px; }
QTreeView::indicator:checked { border: 1px solid #3d7bff; background: #3d7bff; border-radius: 3px; }
QHeaderView::section { background: #0b1a30; color: #9fe3ff; border: 0px; padding: 6px; }
QPushButton { padding: 7px 12px; }
"""


def _label(rows: list[tuple[str, str]], value: str) -> str:
    for key, text in rows:
        if key == value:
            return i18n.t(text)
    return value or i18n.t("q_other")


class EntryEditDialog(QDialog):
    def __init__(self, entry: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.t("edit"))
        self.resize(520, 470)
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.term = QLineEdit(entry.get("term", ""))
        self.definition = QTextEdit()
        self.definition.setPlainText(entry.get("definition", ""))
        self.definition.setFixedHeight(120)
        self.en = QLineEdit(entry.get("en", ""))

        self.category = QComboBox()
        for value, label in CATEGORIES:
            self.category.addItem(i18n.t(label), value)
        self._select(self.category, CATEGORIES, entry.get("category", "other"))

        self.domain = QComboBox()
        for value, label in DOMAINS:
            self.domain.addItem(i18n.t(label), value)
        self._select(self.domain, DOMAINS, entry.get("domain", "other"))

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

    @staticmethod
    def _select(combo: QComboBox, rows: list[tuple[str, str]], value: str) -> None:
        values = [key for key, _ in rows]
        combo.setCurrentIndex(values.index(value) if value in values else len(rows) - 1)

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
        self.resize(900, 620)
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

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([
            i18n.t("term"), i18n.t("category"),
            i18n.t("q_howlong"), i18n.t("definition"),
        ])
        self.tree.setColumnWidth(0, 200)
        self.tree.setColumnWidth(1, 110)
        self.tree.setColumnWidth(2, 120)
        self.tree.itemChanged.connect(self._on_item_changed)
        layout.addWidget(self.tree, 1)

        self.status = QLabel("")
        self.status.setObjectName("titles")
        layout.addWidget(self.status)

        row = QHBoxLayout()
        for key, handler in (
            ("select_all", lambda: self.set_all(True)),
            ("invert", self.invert),
            ("edit", self.edit_current),
            ("delete", self.delete_checked),
            ("export_kb", self.export_file),
            ("import_kb", self.import_file),
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

    # ------------------------------------------------------------------ data
    def visible_entries(self) -> list[dict]:
        text = self.search.text().strip().lower()
        category = self.filter.currentData()
        result = []
        for entry in self.lex.entries:
            if category and entry.get("category") != category:
                continue
            blob = (entry.get("term", "") + entry.get("definition", "")).lower()
            if text and text not in blob:
                continue
            result.append(entry)
        return result

    def reload(self) -> None:
        expanded = self._expanded_categories()
        self.tree.blockSignals(True)
        self.tree.clear()
        groups: dict[str, list[dict]] = {}
        for entry in self.visible_entries():
            groups.setdefault(entry.get("category", "other"), []).append(entry)

        total = 0
        for value, label in CATEGORIES:
            entries = groups.pop(value, [])
            if not entries:
                continue
            parent = QTreeWidgetItem(self.tree)
            parent.setText(0, f"{i18n.t(label)}  ({len(entries)})")
            parent.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            parent.setCheckState(0, Qt.CheckState.Unchecked)
            font = parent.font(0)
            font.setBold(True)
            parent.setFont(0, font)
            for entry in sorted(entries, key=lambda e: e.get("term", "")):
                child = QTreeWidgetItem(parent)
                child.setText(0, entry.get("term", ""))
                child.setText(1, _label(CATEGORIES, entry.get("category", "other")))
                child.setText(2, _label(DOMAINS, entry.get("domain", "other")))
                child.setText(3, entry.get("definition", "")[:120])
                child.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
                               | Qt.ItemFlag.ItemIsSelectable)
                child.setCheckState(0, Qt.CheckState.Unchecked)
                child.setData(0, Qt.ItemDataRole.UserRole, entry.get("term", ""))
                total += 1
            parent.setExpanded(expanded.get(value, True))

        for value, entries in groups.items():  # unknown categories
            parent = QTreeWidgetItem(self.tree)
            parent.setText(0, f"{value}  ({len(entries)})")
            parent.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable)
            for entry in entries:
                child = QTreeWidgetItem(parent)
                child.setText(0, entry.get("term", ""))
                child.setText(1, entry.get("category", "other"))
                child.setText(2, _label(DOMAINS, entry.get("domain", "other")))
                child.setText(3, entry.get("definition", "")[:120])
                child.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsUserCheckable
                               | Qt.ItemFlag.ItemIsSelectable)
                child.setCheckState(0, Qt.CheckState.Unchecked)
                child.setData(0, Qt.ItemDataRole.UserRole, entry.get("term", ""))
                total += 1

        self.tree.blockSignals(False)
        self.status.setText(i18n.t("entries_count", n=total))

    def _expanded_categories(self) -> dict[str, bool]:
        state: dict[str, bool] = {}
        for index in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(index)
            state[item.text(0).split("  (")[0]] = item.isExpanded()
        return state

    def _on_item_changed(self, item: QTreeWidgetItem, column: int) -> None:
        if column != 0 or item.childCount() == 0:
            return
        state = item.checkState(0)
        if state == Qt.CheckState.PartiallyChecked:
            return
        self.tree.blockSignals(True)
        for index in range(item.childCount()):
            item.child(index).setCheckState(0, state)
        self.tree.blockSignals(False)

    # ------------------------------------------------------------------ actions
    def set_all(self, checked: bool) -> None:
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self.tree.blockSignals(True)
        for index in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(index)
            parent.setCheckState(0, state)
            for child_index in range(parent.childCount()):
                parent.child(child_index).setCheckState(0, state)
        self.tree.blockSignals(False)

    def invert(self) -> None:
        self.tree.blockSignals(True)
        for index in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(index)
            for child_index in range(parent.childCount()):
                child = parent.child(child_index)
                child.setCheckState(
                    0,
                    Qt.CheckState.Unchecked if child.checkState(0) == Qt.CheckState.Checked
                    else Qt.CheckState.Checked,
                )
        self.tree.blockSignals(False)

    def checked_terms(self) -> list[str]:
        terms: list[str] = []
        for index in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(index)
            for child_index in range(parent.childCount()):
                child = parent.child(child_index)
                if child.checkState(0) == Qt.CheckState.Checked:
                    terms.append(child.data(0, Qt.ItemDataRole.UserRole))
        return terms

    def current_term(self) -> str:
        item = self.tree.currentItem()
        if item is None:
            return ""
        if item.parent() is None:
            return ""
        return item.data(0, Qt.ItemDataRole.UserRole) or ""

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
        old_term = entry["term"]
        if values["term"] and values["term"] != entry["term"]:
            entry["term"] = values["term"]
        for key in ("definition", "en", "category", "domain", "topic"):
            entry[key] = values[key]
        self.lex.save()
        if old_term != entry["term"]:
            self.lex.remember_correction(old_term, entry["term"])
            self._sync_outputs(old_term, entry["term"])
        self._reload_data()
        self.status.setText(i18n.t("entry_updated"))

    def _sync_outputs(self, old: str, new: str) -> None:
        """Rewrite the newest export folder so a rename lands in the files too."""
        try:
            dirs = sorted(
                (p for p in self.cfg.output.iterdir() if p.is_dir()),
                key=lambda p: p.stat().st_mtime, reverse=True,
            )
        except OSError:
            return
        if not dirs:
            return
        for path in list(dirs[0].glob("*.md")) + list(dirs[0].glob("text/*.txt")):
            try:
                text = path.read_text(encoding="utf-8")
            except OSError:
                continue
            if old in text:
                path.write_text(text.replace(old, new), encoding="utf-8")

    def delete_checked(self) -> None:
        terms = self.checked_terms() or ([self.current_term()] if self.current_term() else [])
        if not terms:
            self.status.setText(i18n.t("select_one"))
            return
        self.lex.entries = [e for e in self.lex.entries if e["term"] not in terms]
        self.lex.save()
        self._reload_data()
        self.status.setText(i18n.t("entry_deleted", n=len(terms)))

    def _reload_data(self) -> None:
        self.lex = glossary.load()
        self.reload()

    # ------------------------------------------------------------------ files
    def export_file(self) -> None:
        target, _ = QFileDialog.getSaveFileName(
            self, i18n.t("export_kb"),
            str(PROJECT_ROOT / "glossary" / "terms-export.json"), "JSON (*.json)",
        )
        if not target:
            return
        path = self.lex.export(Path(target))
        self.status.setText(i18n.t("export_done", path=path.name))

    def import_file(self) -> None:
        source, _ = QFileDialog.getOpenFileName(
            self, i18n.t("import_kb"), str(PROJECT_ROOT / "glossary"), "JSON (*.json)"
        )
        if not source:
            return
        try:
            payload = json.loads(Path(source).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.status.setText(i18n.t("import_failed"))
            return

        entries = payload.get("entries") if isinstance(payload, dict) else payload
        if not isinstance(entries, list):
            self.status.setText(i18n.t("import_failed"))
            return

        added = updated = 0
        for item in entries:
            term = (item or {}).get("term")
            if not term:
                continue
            existing = self.lex.find(term)
            if existing is None:
                self.lex.entries.append(item)
                added += 1
            else:
                existing.update({k: v for k, v in item.items() if k != "term"})
                updated += 1
        self.lex.save()
        self._reload_data()
        self.status.setText(i18n.t("import_done", added=added, updated=updated))
