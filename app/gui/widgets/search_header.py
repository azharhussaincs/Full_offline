"""The top of the window — the "hero": the product mark + name, a short
tagline, the search field, and the Search / Clear buttons.

Emits :attr:`submitted` (with the trimmed query) when the user presses Enter or
clicks Search, and :attr:`cleared` when they click Clear.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.gui import icons, theme


class SearchHeader(QFrame):
    """The white header strip with the product mark and the search controls."""

    submitted = Signal(str)
    cleared = Signal()

    def __init__(self, app_name: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("headerBar")
        self.setAttribute(Qt.WA_StyledBackground, True)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 28, 0, 26)
        outer.setSpacing(0)

        # A centred, max-width column so the hero reads like a polished SaaS page.
        column = QWidget()
        column.setMaximumWidth(theme.SEARCH_MAX_WIDTH)
        column_layout = QVBoxLayout(column)
        column_layout.setContentsMargins(theme.PAGE_GUTTER, 0, theme.PAGE_GUTTER, 0)
        column_layout.setSpacing(0)

        column_row = QHBoxLayout()
        column_row.setContentsMargins(0, 0, 0, 0)
        column_row.addStretch(1)
        column_row.addWidget(column, 100)
        column_row.addStretch(1)
        outer.addLayout(column_row)

        # --- product mark + name ---------------------------------------
        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(0, 0, 0, 0)
        brand_row.setSpacing(11)
        brand_row.addStretch(1)

        logo = QLabel()
        logo.setPixmap(icons.logo_pixmap(34))
        logo.setFixedSize(34, 34)
        brand_row.addWidget(logo, 0, Qt.AlignVCenter)

        title = QLabel(app_name)
        title.setObjectName("appTitle")
        title.setAlignment(Qt.AlignVCenter)
        brand_row.addWidget(title, 0, Qt.AlignVCenter)
        brand_row.addStretch(1)
        column_layout.addLayout(brand_row)

        column_layout.addSpacing(7)

        tagline = QLabel("Search the directory by name, phone number or e‑mail")
        tagline.setObjectName("appTagline")
        tagline.setAlignment(Qt.AlignCenter)
        column_layout.addWidget(tagline)

        column_layout.addSpacing(20)

        # --- search row -------------------------------------------------
        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(10)

        self.input = QLineEdit()
        self.input.setObjectName("searchField")
        self.input.setPlaceholderText("Search by name, phone number or e‑mail…")
        self.input.setClearButtonEnabled(True)
        self.input.addAction(icons.search_icon(18), QLineEdit.LeadingPosition)
        self.input.setFixedHeight(theme.CONTROL_HEIGHT)
        self.input.setMinimumWidth(220)
        self.input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.input.returnPressed.connect(self._on_submit)
        self.input.textChanged.connect(self._on_text_changed)
        search_row.addWidget(self.input, 1)

        self.search_btn = QPushButton("Search")
        self.search_btn.setObjectName("primaryButton")
        self.search_btn.setFixedHeight(theme.CONTROL_HEIGHT)
        self.search_btn.setMinimumWidth(116)
        self.search_btn.setCursor(Qt.PointingHandCursor)
        self.search_btn.setDefault(True)
        self.search_btn.setAutoDefault(True)
        self.search_btn.clicked.connect(self._on_submit)
        search_row.addWidget(self.search_btn)

        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setObjectName("ghostButton")
        self.clear_btn.setFixedHeight(theme.CONTROL_HEIGHT)
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.clicked.connect(self._on_clear)
        search_row.addWidget(self.clear_btn)

        column_layout.addLayout(search_row)

        # --- inline hint (only used for the empty-query case) ----------
        self.hint = QLabel(" ")
        self.hint.setObjectName("searchHint")
        self.hint.setAlignment(Qt.AlignCenter)
        column_layout.addSpacing(9)
        column_layout.addWidget(self.hint)

    # ------------------------------------------------------------------ #
    # Slots
    # ------------------------------------------------------------------ #
    def _on_text_changed(self, _text: str) -> None:
        # Clear any previously shown "type something" hint as soon as the user types.
        if self.hint.text().strip():
            self.hint.setText(" ")

    def _on_submit(self) -> None:
        text = self.input.text().strip()
        if not text:
            self.hint.setText("Type a name, phone number or e‑mail address to search.")
            self.input.setFocus()
            return
        self.hint.setText(" ")
        self.submitted.emit(text)

    def _on_clear(self) -> None:
        self.input.clear()
        self.hint.setText(" ")
        self.input.setFocus()
        self.cleared.emit()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def query_text(self) -> str:
        """The current trimmed query text."""
        return self.input.text().strip()

    def set_query_text(self, text: str) -> None:
        self.input.setText(text or "")

    def focus_input(self) -> None:
        self.input.setFocus()
        self.input.selectAll()

    def set_busy(self, busy: bool) -> None:
        """Disable the controls while a search is running."""
        self.input.setEnabled(not busy)
        self.search_btn.setEnabled(not busy)
        self.clear_btn.setEnabled(not busy)
        self.search_btn.setText("Searching…" if busy else "Search")