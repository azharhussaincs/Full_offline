"""The application's visual theme — a clean, premium *light* theme.

Everything visual lives here: the colour tokens, the base font, the layout
metrics and the global Qt Style Sheet.  Call :func:`apply_theme` once on the
:class:`QApplication`.

Design intent: a calm, modern SaaS surface — generous whitespace, a single
indigo accent, hair-line dividers, soft shadows, large rounded corners and an
unhurried type scale.  Nothing technical ever reaches the screen.
"""
from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

# --------------------------------------------------------------------------- #
# Colour tokens
# --------------------------------------------------------------------------- #
BG_APP = "#f5f6f9"          # window background — soft, cool off-white
BG_CANVAS = "#f5f6f9"       # the scrollable results canvas
BG_SURFACE = "#ffffff"      # cards, header, footer, inputs
BG_SUBTLE = "#f0f1f5"       # subtle fills (hover, badges, track)
BG_ELEVATED = "#fbfbfd"     # a barely-there elevated tint

BORDER = "#e8eaf0"          # hair-line borders / dividers
BORDER_STRONG = "#d8dbe4"   # input borders, more present
BORDER_FOCUS = "#bcb9f3"    # ring shown around a focused input

TEXT_PRIMARY = "#171a21"    # near-black, slightly warm
TEXT_BODY = "#3a4150"       # body / values
TEXT_SECONDARY = "#5b6373"  # secondary copy
TEXT_MUTED = "#949bab"      # captions, labels, hints
TEXT_FAINT = "#b4bac6"      # the faintest readable grey

ACCENT = "#4f46e5"          # indigo — the one accent
ACCENT_HOVER = "#5b52ef"    # lighter on hover
ACCENT_PRESSED = "#3f37c5"  # darker when pressed
ACCENT_SOFT = "#eceafe"     # very light indigo (fills / badges)
ACCENT_TINT = "#f4f4ff"     # the faintest indigo wash
ACCENT_BORDER = "#dedbfb"   # border for soft-accent surfaces

SUCCESS = "#15a35b"
WARNING = "#d98c0c"
DANGER = "#dc4040"

ON_ACCENT = "#ffffff"
ON_ACCENT_DISABLED = "#f1f0ff"
ACCENT_DISABLED = "#c4c1f0"

# Shadow colours (used with QGraphicsDropShadowEffect)
SHADOW_CARD = QColor(23, 26, 33, 26)
SHADOW_CARD_HOVER = QColor(23, 26, 33, 40)
SHADOW_ACCENT = QColor(79, 70, 229, 90)

# Avatar palette — soft, distinct, harmonious hues.
AVATAR_COLORS = (
    "#6366f1", "#0ea5e9", "#0d9488", "#16a34a", "#d97706",
    "#dc4040", "#db2777", "#7c3aed", "#ea580c", "#2563eb",
)

# --------------------------------------------------------------------------- #
# Layout metrics — kept in one place so spacing stays consistent everywhere.
# --------------------------------------------------------------------------- #
CONTENT_MAX_WIDTH = 760     # max width of the cards column
SEARCH_MAX_WIDTH = 680      # max width of the hero search column
PAGE_GUTTER = 32            # left/right padding of the main content
CONTROL_HEIGHT = 50         # search field / button height
RADIUS_LG = 18              # cards
RADIUS_MD = 14              # inputs, buttons
RADIUS_SM = 10              # small chips


