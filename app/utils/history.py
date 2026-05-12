"""Persistent search-history store backed by a small JSON file on disk.

Each entry is a ``dict`` with keys ``text``, ``type``, ``total`` and
``timestamp``.  The list is de-duplicated (most-recent first) and capped at a
configurable maximum.  All public methods are thread-safe.
"""
from __future__ import annotations

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.config.logging_config import get_logger
from app.config.settings import settings

logger = get_logger("utils.history")


class SearchHistory:
    """A bounded, de-duplicated, most-recent-first list of past searches."""

    def __init__(self, path: Optional[Path] = None, max_items: Optional[int] = None) -> None:
        self.path: Path = Path(path) if path else settings.history_file
        self.max_items: int = max_items if max_items is not None else settings.history_max
        self._lock = threading.RLock()
        self._items: list[dict] = []
        self.load()

    # ----------------------------------------------------------------- io --
    def load(self) -> None:
        """(Re)load history from disk, tolerating a missing or corrupt file."""
        with self._lock:
            self._items = []
            if not self.path.exists():
                return
            try:
                data = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, ValueError) as exc:
                logger.warning("Could not read history file %s: %s", self.path, exc)
                return
            if isinstance(data, list):
                self._items = [e for e in data if isinstance(e, dict) and e.get("text")][: self.max_items]

    def save(self) -> None:
        """Persist the current history to disk (best-effort; never raises)."""
        with self._lock:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                self.path.write_text(
                    json.dumps(self._items, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
            except OSError as exc:
                logger.warning("Could not write history file %s: %s", self.path, exc)

    # ------------------------------------------------------------- access --
    def add(self, text: str, search_type: str = "generic", total: Optional[int] = None) -> None:
        """Record (or move to the front) a search entry and persist immediately."""
        text = (text or "").strip()
        if not text:
            return
        with self._lock:
            self._items = [e for e in self._items if e.get("text") != text]
            self._items.insert(0, {
                "text": text,
                "type": str(search_type),
                "total": total,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            })
            del self._items[self.max_items:]
        self.save()

    def items(self) -> list[dict]:
        """Return a shallow copy of all history entries (most recent first)."""
        with self._lock:
            return list(self._items)

    def texts(self) -> list[str]:
        """Return just the query strings, most recent first."""
        return [e.get("text", "") for e in self.items()]

    def clear(self) -> None:
        """Remove every history entry and persist the (now empty) list."""
        with self._lock:
            self._items = []
        self.save()
