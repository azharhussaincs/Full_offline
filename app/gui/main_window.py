"""The application main window — deliberately minimal.

Top:    application title + search field + Search / Clear buttons.
Centre: beautiful result cards (or an inviting empty state / a spinner).
Bottom: a results summary + a small status indicator.

Nothing else — no sidebars, menus, tables, export buttons, history panels or
Elasticsearch controls.  All the (blocking) data work runs on a background
:class:`~app.gui.workers.Worker` so the UI never freezes.
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMainWindow, QMessageBox, QVBoxLayout, QWidget

from app.config.logging_config import get_logger
from app.config.settings import settings
from app.controllers.app_controller import AppController
from app.gui import icons
from app.gui.widgets.results_view import ResultsView
from app.gui.widgets.search_header import SearchHeader
from app.gui.widgets.status_footer import StatusFooter
from app.gui.workers import Worker
from app.models.profile import ProfilePage

logger = get_logger("gui.main")


class MainWindow(QMainWindow):
    """The single, clean window the user interacts with."""

    def __init__(self) -> None:
        super().__init__()
        self.controller = AppController()
        self._workers: set[Worker] = set()
        self._busy = False
        self._connected = False
        self._connection_text = "Connecting…"
        self._query = ""
        self._page = 1

        self.setWindowTitle(settings.app_name)
        self.setWindowIcon(icons.app_icon())
        self.resize(1080, 760)
        self.setMinimumSize(820, 600)

        self._build_ui()
        self._connect_signals()

        self.results_view.show_initial()
        self.footer.set_status("Connecting…", "busy")
        self.header.focus_input()
        self._check_connection()

    # ================================================================== #
    # UI
    # ================================================================== #
    def _build_ui(self) -> None:
        central = QWidget()
        central.setObjectName("rootSurface")
        central.setAttribute(Qt.WA_StyledBackground, True)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = SearchHeader(settings.app_name)
        layout.addWidget(self.header)

        self.results_view = ResultsView()
        layout.addWidget(self.results_view, 1)

        self.footer = StatusFooter()
        layout.addWidget(self.footer)

        self.setCentralWidget(central)

    def _connect_signals(self) -> None:
        self.header.submitted.connect(self._on_search)
        self.header.cleared.connect(self._on_clear)
        self.results_view.loadMoreRequested.connect(self._on_load_more)

    # ================================================================== #
    # Async helper
    # ================================================================== #
    def _run_async(
        self,
        fn: Callable[[], object],
        on_success: Callable[[object], None],
        on_error: Callable[[str], None],
    ) -> None:
        worker = Worker(fn)
        self._workers.add(worker)

        def _cleanup() -> None:
            self._workers.discard(worker)
            worker.deleteLater()

        worker.succeeded.connect(on_success)
        worker.failed.connect(on_error)
        worker.finished.connect(_cleanup)
        worker.start()

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.header.set_busy(busy)

    # ================================================================== #
    # Connection check
    # ================================================================== #
    def _check_connection(self) -> None:
        self._run_async(self.controller.connection_status, self._on_connection_status, self._on_connection_error)

    def _on_connection_status(self, status: object) -> None:
        try:
            ok, message = status  # type: ignore[misc]
        except Exception:  # noqa: BLE001
            ok, message = False, "unavailable"
        self._connected = bool(ok)
        if ok:
            self._connection_text = "Connected"
            self.footer.set_status("Connected", "ok")
        else:
            self._connection_text = "Not connected"
            self.footer.set_status("Not connected", "error")
        logger.info("Connection status: %s (%s)", ok, message)

    def _on_connection_error(self, message: str) -> None:
        self._connected = False
        self._connection_text = "Not connected"
        self.footer.set_status("Not connected", "error")
        logger.warning("Connection check failed: %s", message)

    def _restore_status(self) -> None:
        """Put the footer status back to the connection state after an operation."""
        self.footer.set_status(self._connection_text, "ok" if self._connected else "error")

    # ================================================================== #
    # Search
    # ================================================================== #
    def _on_search(self, text: str) -> None:
        if self._busy:
            return
        self._query = text
        self._page = 1
        self._set_busy(True)
        self.results_view.show_loading(text)
        self.footer.clear_results_summary()
        self.footer.set_status("Searching…", "busy")

        page_size = settings.page_size
        self._run_async(
            lambda: self.controller.find(text, page=1, page_size=page_size),
            self._on_first_page,
            self._on_search_error,
        )

    def _on_first_page(self, result: object) -> None:
        self._set_busy(False)
        if not isinstance(result, ProfilePage):  # defensive
            self._show_error("Unexpected response while searching.")
            self.results_view.show_initial()
            self._restore_status()
            return
        if result.total == 0 or not result.profiles:
            self.results_view.show_no_results(result.query)
            self.footer.set_results_summary(f"No matches for “{result.query}”")
        else:
            self.results_view.show_results(result)
            self.footer.set_results_summary(self._summary_text())
        self._restore_status()

    def _on_load_more(self) -> None:
        if self._busy:
            return
        next_page = self._page + 1
        self.footer.set_status("Loading more…", "busy")
        self._run_async(
            lambda: self.controller.find(self._query, page=next_page, page_size=settings.page_size),
            self._on_more_page,
            self._on_load_more_error,
        )

    def _on_more_page(self, result: object) -> None:
        if isinstance(result, ProfilePage):
            self._page = result.page
            self.results_view.append_results(result)
            self.footer.set_results_summary(self._summary_text())
        self._restore_status()

    def _on_load_more_error(self, message: str) -> None:
        # Re-enable the "Show more" button so the user can retry.
        self.results_view._update_load_more(self.results_view.loaded_count < self.results_view.total_count)
        self._restore_status()
        self._show_error(message, title="Couldn't load more results")

    def _on_search_error(self, message: str) -> None:
        self._set_busy(False)
        if self.results_view.loaded_count == 0:
            self.results_view.show_initial()
            self.footer.clear_results_summary()
        self.footer.set_status("Search failed", "error")
        self._show_error(message)

    def _on_clear(self) -> None:
        if self._busy:
            return
        self._query = ""
        self._page = 1
        self.results_view.show_initial()
        self.footer.clear_results_summary()
        self._restore_status()

    # ================================================================== #
    # Helpers
    # ================================================================== #
    def _summary_text(self) -> str:
        loaded = self.results_view.loaded_count
        total = self.results_view.total_count
        if total <= 0:
            return ""
        if total == 1:
            return "1 match"
        if 0 < loaded < total:
            return f"Showing {loaded:,} of {total:,} matches"
        return f"{total:,} matches"

    def _show_error(self, message: str, *, title: str = "Search failed") -> None:
        text = (message or "Something went wrong.").strip()
        body = "Sorry, we couldn't complete that request."
        if "does not exist" in text.lower():
            body = "The directory could not be found. Please check the data service configuration."
        elif "disconnected" in text.lower() or "connection" in text.lower() or "reach" in text.lower():
            body = "We couldn't reach the data service. Please make sure it is running and try again."
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Warning)
        box.setWindowTitle(title)
        box.setText(body)
        box.setInformativeText(text if text and text.lower() not in body.lower() else "")
        box.setStandardButtons(QMessageBox.Ok)
        box.exec()

    # ----------------------------------------------------------------- #
    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override
        logger.info("Closing window")
        try:
            for worker in list(self._workers):
                worker.quit()
                worker.wait(2000)
        finally:
            try:
                self.controller.shutdown()
            finally:
                super().closeEvent(event)