# --------------------------------------------------------------------------- #
# Stylesheet
# --------------------------------------------------------------------------- #
def _stylesheet() -> str:
    return f"""
* {{
    font-family: "Inter", "SF Pro Text", "SF Pro Display", "Segoe UI",
                 "Helvetica Neue", "Noto Sans", "Cantarell", "DejaVu Sans", sans-serif;
    font-size: 14px;
    color: {TEXT_PRIMARY};
    outline: 0;
}}
QMainWindow, QDialog {{ background: {BG_APP}; }}
#rootSurface {{ background: {BG_APP}; }}

/* ---------- header (the hero) ---------- */
#headerBar {{
    background: {BG_SURFACE};
    border-bottom: 1px solid {BORDER};
}}
#appTitle {{
    font-size: 22px;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    letter-spacing: 0.2px;
}}
#appTagline {{
    font-size: 14px;
    color: {TEXT_MUTED};
    letter-spacing: 0.1px;
}}

/* ---------- search field & buttons ---------- */
QLineEdit#searchField {{
    background: {BG_SURFACE};
    border: 1.5px solid {BORDER_STRONG};
    border-radius: {RADIUS_MD}px;
    padding: 0 16px 0 14px;
    font-size: 15.5px;
    color: {TEXT_PRIMARY};
    selection-background-color: {ACCENT};
    selection-color: {ON_ACCENT};
}}
QLineEdit#searchField:hover {{ border-color: #c6c9d4; }}
QLineEdit#searchField:focus {{
    border-color: {ACCENT};
    background: {BG_SURFACE};
}}
QLineEdit#searchField:disabled {{
    color: {TEXT_MUTED};
    background: {BG_SUBTLE};
    border-color: {BORDER};
}}

QPushButton#primaryButton {{
    background: {ACCENT};
    color: {ON_ACCENT};
    border: none;
    border-radius: {RADIUS_MD}px;
    padding: 0 28px;
    font-size: 14.5px;
    font-weight: 600;
    letter-spacing: 0.2px;
}}
QPushButton#primaryButton:hover {{ background: {ACCENT_HOVER}; }}
QPushButton#primaryButton:pressed {{ background: {ACCENT_PRESSED}; }}
QPushButton#primaryButton:disabled {{ background: {ACCENT_DISABLED}; color: {ON_ACCENT_DISABLED}; }}

QPushButton#ghostButton {{
    background: {BG_SURFACE};
    color: {TEXT_SECONDARY};
    border: 1.5px solid {BORDER_STRONG};
    border-radius: {RADIUS_MD}px;
    padding: 0 22px;
    font-size: 14.5px;
    font-weight: 600;
}}
QPushButton#ghostButton:hover {{ background: {BG_SUBTLE}; color: {TEXT_PRIMARY}; border-color: #c6c9d4; }}
QPushButton#ghostButton:pressed {{ background: #e6e7ee; }}
QPushButton#ghostButton:disabled {{ color: {TEXT_FAINT}; border-color: {BORDER}; background: {BG_SURFACE}; }}

QPushButton#softButton {{
    background: {ACCENT_SOFT};
    color: {ACCENT};
    border: 1px solid {ACCENT_BORDER};
    border-radius: {RADIUS_MD}px;
    padding: 11px 24px;
    font-size: 14px;
    font-weight: 600;
}}
QPushButton#softButton:hover {{ background: #e3e0fd; border-color: #d2cefa; }}
QPushButton#softButton:pressed {{ background: #d8d4fb; }}
QPushButton#softButton:disabled {{ color: {TEXT_FAINT}; border-color: {BORDER}; background: {BG_SUBTLE}; }}

QLabel#searchHint {{ color: {TEXT_MUTED}; font-size: 13px; }}

/* ---------- results toolbar (export) ---------- */
QLabel#resultsCaption {{ color: {TEXT_MUTED}; font-size: 13px; }}
QPushButton#exportButton {{
    background: {BG_SURFACE};
    color: {TEXT_SECONDARY};
    border: 1px solid {BORDER_STRONG};
    border-radius: 9px;
    padding: 7px 13px;
    font-size: 12.5px;
    font-weight: 600;
}}
QPushButton#exportButton:hover {{ background: {BG_SUBTLE}; color: {TEXT_PRIMARY}; border-color: #c6c9d4; }}
QPushButton#exportButton:pressed {{ background: #e6e7ee; }}
QPushButton#exportButton:disabled {{ color: {TEXT_FAINT}; border-color: {BORDER}; background: {BG_SURFACE}; }}

/* ---------- result cards ---------- */
QFrame#card {{
    background: {BG_SURFACE};
    border: 1px solid {BORDER};
    border-radius: {RADIUS_LG}px;
}}
QFrame#card:hover {{ border-color: #dbdee7; }}
QLabel#cardName {{
    font-size: 18.5px;
    font-weight: 700;
    color: {TEXT_PRIMARY};
    letter-spacing: 0.1px;
}}
QLabel#cardSubtitle {{ font-size: 13px; color: {TEXT_MUTED}; }}
QFrame#cardDivider {{ background: {BORDER}; border: none; }}
QLabel#fieldLabel {{
    font-size: 12.5px;
    font-weight: 600;
    color: {TEXT_MUTED};
}}
QLabel#fieldValue {{ font-size: 14.5px; color: {TEXT_BODY}; }}
QLabel#fieldValueEmpty {{ font-size: 14px; color: {TEXT_FAINT}; font-style: italic; }}

/* ---------- empty / loading states ---------- */
QLabel#stateTitle {{ font-size: 19.5px; font-weight: 700; color: {TEXT_PRIMARY}; }}
QLabel#stateBody  {{ font-size: 14.5px; color: {TEXT_MUTED}; }}
QLabel#stateQuery {{ font-size: 14.5px; color: {TEXT_SECONDARY}; }}

/* ---------- footer ---------- */
#footerBar {{
    background: {BG_SURFACE};
    border-top: 1px solid {BORDER};
}}
QLabel#footerTotal {{ font-size: 13px; color: {TEXT_SECONDARY}; }}
QLabel#footerStatus {{ font-size: 13px; color: {TEXT_MUTED}; }}

/* ---------- scroll area ---------- */
QScrollArea {{ background: transparent; border: none; }}
QScrollArea > QWidget > QWidget {{ background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 14px; margin: 6px 4px 6px 0; }}
QScrollBar::handle:vertical {{
    background: #d3d6df; min-height: 40px; border-radius: 5px;
}}
QScrollBar::handle:vertical:hover {{ background: #c0c4cf; }}
QScrollBar::handle:vertical:pressed {{ background: #b1b6c2; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: transparent; }}
QScrollBar:horizontal {{ height: 0; }}

/* ---------- tooltips / message boxes ---------- */
QToolTip {{
    background: {TEXT_PRIMARY}; color: {ON_ACCENT}; border: none;
    padding: 6px 10px; border-radius: 8px; font-size: 12.5px;
}}
QMessageBox {{ background: {BG_SURFACE}; }}
QMessageBox QLabel {{ color: {TEXT_PRIMARY}; font-size: 14px; }}
QMessageBox QPushButton {{
    background: {ACCENT}; color: {ON_ACCENT}; border: none; border-radius: 10px;
    padding: 8px 20px; font-weight: 600; min-width: 80px;
}}
QMessageBox QPushButton:hover {{ background: {ACCENT_HOVER}; }}
QMessageBox QPushButton:pressed {{ background: {ACCENT_PRESSED}; }}
"""


def _pick_base_font() -> QFont:
    """Pick a clean UI font, preferring Inter, then common system sans fonts."""
    families = set(QFontDatabase.families())
    for candidate in ("Inter", "SF Pro Text", "SF Pro Display", "Segoe UI",
                      "Helvetica Neue", "Noto Sans", "Cantarell", "Ubuntu", "DejaVu Sans"):
        if candidate in families:
            font = QFont(candidate)
            break
    else:
        font = QFont()
    font.setPixelSize(14)
    font.setHintingPreference(QFont.PreferFullHinting)
    return font


def apply_theme(app: QApplication) -> None:
    """Apply the premium light theme (style, font and stylesheet) to *app*."""
    app.setStyle("Fusion")
    app.setFont(_pick_base_font())
    app.setStyleSheet(_stylesheet())
