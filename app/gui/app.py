"""GUI bootstrap — create the :class:`QApplication`, apply the theme, show the
main window.

Importing this module has no side effects; call :func:`run` (or
:func:`create_application` if you want to drive the event loop yourself).
"""
from __future__ import annotations

import sys
from typing import Optional

from PySide6.QtWidgets import QApplication

from app.config.logging_config import get_logger
from app.config.settings import settings
from app.gui import icons, theme
from app.gui.main_window import MainWindow

logger = get_logger("gui.app")


def create_application(argv: Optional[list[str]] = None) -> tuple[QApplication, MainWindow]:
    """Create (or reuse) the :class:`QApplication`, apply the theme, build the window.

    Does **not** enter the Qt event loop.  Returns ``(app, window)`` — the window
    is created but not yet shown.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication(argv if argv is not None else sys.argv)
    app.setApplicationName(settings.app_name)
    app.setApplicationVersion(settings.app_version)
    app.setOrganizationName("OfflineApps")
    app.setWindowIcon(icons.app_icon())
    theme.apply_theme(app)

    window = MainWindow()
    return app, window


def run(argv: Optional[list[str]] = None) -> int:
    """Launch the desktop application and block until it exits; return the exit code."""
    settings.ensure_dirs()
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)
    app, window = create_application(argv)
    window.show()
    exit_code = int(app.exec())
    logger.info("Application event loop finished (exit code %s)", exit_code)
    return exit_code
