"""Review dialog for terms that could not be confirmed automatically."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QProgressDialog,
    QPushButton,
    QRadioButton,
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
    """Two plain-language questions, then save. No jargon fields."""

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

    def __init__(self, term: str, hint: str = "", topics: list[str] | None = None,
                 cfg=None, parent=None):
        super().__init__(parent)
        self.cfg = cfg
        self._en = ""
        self.setWindowTitle(i18n.t("add_to_kb"))
        self.resize(520, 560)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self.term = QLineEdit(term)
        self.term.setReadOnly(True)
        layout.addWidget(self.term)

        layout.addWidget(QLabel(i18n.t("edit_definition")))
        self.definition = QTextEdit()
        self.definition.setPlainText(hint)
        self.definition.setFixedHeight(96)
        layout.addWidget(self.definition)

        what_box = QGroupBox(i18n.t("q_what"))
        what_layout = QGridLayout(what_box)
        what_layout.setHorizontalSpacing(18)
        what_layout.setVerticalSpacing(6)
        self.category_group = QButtonGroup(self)
        for index, (value, label) in enumerate(self.CATEGORIES):
            radio = QRadioButton(i18n.t(label))
            radio.setProperty("value", value)
            self.category_group.addButton(radio, index)
            what_layout.addWidget(radio, index // 2, index % 2)
            if value == "slang":
                radio.setChecked(True)
        layout.addWidget(what_box)

        domain_box = QGroupBox(i18n.t("q_howlong"))
        domain_layout = QGridLayout(domain_box)
        domain_layout.setHorizontalSpacing(18)
        domain_layout.setVerticalSpacing(6)
        self.domain_group = QButtonGroup(self)
        for index, (value, label) in enumerate(self.DOMAINS):
            radio = QRadioButton(i18n.t(label))
            radio.setProperty("value", value)
            self.domain_group.addButton(radio, index)
            domain_layout.addWidget(radio, index // 2, index % 2)
            if value == "ai":
                radio.setChecked(True)
        layout.addWidget(domain_box)

        topic_row = QHBoxLayout()
        topic_row.addWidget(QLabel(i18n.t("topic")))
        self.topic = QComboBox()
        self.topic.setEditable(True)
        self.topic.addItems(topics or ["deepseek", "网络热词"])
        topic_row.addWidget(self.topic, 1)
        layout.addLayout(topic_row)

        layout.addStretch(1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _checked_value(self, group: QButtonGroup) -> str:
        button = group.checkedButton()
        return button.property("value") if button else "other"

    def _translate(self, text: str) -> str:
        if self.cfg is None:
            return ""
        try:
            from .. import llm

            answer = llm.chat(
                [{"role": "user", "content":
                  "Translate the following glossary definition into one concise English "
                  f"sentence. Output only the translation.\n\n{text}"}],
                self.cfg, temperature=0.0, max_tokens=256,
            )
            return answer.strip()
        except Exception:
            return ""

    def accept(self) -> None:
        text = self.definition.toPlainText().strip()
        if text and not self._en:
            self._en = self._translate(text)
        super().accept()

    def values(self) -> dict:
        return {
            "term": self.term.text().strip(),
            "definition": self.definition.toPlainText().strip(),
            "en": self._en,
            "category": self._checked_value(self.category_group),
            "domain": self._checked_value(self.domain_group),
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

        tools = QHBoxLayout()
        tools.setSpacing(8)
        self.btn_all = QPushButton(i18n.t("select_all"))
        self.btn_all.clicked.connect(lambda: self.set_all(True))
        self.btn_invert = QPushButton(i18n.t("invert"))
        self.btn_invert.clicked.connect(self.invert_selection)
        self.btn_fix = QPushButton(i18n.t("fix_term"))
        self.btn_fix.clicked.connect(self.fix_term)
        self.btn_fetch = QPushButton(i18n.t("fetch_missing"))
        self.btn_fetch.clicked.connect(self.fetch_missing)
        tools.addWidget(self.btn_all)
        tools.addWidget(self.btn_invert)
        tools.addWidget(self.btn_fix)
        tools.addWidget(self.btn_fetch)
        tools.addStretch(1)
        layout.addLayout(tools)

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

        self.status = QLabel("")
        self.status.setObjectName("titles")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

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
                summary = i18n.t("not_fetched")
            elif record.get("empty"):
                summary = i18n.t("no_result")
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

    def set_all(self, checked: bool) -> None:
        for box in self.checks.values():
            box.setChecked(checked)

    def invert_selection(self) -> None:
        for box in self.checks.values():
            box.setChecked(not box.isChecked())

    def fetch_missing(self) -> None:
        """Search every pending term that has no cached summary yet."""
        missing = [p["term"] for p in self.lex.pending if prefetch.cached(p["term"]) is None]
        if not missing:
            self.status.setText(i18n.t("nothing_pending"))
            return

        progress = QProgressDialog(i18n.t("fetching"), "", 0, len(missing), self)
        progress.setWindowTitle(i18n.t("fetch_missing"))
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        QApplication.processEvents()

        for index, term in enumerate(missing, 1):
            progress.setLabelText(f"{term}  ({index}/{len(missing)})")
            QApplication.processEvents()
            prefetch.build(term, self.cfg)
            progress.setValue(index)
            QApplication.processEvents()

        progress.close()
        self.reload()

    def fix_term(self) -> None:
        """Correct a mis-recognised term, then search again with the new spelling."""
        terms = self.selected_terms()
        if len(terms) != 1:
            self.status.setText(i18n.t("review_hint"))
            return
        old = terms[0]
        new, ok = QInputDialog.getText(
            self, i18n.t("fix_term"), i18n.t("fix_prompt"), text=old
        )
        new = new.strip()
        if not ok or not new or new == old:
            return

        for item in self.lex.pending:
            if item["term"] == old:
                item["term"] = new
        self.lex.save()
        prefetch.drop_cache(old)

        self.status.setText(i18n.t("fix_done", term=new))
        QApplication.processEvents()
        prefetch.build(new, self.cfg)
        self.reload()

    def add_selected(self) -> None:
        for term in self.selected_terms():
            dialog = TermEditDialog(term, self._hints.get(term, ""),
                                    list(self.lex.topics), self.cfg, self)
            if not dialog.exec():
                continue
            values = dialog.values()
            reason = ""
            for item in self.lex.pending:
                if item["term"] == term:
                    reason = item.get("reason", "")
                    break
            topic = reason.split(":", 1)[1] if reason.startswith("discovered:") else values["topic"]
            self.lex.add(
                values["term"],
                definition=values["definition"],
                en=values["en"],
                category=values["category"],
                domain=values["domain"],
                topic=topic,
                confidence="medium",
            )
            self.lex.resolve_pending(term)
        self.reload()

    def research_selected(self) -> None:
        terms = self.selected_terms()
        if not terms:
            self.status.setText(i18n.t("nothing_pending"))
            return

        progress = QProgressDialog(i18n.t("researching"), "", 0, len(terms), self)
        progress.setWindowTitle(i18n.t("research_selected"))
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setCancelButton(None)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        QApplication.processEvents()

        saved = unconfirmed = dropped = 0
        for index, term in enumerate(terms, 1):
            progress.setLabelText(f"{term}  ({index}/{len(terms)})")
            QApplication.processEvents()

            entry, ambiguous = research.research_term(term, self.lex, self.cfg)
            if entry is not None:
                self.lex.resolve_pending(term)
                saved += 1
            elif ambiguous:
                self.lex.queue(term, reason="still unconfirmed")
                unconfirmed += 1
            else:
                # No reliable match: keep it visible instead of silently deleting.
                self.lex.queue(term, reason="no-match")
                dropped += 1

            progress.setValue(index)
            QApplication.processEvents()

        progress.close()
        self.status.setText(i18n.t("rs_status", saved=saved,
                                   pending=unconfirmed, dropped=dropped))
        self.reload()

    def drop_selected(self) -> None:
        for term in self.selected_terms():
            self.lex.resolve_pending(term)
        self.reload()
