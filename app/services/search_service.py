"""High-level search operations against Elasticsearch.

This layer turns a :class:`~app.models.search_models.SearchQuery` into an
Elasticsearch request (delegating the DSL to :mod:`app.services.query_builder`),
executes it, and converts the raw response into domain objects
(:class:`~app.models.search_models.SearchResult` / ``Document``).

It also memoises each index's searchable field list so the query builder can be
mapping-aware without a round-trip on every keystroke.
"""
from __future__ import annotations

from typing import Any, Optional

from elasticsearch import NotFoundError

from app.config.logging_config import get_logger
from app.config.settings import settings
from app.database.es_client import ESClient
from app.models.search_models import Document, SearchQuery, SearchResult, SearchType
from app.services.index_service import IndexService
from app.services.query_builder import build_search_body, simple_search_body

logger = get_logger("services.search")


class SearchError(RuntimeError):
    """Raised when a search request cannot be completed at all."""


class SearchService:
    """Executes searches and converts raw responses into domain objects."""

    def __init__(
        self,
        es_client: Optional[ESClient] = None,
        index_service: Optional[IndexService] = None,
    ) -> None:
        self._es = es_client or ESClient.instance()
        self._index_service = index_service or IndexService(self._es)
        self._fields_cache: dict[str, list[str]] = {}

    # ------------------------------------------------------------------ #
    # Field-list caching
    # ------------------------------------------------------------------ #
    def available_fields(self, index: Optional[str] = None) -> list[str]:
        """Return (and memoise) the searchable field names for *index*."""
        index = index or settings.es_index
        if index not in self._fields_cache:
            try:
                self._fields_cache[index] = self._index_service.get_mapping_fields(index)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not load mapping for %r: %s", index, exc)
                self._fields_cache[index] = []
        return list(self._fields_cache[index])

    def invalidate_fields_cache(self, index: Optional[str] = None) -> None:
        """Drop the cached field list for *index* (or for every index when ``None``)."""
        if index is None:
            self._fields_cache.clear()
        else:
            self._fields_cache.pop(index, None)

    # ------------------------------------------------------------------ #
    # Search
    # ------------------------------------------------------------------ #
    def search(self, query: SearchQuery) -> SearchResult:
        """Run *query* and return a populated :class:`SearchResult`.

        On a rejected rich query (exotic mapping, etc.) it transparently retries
        with a minimal ``multi_match``.  It raises :class:`SearchError` only if
        the target index is missing or even the fallback query fails.
        """
        index = query.index or settings.es_index
        page = max(1, query.page)
        size = max(1, query.page_size)
        from_ = (page - 1) * size

        body = build_search_body(query, self.available_fields(index))
        logger.debug("Searching index=%s type=%s page=%d size=%d body=%s",
                     index, query.search_type, page, size, body)
        try:
            resp = self._es.client.search(
                index=index, query=body, from_=from_, size=size, track_total_hits=True,
            )
        except NotFoundError as exc:
            logger.error("Search target index %r not found", index)
            raise SearchError(f"Index '{index}' does not exist.") from exc
        except Exception as exc:  # noqa: BLE001
            logger.warning("Rich query failed (%s); retrying with a simple query", exc)
            try:
                resp = self._es.client.search(
                    index=index, query=simple_search_body(query.text),
                    from_=from_, size=size, track_total_hits=True,
                )
            except NotFoundError as exc2:
                raise SearchError(f"Index '{index}' does not exist.") from exc2
            except Exception as exc2:  # noqa: BLE001
                logger.exception("Search failed for index %r", index)
                raise SearchError(f"Search failed: {exc2}") from exc2

        return self._to_result(query, dict(resp))

    def get_all_documents(
        self, index: Optional[str] = None, page: int = 1, page_size: Optional[int] = None,
    ) -> SearchResult:
        """Convenience wrapper that returns every document (paged) from *index*."""
        query = SearchQuery(
            text="", search_type=SearchType.ALL, page=page,
            page_size=page_size or settings.page_size, index=index or settings.es_index,
        )
        return self.search(query)

    # ------------------------------------------------------------------ #
    def _to_result(self, query: SearchQuery, resp: dict[str, Any]) -> SearchResult:
        """Convert a raw search response dict into a :class:`SearchResult`."""
        hits = resp.get("hits") or {}
        total_raw = hits.get("total")
        if isinstance(total_raw, dict):
            total = int(total_raw.get("value", 0))
        else:
            total = int(total_raw or 0)

        documents = [
            Document(
                id=str(hit.get("_id", "")),
                index=str(hit.get("_index", query.index or settings.es_index)),
                score=hit.get("_score"),
                source=dict(hit.get("_source") or {}),
            )
            for hit in (hits.get("hits") or [])
        ]
        return SearchResult(
            query=query, total=total, took_ms=int(resp.get("took", 0)), documents=documents,
        )
