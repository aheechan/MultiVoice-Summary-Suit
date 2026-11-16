"""Provider management dialogs: add / edit / reorder / test LLM endpoints."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from .. import providers
from . import i18n


class ProviderEditDialog(QDialog):
    def __init__(self, item: dict | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(i18n.t("edit") if item else i18n.t("add"))
        self.resize(460, 320)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.name = QLineEdit((item or {}).get("name", ""))
        self.base_url = QLineEdit((item or {}).get("base_url", "http://127.0.0.1:8082/v1"))
        self.model = QLineEdit((item or {}).get("model", ""))
        self.api_key = QLineEdit((item or {}).get("api_key", ""))
        self.api_key.setEchoMode(QLineEdit.EchoMode.Password)

        self.priority = QSpinBox()
        self.priority.setRange(1, 999)
        self.priority.setValue(int((item or {}).get("priority", 10)))

        self.timeout = QSpinBox()
        self.timeout.setRange(5, 600)
        self.timeout.setValue(int((item or {}).get("timeout_s", 180)))

        self.enabled = QCheckBox(i18n.t("enabled"))
        self.enabled.setChecked(bool((item or {}).get("enabled", True)))

        form.addRow(i18n.t("name"), self.name)
        form.addRow(i18n.t("base_url"), self.base_url)
        form.addRow(i18n.t("model"), self.model)
        form.addRow(i18n.t("priority"), self.priority)
        form.addRow(i18n.t("timeout"), self.timeout)
        form.addRow(i18n.t("api_key"), self.api_key)
        form.addRow(self.enabled)
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def values(self) -> dict:
        return {
            "name": self.name.text().strip(),
            "base_url": self.base_url.text().strip(),
            "model": self.model.text().strip(),
            "api_key": self.api_key.text().strip(),
            "priority": self.priority.value(),
            "timeout_s": self.timeout.value(),
            "enabled": self.enabled.isChecked(),
        }


class ProviderManagerDialog(QDialog):
    def __init__(self, cfg, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self.items = providers.load(cfg)
        self.status: dict[str, str] = {}

        self.setWindowTitle(i18n.t("provider_title"))
        self.resize(880, 460)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(i18n.t("provider_hint")))

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            i18n.t("enabled"), i18n.t("name"), i18n.t("base_url"),
            i18n.t("model"), i18n.t("priority"), i18n.t("key"),
            i18n.t("status"),
        ])
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        row = QHBoxLayout()
        for key, handler in (
            ("add", self.add_item), ("edit", self.edit_item),
            ("delete", self.delete_item), ("move_up", lambda: self.move(-1)),
            ("move_down", lambda: self.move(1)), ("test", self.test_item),
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

    def reload(self) -> None:
        self.table.setRowCount(len(self.items))
        for index, item in enumerate(self.items):
            values = [
                "✓" if item.get("enabled", True) else "",
                item.get("name", ""),
                item.get("base_url", ""),
                item.get("model", ""),
                str(item.get("priority", "")),
                providers.masked(item),
                self.status.get(item["name"], i18n.t("not_tested")),
            ]
            for column, value in enumerate(values):
                cell = QTableWidgetItem(value)
                if column == 0:
                    cell.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(index, column, cell)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)

    def current_index(self) -> int:
        rows = self.table.selectionModel().selectedRows()
        return rows[0].row() if rows else -1

    def add_item(self) -> None:
        dialog = ProviderEditDialog(None, self)
        if dialog.exec():
            data = dialog.values()
            if data["name"]:
                self.items.append(data)
                self.commit()

    def edit_item(self) -> None:
        index = self.current_index()
        if index < 0:
            return
        dialog = ProviderEditDialog(self.items[index], self)
        if dialog.exec():
            data = dialog.values()
            if data["name"]:
                self.items[index] = data
                self.commit()

    def delete_item(self) -> None:
        index = self.current_index()
        if index >= 0:
            self.items.pop(index)
            self.commit()

    def move(self, delta: int) -> None:
        index = self.current_index()
        target = index + delta
        if 0 <= index < len(self.items) and 0 <= target < len(self.items):
            self.items[index], self.items[target] = self.items[target], self.items[index]
            self.commit(select=target)

    def test_item(self) -> None:
        index = self.current_index()
        if index < 0:
            return
        ok, detail = providers.test(self.items[index])
        self.status[self.items[index]["name"]] = (
            f"{i18n.t('test_ok')}: {detail}" if ok else f"{i18n.t('test_failed')}: {detail}"
        )
        self.reload()

    def commit(self, select: int | None = None) -> None:
        providers.save(self.items)
        self.cfg.llm["providers"] = self.items
        self.cfg.llm["order"] = providers.order(self.items)
        self.reload()
        if select is not None and 0 <= select < len(self.items):
            self.table.selectRow(select)
