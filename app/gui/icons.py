"""Tiny programmatically-drawn icons — no image asset files required.

Every icon is a crisp, minimal line glyph (rounded caps, ~1.6px stroke at 16px)
so they sit quietly next to text.  Helpers return ``QIcon``; ``logo_pixmap`` and
``app_icon`` return the product mark (a rounded indigo tile with a magnifier).
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (
    QBrush,
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

from app.gui import theme

_DPR = 2  # render at 2x for crispness on HiDPI screens


# --------------------------------------------------------------------------- #
# Low-level helpers
# --------------------------------------------------------------------------- #
def _canvas(size: int) -> tuple[QPixmap, QPainter]:
    pixmap = QPixmap(size * _DPR, size * _DPR)
    pixmap.setDevicePixelRatio(_DPR)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    return pixmap, painter


def _stroke(painter: QPainter, color: QColor, size: int) -> QPen:
    pen = QPen(color)
    pen.setWidthF(max(1.25, size * 0.105))
    pen.setCapStyle(Qt.RoundCap)
    pen.setJoinStyle(Qt.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    return pen


def _magnifier(painter: QPainter, size: float, color: QColor, stroke_ratio: float = 0.11) -> None:
    """Draw a magnifying-glass outline that fills a *size* × *size* box."""
    pen = QPen(color)
    pen.setWidthF(max(1.2, size * stroke_ratio))
    pen.setCapStyle(Qt.RoundCap)
    painter.setPen(pen)
    painter.setBrush(Qt.NoBrush)
    cx, cy = size * 0.42, size * 0.42
    radius = size * 0.255
    painter.drawEllipse(QPointF(cx, cy), radius, radius)
    angle = math.radians(45)
    x1 = cx + radius * math.cos(angle)
    y1 = cy + radius * math.sin(angle)
    painter.drawLine(QPointF(x1, y1), QPointF(size * 0.86, size * 0.86))


# --------------------------------------------------------------------------- #
# Field glyphs (used inside result cards)
# --------------------------------------------------------------------------- #
def _draw_person(p: QPainter, s: int) -> None:
    _stroke(p, p.pen().color(), s)
    head_r = s * 0.155
    p.drawEllipse(QPointF(s * 0.5, s * 0.34), head_r, head_r)
    path = QPainterPath()
    path.moveTo(s * 0.20, s * 0.84)
    path.cubicTo(s * 0.20, s * 0.58, s * 0.80, s * 0.58, s * 0.80, s * 0.84)
    p.drawPath(path)


def _draw_phone(p: QPainter, s: int) -> None:
    _stroke(p, p.pen().color(), s)
    rect = QRectF(s * 0.30, s * 0.11, s * 0.40, s * 0.78)
    p.drawRoundedRect(rect, s * 0.105, s * 0.105)
    p.drawLine(QPointF(s * 0.435, s * 0.205), QPointF(s * 0.565, s * 0.205))  # earpiece
    p.drawLine(QPointF(s * 0.445, s * 0.785), QPointF(s * 0.555, s * 0.785))  # home indicator


def _draw_mail(p: QPainter, s: int) -> None:
    _stroke(p, p.pen().color(), s)
    rect = QRectF(s * 0.13, s * 0.24, s * 0.74, s * 0.52)
    p.drawRoundedRect(rect, s * 0.08, s * 0.08)
    flap = QPainterPath()
    flap.moveTo(rect.left() + s * 0.02, rect.top() + s * 0.04)
    flap.lineTo(rect.center().x(), rect.top() + rect.height() * 0.52)
    flap.lineTo(rect.right() - s * 0.02, rect.top() + s * 0.04)
    p.drawPath(flap)


def _draw_pin(p: QPainter, s: int) -> None:
    _stroke(p, p.pen().color(), s)
    cx, cy, r = s * 0.5, s * 0.40, s * 0.225
    path = QPainterPath()
    path.moveTo(cx, s * 0.86)
    # left side up to the bulb, around the top, back down the right side.
    path.quadTo(cx - r * 1.05, cy + r * 0.7, cx - r, cy)
    path.arcTo(QRectF(cx - r, cy - r, 2 * r, 2 * r), 180, -180)
    path.quadTo(cx + r * 1.05, cy + r * 0.7, cx, s * 0.86)
    p.drawPath(path)
    inner = s * 0.075
    p.drawEllipse(QPointF(cx, cy), inner, inner)


def _draw_id(p: QPainter, s: int) -> None:
    _stroke(p, p.pen().color(), s)
    rect = QRectF(s * 0.13, s * 0.24, s * 0.74, s * 0.52)
    p.drawRoundedRect(rect, s * 0.09, s * 0.09)
    hr = s * 0.075
    p.drawEllipse(QPointF(s * 0.34, s * 0.42), hr, hr)
    body = QPainterPath()
    body.moveTo(s * 0.24, s * 0.62)
    body.quadTo(s * 0.34, s * 0.50, s * 0.44, s * 0.62)
    p.drawPath(body)
    p.drawLine(QPointF(s * 0.54, s * 0.40), QPointF(s * 0.76, s * 0.40))
    p.drawLine(QPointF(s * 0.54, s * 0.52), QPointF(s * 0.76, s * 0.52))
    p.drawLine(QPointF(s * 0.54, s * 0.62), QPointF(s * 0.70, s * 0.62))


def _draw_calendar(p: QPainter, s: int) -> None:
    _stroke(p, p.pen().color(), s)
    rect = QRectF(s * 0.16, s * 0.20, s * 0.68, s * 0.62)
    p.drawRoundedRect(rect, s * 0.08, s * 0.08)
    p.drawLine(QPointF(rect.left(), s * 0.36), QPointF(rect.right(), s * 0.36))
    p.drawLine(QPointF(s * 0.34, s * 0.12), QPointF(s * 0.34, s * 0.26))
    p.drawLine(QPointF(s * 0.66, s * 0.12), QPointF(s * 0.66, s * 0.26))


def _draw_dot(p: QPainter, s: int) -> None:
    # The caller leaves the brush set to the requested colour.
    p.setPen(Qt.NoPen)
    r = s * 0.135
    p.drawEllipse(QPointF(s * 0.5, s * 0.5), r, r)


def _draw_download(p: QPainter, s: int) -> None:
    _stroke(p, p.pen().color(), s)
    # shaft + arrowhead
    p.drawLine(QPointF(s * 0.5, s * 0.12), QPointF(s * 0.5, s * 0.60))
    arrow = QPainterPath()
    arrow.moveTo(s * 0.30, s * 0.42)
    arrow.lineTo(s * 0.5, s * 0.62)
    arrow.lineTo(s * 0.70, s * 0.42)
    p.drawPath(arrow)
    # tray
    tray = QPainterPath()
    tray.moveTo(s * 0.18, s * 0.66)
    tray.lineTo(s * 0.18, s * 0.84)
    tray.lineTo(s * 0.82, s * 0.84)
    tray.lineTo(s * 0.82, s * 0.66)
    p.drawPath(tray)


_FIELD_DRAWERS = {
    "name": _draw_person,
    "phone": _draw_phone,
    "mobile": _draw_phone,
    "email": _draw_mail,
    "e-mail": _draw_mail,
    "address": _draw_pin,
    "city": _draw_pin,
    "country": _draw_pin,
    "location": _draw_pin,
    "cnic": _draw_id,
    "nic": _draw_id,
    "id": _draw_id,
    "passport": _draw_id,
    "national id": _draw_id,
    "date of birth": _draw_calendar,
    "dob": _draw_calendar,
    "age": _draw_calendar,
}


def _drawer_for(label: str):
    key = (label or "").strip().lower()
    if key in _FIELD_DRAWERS:
        return _FIELD_DRAWERS[key]
    for token, drawer in _FIELD_DRAWERS.items():
        if token in key:
            return drawer
    return _draw_dot


def field_icon(label: str, size: int = 16, color: str = theme.TEXT_MUTED) -> QIcon:
    """A small monochrome line glyph appropriate for the *label* of a card row."""
    pixmap, painter = _canvas(size)
    painter.setPen(QColor(color))
    painter.setBrush(QColor(color))
    _drawer_for(label)(painter, size)
    painter.end()
    return QIcon(pixmap)


# --------------------------------------------------------------------------- #
# Search glyph + product mark
# --------------------------------------------------------------------------- #
def search_icon(size: int = 18, color: str = theme.TEXT_MUTED) -> QIcon:
    """A small search glyph for use inside the search field."""
    pixmap, painter = _canvas(size)
    _magnifier(painter, float(size), QColor(color))
    painter.end()
    return QIcon(pixmap)


def download_icon(size: int = 14, color: str = theme.TEXT_SECONDARY) -> QIcon:
    """A small "download" glyph (arrow into a tray) for the export buttons."""
    pixmap, painter = _canvas(size)
    painter.setPen(QColor(color))
    painter.setBrush(QColor(color))
    _draw_download(painter, size)
    painter.end()
    return QIcon(pixmap)


def paint_magnifier(painter: QPainter, rect, color: str = theme.ACCENT, frac: float = 0.46) -> None:
    """Paint a centred magnifier glyph inside *rect* (used by the state badges)."""
    side = min(rect.width(), rect.height()) * frac
    painter.save()
    painter.translate(rect.center().x() - side / 2.0, rect.center().y() - side / 2.0)
    _magnifier(painter, side, QColor(color), stroke_ratio=0.125)
    painter.restore()


def _draw_logo_tile(painter: QPainter, size: int) -> None:
    radius = size * 0.255
    gradient = QLinearGradient(0, 0, size, size)
    gradient.setColorAt(0.0, QColor("#6f67ec"))
    gradient.setColorAt(1.0, QColor(theme.ACCENT))
    painter.setPen(Qt.NoPen)
    painter.setBrush(QBrush(gradient))
    painter.drawRoundedRect(QRectF(0, 0, size, size), radius, radius)
    # subtle top sheen
    sheen = QLinearGradient(0, 0, 0, size)
    sheen.setColorAt(0.0, QColor(255, 255, 255, 46))
    sheen.setColorAt(0.5, QColor(255, 255, 255, 0))
    painter.setBrush(QBrush(sheen))
    painter.drawRoundedRect(QRectF(0, 0, size, size), radius, radius)
    painter.save()
    painter.translate(size * 0.205, size * 0.205)
    _magnifier(painter, size * 0.59, QColor("#ffffff"), stroke_ratio=0.118)
    painter.restore()


def logo_pixmap(size: int = 40) -> QPixmap:
    """The product mark as a pixmap (for placing inside the header)."""
    pixmap, painter = _canvas(size)
    _draw_logo_tile(painter, size)
    painter.end()
    return pixmap


def app_icon(size: int = 256) -> QIcon:
    """The window / taskbar icon: a rounded indigo tile with a white magnifier."""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    _draw_logo_tile(painter, size)
    painter.end()
    return QIcon(pixmap)