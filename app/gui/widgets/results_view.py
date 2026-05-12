"""The centre of the window — a stack of four "pages":

1. **initial**     – an inviting prompt shown before the first search;
2. **loading**     – a spinner + "Searching…";
3. **results**     – a small export toolbar, a scrollable column of
   :class:`ResultCard`s, and an optional "Show more results" button;
4. **no results**  – a friendly empty-state for a query that matched nothing.

Errors are *not* a page here — the main window shows them as a clean popup.

The view emits :attr:`loadMoreRequested` when the user asks for the next page;
the main window fetches it and calls :meth:`append_results`.  "Download CSV" /
"Download PDF" are handled here (the view owns the displayed profiles) — only
user-facing fields are ever written, never Elasticsearch metadata.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QUrl, Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.config.logging_config import get_logger
from app.config.settings import settings
from app.gui import icons, theme
from app.gui.widgets.result_card import ResultCard
from app.gui.widgets.states import LoadingState, MessageState
from app.models.profile import Profile, ProfilePage
from app.utils import profile_export

logger = get_logger("gui.results")


class ResultsView(QStackedWidget):
    """A self-managing results area (states + export toolbar + scrollable cards)."""

    loadMoreRequested = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._loaded = 0
        self._total = 0
        self._query = ""
        self._profiles: list[Profile] = []

        # --- page: initial prompt ---------------------------------------
        self._initial = MessageState(
            None,
            "Find a person",
            "Search by name, phone number or e‑mail address and matching "
            "profiles will appear here.",
        )
        self.addWidget(self._initial)

        # --- page: loading ---------------------------------------------
        self._loading = LoadingState()
        self.addWidget(self._loading)

        # --- page: results ---------------------------------------------
        self._results_page = self._build_results_page()
        self.addWidget(self._results_page)

        # --- page: no results ------------------------------------------
        self._no_results = MessageState(
            None,
            "No matches found",
            "We couldn't find anyone matching your search. Try a different "
            "name, phone number or e‑mail address.",
        )
        self.addWidget(self._no_results)

        self.setCurrentWidget(self._initial)

    # ------------------------------------------------------------------ #
    # Building the results page
    # ------------------------------------------------------------------ #
    def _build_results_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # --- export toolbar (aligned with the card column) -------------
        layout.addWidget(self._build_export_toolbar())

        # --- scrollable cards ------------------------------------------
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._scroll.setFrameShape(QScrollArea.NoFrame)

        scroll_content = QWidget()
        content_row = QHBoxLayout(scroll_content)
        content_row.setContentsMargins(theme.PAGE_GUTTER, 18, theme.PAGE_GUTTER, 28)
        content_row.setSpacing(0)
        content_row.addStretch(1)

        self._cards_column = QWidget()
        self._cards_column.setMaximumWidth(theme.CONTENT_MAX_WIDTH)
        self._cards_layout = QVBoxLayout(self._cards_column)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)
        self._cards_layout.setSpacing(16)
        self._cards_layout.addStretch(1)
        # Big stretch factor -> the column claims the width up to its maximum;
        # the side spacers split whatever is left, keeping the cards centred.
        content_row.addWidget(self._cards_column, 100)

        content_row.addStretch(1)
        self._scroll.setWidget(scroll_content)
        layout.addWidget(self._scroll, 1)

        # --- "Show more" row, pinned below the scroll area -------------
        self._load_more_row = QWidget()
        row = QHBoxLayout(self._load_more_row)
        row.setContentsMargins(0, 8, 0, 22)
        row.addStretch(1)
        self._load_more_btn = QPushButton("Show more results")
        self._load_more_btn.setObjectName("softButton")
        self._load_more_btn.setCursor(Qt.PointingHandCursor)
        self._load_more_btn.clicked.connect(self._on_load_more_clicked)
        row.addWidget(self._load_more_btn)
        row.addStretch(1)
        self._load_more_row.setVisible(False)
        layout.addWidget(self._load_more_row)

        return page

    def _build_export_toolbar(self) -> QWidget:
        toolbar = QWidget()
        outer = QHBoxLayout(toolbar)
        outer.setContentsMargins(theme.PAGE_GUTTER, 18, theme.PAGE_GUTTER, 4)
        outer.setSpacing(0)
        outer.addStretch(1)

        inner = QWidget()
        inner.setMaximumWidth(theme.CONTENT_MAX_WIDTH)
        bar = QHBoxLayout(inner)
        bar.setContentsMargins(0, 0, 0, 0)
        bar.setSpacing(8)

        self._results_caption = QLabel("")
        self._results_caption.setObjectName("resultsCaption")
        self._results_caption.setTextInteractionFlags(Qt.TextSelectableByMouse)
        self._results_caption.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Preferred)
        bar.addWidget(self._results_caption, 1)

        self._csv_btn = QPushButton("Download CSV")
        self._csv_btn.setObjectName("exportButton")
        self._csv_btn.setCursor(Qt.PointingHandCursor)
        self._csv_btn.setIcon(icons.download_icon(14))
        self._csv_btn.setToolTip("Save the listed results as a CSV spreadsheet")
        self._csv_btn.clicked.connect(lambda: self._export("csv"))
        bar.addWidget(self._csv_btn)

        self._pdf_btn = QPushButton("Download PDF")
        self._pdf_btn.setObjectName("exportButton")
        self._pdf_btn.setCursor(Qt.PointingHandCursor)
        self._pdf_btn.setIcon(icons.download_icon(14))
        self._pdf_btn.setToolTip("Save the listed results as a PDF report")
        self._pdf_btn.clicked.connect(lambda: self._export("pdf"))
        bar.addWidget(self._pdf_btn)

        outer.addWidget(inner, 100)
        outer.addStretch(1)
        return toolbar

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    @property
    def loaded_count(self) -> int:
        return self._loaded

    @property
    def total_count(self) -> int:
        return self._total

    def show_initial(self) -> None:
        """Return to the pre-search prompt."""
        self._loading.stop()
        self._reset_results()
        self.setCurrentWidget(self._initial)

    def show_loading(self, query: str) -> None:
        """Switch to the loading state for *query*."""
        self._loading.start(query)
        self.setCurrentWidget(self._loading)

    def show_results(self, page: ProfilePage) -> None:
        """Display the first page of results (replacing any previous results)."""
        self._loading.stop()
        self._clear_cards()
        self._profiles = []
        self._loaded = 0
        self._total = page.total
        self._query = page.query or ""
        self._add_cards(page.profiles)
        self._loaded = len(page.profiles)
        self._update_load_more(page.has_more)
        self._refresh_export_bar()
        self.setCurrentWidget(self._results_page)
        self._scroll.verticalScrollBar().setValue(0)

    def append_results(self, page: ProfilePage) -> None:
        """Append another page of results to the current list."""
        self._add_cards(page.profiles)
        self._loaded += len(page.profiles)
        self._total = page.total
        self._update_load_more(page.has_more)
        self._refresh_export_bar()

    def show_no_results(self, query: str) -> None:
        """Show the friendly empty-state for a query that matched nothing."""
        self._loading.stop()
        self._reset_results()
        self._no_results.configure(
            None,
            "No matches found",
            f"We couldn't find anyone matching “{query}”. Try a different "
            "name, phone number or e‑mail address.",
        )
        self.setCurrentWidget(self._no_results)

    # ------------------------------------------------------------------ #
    # Internals
    # ------------------------------------------------------------------ #
    def _reset_results(self) -> None:
        self._clear_cards()
        self._profiles = []
        self._loaded = 0
        self._total = 0
        self._query = ""
        self._load_more_row.setVisible(False)

    def _clear_cards(self) -> None:
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                widget.deleteLater()
        self._cards_layout.addStretch(1)

    def _add_cards(self, profiles) -> None:
        for profile in profiles:
            self._profiles.append(profile)
            card = ResultCard(profile)
            # Insert before the trailing stretch so cards stay top-aligned.
            self._cards_layout.insertWidget(self._cards_layout.count() - 1, card)

    def _update_load_more(self, has_more: bool) -> None:
        self._load_more_btn.setEnabled(True)
        self._load_more_btn.setText("Show more results")
        self._load_more_row.setVisible(bool(has_more))

    def _on_load_more_clicked(self) -> None:
        self._load_more_btn.setEnabled(False)
        self._load_more_btn.setText("Loading more…")
        self.loadMoreRequested.emit()

    # ------------------------------------------------------------------ #
    # Export toolbar
    # ------------------------------------------------------------------ #
    def _refresh_export_bar(self) -> None:
        count = len(self._profiles)
        have = count > 0
        if self._total and self._total > count:
            tally = f"{count:,} of {self._total:,} shown"
        else:
            tally = "1 result" if count == 1 else f"{count:,} results"
        query = self._query if len(self._query) <= 40 else f"{self._query[:39].rstrip()}…"
        caption = f"Results for “{query}”  ·  {tally}" if query else tally
        self._results_caption.setText(caption)
        self._csv_btn.setEnabled(have)
        self._pdf_btn.setEnabled(have)

    def _export(self, fmt: str) -> None:
        if not self._profiles:
            return
        fmt = fmt.lower()
        if fmt == "csv":
            title, file_filter, ext = "Save results as CSV", "CSV spreadsheet (*.csv)", "csv"
        else:
            title, file_filter, ext = "Save results as PDF", "PDF report (*.pdf)", "pdf"

        settings.export_dir.mkdir(parents=True, exist_ok=True)
        default_path = str(Path(settings.export_dir) / profile_export.suggested_filename(self._query, ext))
        chosen, _selected = QFileDialog.getSaveFileName(self, title, default_path, file_filter)
        if not chosen:
            return
        if not chosen.lower().endswith(f".{ext}"):
            chosen = f"{chosen}.{ext}"

        try:
            if fmt == "csv":
                saved = profile_export.write_csv(self._profiles, chosen)
            else:
                saved = profile_export.write_pdf(
                    self._profiles, chosen, query=self._query, total=self._total,
                    app_name=settings.app_name,
                )
        except Exception as exc:  # noqa: BLE001 - surface any failure cleanly
            logger.exception("Export to %s failed", fmt.upper())
            QMessageBox.warning(
                self, "Export failed",
                f"Sorry, the {fmt.upper()} file couldn't be saved.\n\n{exc}",
            )
            return

        self._announce_export(saved)

    def _announce_export(self, path: Path) -> None:
        count = len(self._profiles)
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle("Export complete")
        box.setText(f"Saved {count:,} {'record' if count == 1 else 'records'} to:")
        box.setInformativeText(str(path))
        open_btn = box.addButton("Open folder", QMessageBox.ActionRole)
        box.addButton(QMessageBox.Ok)
        box.setDefaultButton(QMessageBox.Ok)
        box.exec()
        if box.clickedButton() is open_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))
