"""A circular monogram avatar — a soft, gently-graded disc with the person's
initials.

The colour is derived deterministically from the name, so the same person always
gets the same avatar.  Used in :class:`~app.gui.widgets.result_card.ResultCard`.
"""
from __future__ import annotations

import re
from typing import Optional

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QRadialGradient
from PySide6.QtWidgets import QWidget

from app.gui import theme


class Avatar(QWidget):
    """Fixed-size circular avatar showing up to two initials."""

    def __init__(self, name: str = "", diameter: int = 48, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._diameter = diameter
        self.setFixedSize(diameter, diameter)
        self._initials = "?"
        self._color = QColor(theme.AVATAR_COLORS[0])
        self.set_name(name)

    # ------------------------------------------------------------------ #
    def set_name(self, name: str) -> None:
        """Recompute the initials and colour from *name* and repaint."""
        clean = (name or "").strip()
        parts = [p for p in re.split(r"[\s._/\\-]+", clean) if p and p[0].isalnum()]
        if not parts or clean.lower() == "unknown":
            self._initials = "?"
        elif len(parts) == 1:
            self._initials = parts[0][:2].upper()
        else:
            self._initials = (parts[0][0] + parts[-1][0]).upper()

        seed = sum((i + 1) * ord(ch) for i, ch in enumerate(clean)) if clean else 0
        self._color = QColor(theme.AVATAR_COLORS[seed % len(theme.AVATAR_COLORS)])
        self.update()

    # ------------------------------------------------------------------ #
    def paintEvent(self, event) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()

        # Soft tinted disc with a barely-there top-left highlight.
        light = QColor(self._color)
        light.setAlpha(34)
        deep = QColor(self._color)
        deep.setAlpha(60)
        gradient = QRadialGradient(QPointF(rect.center()) - QPointF(rect.width() * 0.18, rect.height() * 0.22),
                                   rect.width() * 0.95)
        gradient.setColorAt(0.0, light)
        gradient.setColorAt(1.0, deep)
        painter.setPen(Qt.NoPen)
        painter.setBrush(gradient)
        painter.drawEllipse(rect)

        # Initials in the full-strength colour.
        painter.setPen(self._color)
        font = QFont(self.font())
        font.setBold(True)
        font.setPixelSize(max(11, int(self._diameter * 0.40)))
        painter.setFont(font)
        painter.drawText(rect, Qt.AlignCenter, self._initials)
        painter.end()