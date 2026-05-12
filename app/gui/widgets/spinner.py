"""A lightweight, smooth, indeterminate loading spinner (a rotating arc).

Pure-Qt — no extra dependencies, no GIFs.  Stop it when you hide it so the
timer is not left running.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from app.gui import theme


class Spinner(QWidget):
    """An indeterminate circular spinner — a soft track with a rotating accent arc."""

    def __init__(self, diameter: int = 40, line_width: int = 4,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._diameter = diameter
        self._line_width = line_width
        self._angle = 0
        self.setFixedSize(diameter, diameter)
        self._timer = QTimer(self)
        self._timer.setInterval(16)  # ~60 fps
        self._timer.timeout.connect(self._advance)

    # ------------------------------------------------------------------ #
    def start(self) -> None:
        """Start animating and show the widget."""
        if not self._timer.isActive():
            self._timer.start()
        self.show()

    def stop(self) -> None:
        """Stop animating and hide the widget."""
        self._timer.stop()
        self.hide()

    # ------------------------------------------------------------------ #
    def _advance(self) -> None:
        self._angle = (self._angle + 5) % 360
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        margin = self._line_width + 1
        rect = self.rect().adjusted(margin, margin, -margin, -margin)

        track_pen = QPen(QColor(theme.BG_SUBTLE), self._line_width, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(track_pen)
        painter.drawEllipse(rect)

        arc_pen = QPen(QColor(theme.ACCENT), self._line_width, Qt.SolidLine, Qt.RoundCap)
        painter.setPen(arc_pen)
        # Qt angles are in 1/16th degrees; sweep ~95°, rotating clockwise.
        painter.drawArc(rect, int(-self._angle * 16), int(95 * 16))
        painter.end()