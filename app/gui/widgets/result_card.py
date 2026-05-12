"""A single search result rendered as a clean, premium profile card.

Layout::

    ┌──────────────────────────────────────────────────────────┐
    │  ╭────╮   Ali Khan                                       │
    │  │ AK │   ────────────────────────────────────────────   │
    │  ╰────╯   📞  Phone      0300 1234567                    │
    │           ✉   Email      ali.khan@gmail.com             │
    │           📍  Address    Gulberg III, Lahore, Pakistan  │
    └──────────────────────────────────────────────────────────┘

Each row is ``icon · label · value`` on a fixed grid so every value lines up;
values wrap cleanly, never collide, and are selectable (so a phone number or
e‑mail can be copied).  No ``_id`` / ``_score`` / ``_index`` or any other
technical data ever appears here.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.gui import icons, theme
from app.gui.widgets.avatar import Avatar
from app.models.profile import Profile

_ICON_COL_WIDTH = 22
_LABEL_COL_WIDTH = 90


class ResultCard(QFrame):
    """An elegant, self-contained card for one :class:`Profile`."""

    def __init__(self, profile: Profile, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setAttribute(Qt.WA_Hover, True)

        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(28)
        self._shadow.setXOffset(0)
        self._shadow.setYOffset(10)
        self._shadow.setColor(theme.SHADOW_CARD)
        self.setGraphicsEffect(self._shadow)

        outer = QHBoxLayout(self)
        outer.setContentsMargins(24, 22, 26, 24)
        outer.setSpacing(20)

        # --- avatar (top-aligned) ---------------------------------------
        avatar_col = QVBoxLayout()
        avatar_col.setContentsMargins(0, 2, 0, 0)
        avatar_col.setSpacing(0)
        avatar_col.addWidget(Avatar(profile.display_name, 52))
        avatar_col.addStretch(1)
        outer.addLayout(avatar_col)

        # --- text column ------------------------------------------------
        text_col = QVBoxLayout()
        text_col.setContentsMargins(0, 0, 0, 0)
        text_col.setSpacing(0)

        name_label = QLabel(profile.display_name)
        name_label.setObjectName("cardName")
        name_label.setWordWrap(True)
        name_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        text_col.addWidget(name_label)

        if profile.fields:
            divider = QFrame()
            divider.setObjectName("cardDivider")
            divider.setFixedHeight(1)
            divider.setFrameShape(QFrame.NoFrame)
            text_col.addSpacing(15)
            text_col.addWidget(divider)
            text_col.addSpacing(15)

            grid = QGridLayout()
            grid.setHorizontalSpacing(10)
            grid.setVerticalSpacing(12)
            grid.setContentsMargins(0, 0, 0, 0)
            for row, item in enumerate(profile.fields):
                glyph = QLabel()
                glyph.setPixmap(icons.field_icon(item.label, 16).pixmap(16, 16))
                glyph.setFixedWidth(_ICON_COL_WIDTH)
                glyph.setAlignment(Qt.AlignLeft | Qt.AlignTop)
                glyph.setContentsMargins(0, 2, 0, 0)

                label = QLabel(item.label)
                label.setObjectName("fieldLabel")
                label.setMinimumWidth(_LABEL_COL_WIDTH)
                label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
                label.setContentsMargins(0, 1, 0, 0)

                value = QLabel(item.value)
                value.setObjectName("fieldValue")
                value.setWordWrap(True)
                value.setTextInteractionFlags(Qt.TextSelectableByMouse)
                value.setAlignment(Qt.AlignLeft | Qt.AlignTop)

                grid.addWidget(glyph, row, 0, Qt.AlignTop)
                grid.addWidget(label, row, 1, Qt.AlignTop)
                grid.addWidget(value, row, 2)
            grid.setColumnStretch(2, 1)
            text_col.addLayout(grid)
        else:
            text_col.addSpacing(8)
            empty = QLabel("No additional details available.")
            empty.setObjectName("fieldValueEmpty")
            text_col.addWidget(empty)

        text_col.addStretch(1)
        outer.addLayout(text_col, 1)

    # ------------------------------------------------------------------ #
    # A gentle "lift" on hover.
    # ------------------------------------------------------------------ #
    def enterEvent(self, event) -> None:  # noqa: N802 - Qt override
        self._shadow.setBlurRadius(34)
        self._shadow.setYOffset(14)
        self._shadow.setColor(theme.SHADOW_CARD_HOVER)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:  # noqa: N802 - Qt override
        self._shadow.setBlurRadius(28)
        self._shadow.setYOffset(10)
        self._shadow.setColor(theme.SHADOW_CARD)
        super().leaveEvent(event)