"""The thin footer strip: a "results" summary on the left and a small status
indicator (a coloured dot + word) on the right.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget

from app.gui import theme

# status name -> dot colour
_STATUS_COLORS = {
    "neutral": theme.TEXT_MUTED,
    "busy": theme.WARNING,
    "ok": theme.SUCCESS,
    "error": theme.DANGER,
}


class _Dot(QWidget):
    """A small filled circle with a soft halo, used as a status indicator."""

    def __init__(self, color: str = theme.TEXT_MUTED, diameter: int = 8,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._color = QColor(color)
        self._diameter = diameter
        self.setFixedSize(diameter + 8, diameter + 8)

    def set_color(self, color: str) -> None:
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        cx, cy = self.width() / 2, self.height() / 2

        halo = QColor(self._color)
        halo.setAlpha(40)
        painter.setBrush(halo)
        painter.drawEllipse(self.rect())

        painter.setBrush(self._color)
        r = self._diameter / 2
        painter.drawEllipse(int(cx - r), int(cy - r), self._diameter, self._diameter)
        painter.end()


class StatusFooter(QFrame):
    """A 1-line footer with a results summary and a connection/status badge."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("footerBar")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.setFixedHeight(40)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(theme.PAGE_GUTTER, 0, theme.PAGE_GUTTER - 6, 0)
        layout.setSpacing(8)

        self._total = QLabel("")
        self._total.setObjectName("footerTotal")
        layout.addWidget(self._total)

        layout.addStretch(1)

        self._dot = _Dot(theme.TEXT_MUTED, 8)
        layout.addWidget(self._dot)
        self._status = QLabel("Starting…")
        self._status.setObjectName("footerStatus")
        layout.addWidget(self._status)

    # ------------------------------------------------------------------ #
    def set_results_summary(self, text: str) -> None:
        """Set the left-hand summary text (e.g. ``"Showing 20 of 1,284 matches"``)."""
        self._total.setText(text or "")

    def clear_results_summary(self) -> None:
        self._total.setText("")

    def set_status(self, text: str, state: str = "neutral") -> None:
        """Set the right-hand status word; *state* ∈ {neutral, busy, ok, error}."""
        self._status.setText(text or "")
        self._dot.set_color(_STATUS_COLORS.get(state, theme.TEXT_MUTED))