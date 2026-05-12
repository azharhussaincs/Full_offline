"""Application logging configuration.

Call :func:`configure_logging` exactly once at start-up.  Everywhere else use
:func:`get_logger` to obtain a namespaced child logger (``app.<name>``).

Two handlers are installed on the ``app`` logger:

* a :class:`~logging.handlers.RotatingFileHandler` writing to ``<LOG_DIR>/app.log``
  (5 × 2 MB rotation), and
* a console (``stderr``) handler.

``propagate`` is disabled so messages are not duplicated by the root logger.
"""
from __future__ import annotations

import logging
import logging.handlers
from typing import Optional

from app.config.settings import settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-28s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_ROOT_NAME = "app"
_configured = False


def configure_logging(level: Optional[str] = None) -> logging.Logger:
    """Configure and return the application's root logger (idempotent).

    Args:
        level: optional level name overriding ``settings.log_level``.

    Returns:
        The configured ``logging.Logger`` named ``"app"``.
    """
    global _configured
    root = logging.getLogger(_ROOT_NAME)
    if _configured:
        return root

    settings.ensure_dirs()
    level_name = (level or settings.log_level or "INFO").upper()
    log_level = getattr(logging, level_name, logging.INFO)
    root.setLevel(log_level)

    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    file_handler = logging.handlers.RotatingFileHandler(
        filename=settings.log_dir / "app.log",
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(console_handler)
    root.propagate = False

    _configured = True
    root.debug("Logging configured (level=%s, file=%s)", level_name, settings.log_dir / "app.log")
    return root


def get_logger(name: str) -> logging.Logger:
    """Return a child logger named ``app.<name>`` (creates the namespace lazily)."""
    return logging.getLogger(f"{_ROOT_NAME}.{name}")
