"""Application controller — the single façade the GUI layer talks to.

It wires together the database client, the index/search services, the search
history and the export utilities, and exposes coarse-grained, GUI-friendly
methods.  Keeping this layer free of any Qt imports means the same controller
could back a CLI, a REST API or a test-suite without changes.

All of its methods are *blocking* — the GUI runs them on a background thread
(see :mod:`app.gui.workers`).
"""
from __future__ import annotations

from pathlib import Path
from typing import Iterable, Optional

from app.config.logging_config import get_logger
from app.config.settings import settings
from app.database.es_client import ESClient, ElasticsearchConnectionError
from app.models.profile import ProfilePage
from app.models.search_models import Document, SearchQuery, SearchResult, SearchType
from app.services.index_service import IndexService
from app.services.search_service import SearchError, SearchService
from app.utils.detector import detect_search_type
from app.utils.export import export_documents
from app.utils.history import SearchHistory
from app.utils.profile_mapper import document_to_profile
from app.utils.validators import ValidationError, validate_search_text

logger = get_logger("controller")

# Type aliases for readability of the public API.
SearchTypeName = str  # one of: "auto", "name", "email", "phone", "all", "generic"
MatchMode = str       # one of: "smart", "contains", "exact"


class AppController:
    """High-level operations used by the desktop UI."""

    def __init__(self) -> None:
        self.es = ESClient.instance()
        self.index_service = IndexService(self.es)
        self.search_service = SearchService(self.es, self.index_service)
        self.history = SearchHistory()
        logger.info(
            "Controller initialised (index=%s, host=%s, user=%s)",
            settings.es_index, settings.es_host, settings.es_username,
        )

    # ------------------------------------------------------------------ #
    # Connection
    # ------------------------------------------------------------------ #
    def connection_status(self) -> tuple[bool, str]:
        """Return ``(is_connected, human_message)`` describing the cluster state."""
        if not self.es.ping():
            return False, "disconnected — is Elasticsearch running on this host?"
        try:
            info = self.es.cluster_info()
            return True, f"connected to '{info.get('cluster_name')}' (v{info.get('version')})"
        except ElasticsearchConnectionError:
            return True, "connected"

    # ------------------------------------------------------------------ #
    # Mapping / fields
    # ------------------------------------------------------------------ #
    def available_fields(self, index: Optional[str] = None) -> list[str]:
        """Return the searchable (dotted) field names for *index*."""
        return self.search_service.available_fields(index or settings.es_index)

    def refresh_fields(self, index: Optional[str] = None) -> list[str]:
        """Invalidate the cached field list for *index* and reload it."""
        self.search_service.invalidate_fields_cache(index or settings.es_index)
        return self.available_fields(index)

    # ------------------------------------------------------------------ #
    # Query construction
    # ------------------------------------------------------------------ #
    def make_query(
        self,
        *,
        text: str,
        search_type: SearchTypeName = "auto",
        field: Optional[str] = None,
        match_mode: MatchMode = "smart",
        index: Optional[str] = None,
        page: int = 1,
        page_size: Optional[int] = None,
    ) -> SearchQuery:
        """Validate inputs and build a :class:`SearchQuery`.

        ``search_type`` may be ``"auto"`` (detect from *text*), one of the
        concrete :class:`SearchType` values, or ``"all"`` (browse everything —
        the only case where empty *text* is allowed).

        Raises:
            ValidationError: if the text is empty (and not ``"all"``) or too long.
        """
        raw_type = (search_type or "auto").strip().lower()
        cleaned = validate_search_text(text, allow_empty=(raw_type == "all"))

        if raw_type == "all":
            stype = SearchType.ALL
        elif raw_type in {"auto", "", "generic"}:
            stype = detect_search_type(cleaned)
        else:
            try:
                stype = SearchType(raw_type)
            except ValueError:
                stype = detect_search_type(cleaned)

        fields: list[str] = []
        if field and field.strip() and field.strip() not in {"*", "all", "all fields"}:
            fields = [field.strip()]

        return SearchQuery(
            text=cleaned,
            search_type=stype,
            page=max(1, page),
            page_size=page_size or settings.page_size,
            fields=fields,
            match_mode=(match_mode or "smart").strip().lower(),
            index=(index or settings.es_index).strip() or settings.es_index,
        )

    # ------------------------------------------------------------------ #
    # Searching
    # ------------------------------------------------------------------ #
    def search(self, query: SearchQuery) -> SearchResult:
        """Execute *query* (and record it in the history when it has text)."""
        result = self.search_service.search(query)
        if query.text.strip():
            try:
                self.history.add(query.text, str(query.search_type), result.total)
            except Exception:  # noqa: BLE001 - history must never break a search
                logger.warning("Could not persist search history", exc_info=True)
        return result

    def all_documents(
        self, index: Optional[str] = None, page: int = 1, page_size: Optional[int] = None,
    ) -> SearchResult:
        """Return every document (paged) from *index* — i.e. a ``match_all`` search."""
        return self.search_service.get_all_documents(
            index=index or settings.es_index, page=page, page_size=page_size or settings.page_size,
        )

    # ------------------------------------------------------------------ #
    # The single high-level operation the (new) clean UI uses
    # ------------------------------------------------------------------ #
    def find(self, text: str, page: int = 1, page_size: Optional[int] = None) -> ProfilePage:
        """Search for a name / phone / e-mail and return clean :class:`Profile` cards.

        The search type is auto-detected; no Elasticsearch metadata is exposed.

        Args:
            text: the user's query (a name, phone number or e-mail address).
            page: 1-based page number (for "load more").
            page_size: results per page (defaults to ``settings.page_size``).

        Returns:
            A :class:`~app.models.profile.ProfilePage`.

        Raises:
            ValidationError: if *text* is empty / too long.
            SearchError: if the search cannot be performed (e.g. missing index).
        """
        query = self.make_query(text=text, search_type="auto", page=page, page_size=page_size or settings.page_size)
        result = self.search_service.search(query)
        if query.text.strip():
            try:
                self.history.add(query.text, str(query.search_type), result.total)
            except Exception:  # noqa: BLE001 - history must never break a search
                logger.debug("Could not persist search history", exc_info=True)
        profiles = [document_to_profile(doc.source) for doc in result.documents]
        logger.info("find(%r) page %d -> %d/%d hit(s) in %dms (type=%s)",
                    query.text, query.page, len(profiles), result.total, result.took_ms, query.search_type)
        return ProfilePage(
            query=query.text, detected_type=str(query.search_type), profiles=profiles,
            total=result.total, page=query.page, page_size=query.page_size, took_ms=result.took_ms,
        )

    # ------------------------------------------------------------------ #
    # Index management
    # ------------------------------------------------------------------ #
    def list_indices(self) -> list[dict]:
        """Return all cluster indices with metadata (see :meth:`IndexService.list_indices`)."""
        return self.index_service.list_indices()

    def index_exists(self, name: str) -> bool:
        """Return ``True`` if the index *name* exists in the cluster."""
        return self.index_service.index_exists(name)

    def document_count(self, index: Optional[str] = None) -> int:
        """Return the number of documents in *index*."""
        return self.index_service.count(index or settings.es_index)

    # ------------------------------------------------------------------ #
    # Export
    # ------------------------------------------------------------------ #
    def export_results(self, documents: Iterable[Document], fmt: str, path: Path) -> Path:
        """Export *documents* to *path* in ``"csv"`` or ``"json"`` format; return the path."""
        return export_documents(list(documents), fmt, Path(path))

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #
    def shutdown(self) -> None:
        """Persist state and release resources.  Safe to call multiple times."""
        try:
            self.history.save()
        finally:
            self.es.close()


__all__ = ["AppController", "SearchError", "ValidationError"]
