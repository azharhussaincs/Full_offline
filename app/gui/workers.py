"""Background-thread helper for the GUI.

Elasticsearch calls are blocking, so they must never run on the Qt main thread —
that would freeze the UI.  :class:`Worker` runs an arbitrary callable on a
:class:`~PySide6.QtCore.QThread` and reports the result (or the error) back to
the main thread via signals.

Typical use (see :class:`app.gui.main_window.MainWindow._run_async`)::

    worker = Worker(controller.search, query)
    worker.succeeded.connect(self._on_result)
    worker.failed.connect(self._on_error)
    worker.finished.connect(worker.deleteLater)
    worker.start()
"""
from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QThread, Signal

from app.config.logging_config import get_logger

logger = get_logger("gui.worker")


class Worker(QThread):
    """Runs ``fn(*args, **kwargs)`` on a background thread.

    Signals:
        succeeded(object): emitted with the return value when ``fn`` completes.
        failed(str): emitted with an error message if ``fn`` raises.

    (``QThread`` already provides ``started`` and ``finished``.)
    """

    succeeded = Signal(object)
    failed = Signal(str)

    def __init__(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        super().__init__()
        self._fn = fn
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:  # noqa: D401 - QThread entry point
        """Execute the wrapped callable; emit :attr:`succeeded` or :attr:`failed`."""
        try:
            result = self._fn(*self._args, **self._kwargs)
        except Exception as exc:  # noqa: BLE001 - surface everything to the UI
            logger.exception("Background task failed: %s", getattr(self._fn, "__name__", self._fn))
            self.failed.emit(str(exc) or exc.__class__.__name__)
        else:
            self.succeeded.emit(result)
