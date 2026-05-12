"""The non-result "states" shown in the centre of the window:

* :class:`MessageState` — a centred glyph badge + title + body (used for the
  initial prompt and the "no results" message).
* :class:`LoadingState` — a centred spinner + "Searching…" message.

Both are plain, dependency-light widgets so they can be reused anywhere.
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QPointF, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QRadialGradient
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.gui import icons, theme
from app.gui.widgets.spinner import Spinner

# A "glyph painter" draws the badge's foreground into the given rect.
GlyphPainter = Callable[[QPainter, QRect], None]


def _default_glyph(painter: QPainter, rect: QRect) -> None:
    icons.paint_magnifier(painter, rect, theme.ACCENT)


class _GlyphBadge(QWidget):
    """A soft, gently-graded circular badge with a vector glyph in its centre."""

    def __init__(self, glyph: Optional[GlyphPainter] = None, diameter: int = 88,
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._diameter = diameter
        self._glyph: GlyphPainter = glyph or _default_glyph
        self.setFixedSize(diameter, diameter)

    def set_glyph(self, glyph: Optional[GlyphPainter]) -> None:
        self._glyph = glyph or _default_glyph
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        gradient = QRadialGradient(QPointF(rect.center()) - QPointF(0, rect.height() * 0.20),
                                   rect.width() * 0.85)
        gradient.setColorAt(0.0, QColor(theme.ACCENT_TINT))
        gradient.setColorAt(1.0, QColor(theme.ACCENT_SOFT))
        painter.setPen(Qt.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(rect)

        painter.save()
        self._glyph(painter, rect)
        painter.restore()
        painter.end()


def _centered(widget: QLabel, max_width: int) -> QWidget:
    """Wrap *widget* in a horizontally-centred row capped at *max_width*."""
    widget.setMaximumWidth(max_width)
    row = QWidget()
    box = QHBoxLayout(row)
    box.setContentsMargins(0, 0, 0, 0)
    box.addStretch(1)
    box.addWidget(widget)
    box.addStretch(1)
    return row


class MessageState(QWidget):
    """A centred empty/info state: glyph badge, title, supporting text."""

    def __init__(self, glyph: Optional[GlyphPainter] = None, title: str = "", body: str = "",
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        col = QVBoxLayout(self)
        col.setContentsMargins(48, 40, 48, 40)
        col.setSpacing(0)
        col.addStretch(3)

        self._badge = _GlyphBadge(glyph, 88)
        col.addWidget(self._badge, 0, Qt.AlignHCenter)
        col.addSpacing(24)

        self._title = QLabel(title)
        self._title.setObjectName("stateTitle")
        self._title.setAlignment(Qt.AlignCenter)
        col.addWidget(self._title)
        col.addSpacing(10)

        self._body = QLabel(body)
        self._body.setObjectName("stateBody")
        self._body.setAlignment(Qt.AlignCenter)
        self._body.setWordWrap(True)
        col.addWidget(_centered(self._body, 420))

        col.addStretch(4)

    def configure(self, glyph: Optional[GlyphPainter], title: str, body: str) -> None:
        """Update the glyph, title and body text."""
        self._badge.set_glyph(glyph)
        self._title.setText(title)
        self._body.setText(body)


class LoadingState(QWidget):
    """A centred spinner with a status line."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        col = QVBoxLayout(self)
        col.setContentsMargins(48, 40, 48, 40)
        col.setSpacing(0)
        col.addStretch(3)

        self.spinner = Spinner(46, 4)
        col.addWidget(self.spinner, 0, Qt.AlignHCenter)
        col.addSpacing(24)

        self._label = QLabel("Searching…")
        self._label.setObjectName("stateTitle")
        self._label.setAlignment(Qt.AlignCenter)
        col.addWidget(self._label)
        col.addSpacing(8)

        self._sub = QLabel("")
        self._sub.setObjectName("stateQuery")
        self._sub.setAlignment(Qt.AlignCenter)
        self._sub.setWordWrap(True)
        col.addWidget(_centered(self._sub, 440))

        col.addStretch(4)

    def start(self, query: str = "") -> None:
        """Begin the animation; *query* is shown as supporting text."""
        self._label.setText("Searching…")
        self._sub.setText(f"Looking for “{query}”" if query else "")
        self.spinner.start()

    def stop(self) -> None:
        """Stop the animation (call when the loading state is hidden)."""
        self.spinner.stop()