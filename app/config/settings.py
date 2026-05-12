"""Centralised application configuration.

Configuration is loaded **once** at import time from (in priority order):

1. real environment variables already exported in the shell, then
2. a ``.env`` file in the project root (via :mod:`python-dotenv`), then
3. the hard-coded defaults below.

The result is exposed as a single, immutable :class:`Settings` instance named
:data:`settings`.  No other module should read ``os.environ`` directly — import
``settings`` instead.  This keeps configuration in one place and makes the app
easy to test and to extend (e.g. for a future web/API front-end).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from dotenv import load_dotenv

# Project root = three levels up from this file (app/config/settings.py).
BASE_DIR: Final[Path] = Path(__file__).resolve().parents[2]


# --------------------------------------------------------------------------- #
# Helpers for safely coercing environment variables
# --------------------------------------------------------------------------- #
def _get_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "y"}


def _get_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        return default


def _resolve_path(value: str) -> Path:
    """Return *value* as an absolute :class:`~pathlib.Path` (relative to BASE_DIR)."""
    path = Path(value).expanduser()
    return path if path.is_absolute() else (BASE_DIR / path)


# --------------------------------------------------------------------------- #
# The settings object
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Settings:
    """Immutable, fully-resolved application configuration."""

    # --- Elasticsearch -----------------------------------------------------
    es_host: str
    es_username: str
    es_password: str
    es_index: str
    es_verify_certs: bool
    es_timeout: int

    # --- Application -------------------------------------------------------
    app_name: str
    app_version: str
    page_size: int

    # --- Logging ----------------------------------------------------------
    log_level: str
    log_dir: Path

    # --- Search history / exports -----------------------------------------
    history_file: Path
    history_max: int
    export_dir: Path

    # --- Misc -------------------------------------------------------------
    base_dir: Path

    # ------------------------------------------------------------------ #
    def ensure_dirs(self) -> None:
        """Create the directories the app writes to (logs / exports)."""
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def masked_password(self) -> str:
        """Return the password with all but the last character masked (for logs/UI)."""
        if not self.es_password:
            return ""
        if len(self.es_password) <= 2:
            return "*" * len(self.es_password)
        return "*" * (len(self.es_password) - 1) + self.es_password[-1]


def _load_settings() -> Settings:
    """Read ``.env`` (if present) and build the :class:`Settings` instance."""
    # ``override=False`` -> already-exported shell variables win over the file.
    load_dotenv(BASE_DIR / ".env", override=False)
    return Settings(
        es_host=os.getenv("ES_HOST", "https://localhost:9200").strip(),
        es_username=os.getenv("ES_USERNAME", "elastic"),
        es_password=os.getenv("ES_PASSWORD", "admin123"),
        es_index=os.getenv("ES_INDEX", "tc_index").strip(),
        es_verify_certs=_get_bool("ES_VERIFY_CERTS", False),
        es_timeout=max(1, _get_int("ES_TIMEOUT", 30)),
        app_name=os.getenv("APP_NAME", "PeopleFinder").strip() or "PeopleFinder",
        app_version="1.0.0",
        page_size=max(1, _get_int("APP_PAGE_SIZE", 20)),
        log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        log_dir=_resolve_path(os.getenv("LOG_DIR", "logs")),
        history_file=_resolve_path(os.getenv("HISTORY_FILE", "search_history.json")),
        history_max=max(1, _get_int("HISTORY_MAX", 50)),
        export_dir=_resolve_path(os.getenv("EXPORT_DIR", "exports")),
        base_dir=BASE_DIR,
    )


#: The process-wide configuration object.  Import this everywhere.
settings: Final[Settings] = _load_settings()
