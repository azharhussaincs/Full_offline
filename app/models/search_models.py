"""Domain models used across the application.

These are intentionally framework-agnostic dataclasses: they contain no Qt and
no Elasticsearch imports, so they can be reused unchanged by a future web/API
front-end or by automated tests.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class SearchType(str, Enum):
    """The kind of value a free-text search query represents."""

    NAME = "name"
    EMAIL = "email"
    PHONE = "phone"
    GENERIC = "generic"   # text that could not be confidently classified
    ALL = "all"           # "browse everything" — translates to match_all

    def __str__(self) -> str:  # friendlier display in the UI / logs
        return self.value


@dataclass
class SearchQuery:
    """A parsed search request ready to be executed by the search service.

    Attributes:
        text: the raw (already-trimmed) query string.
        search_type: the detected/selected :class:`SearchType`.
        page: 1-based page number.
        page_size: number of hits per page.
        fields: optional explicit list of fields to restrict the search to.
        match_mode: ``"smart"`` (default), ``"contains"`` or ``"exact"``.
        index: target index name (defaults to the configured index when ``None``).
    """

    text: str = ""
    search_type: SearchType = SearchType.GENERIC
    page: int = 1
    page_size: int = 25
    fields: list[str] = field(default_factory=list)
    match_mode: str = "smart"
    index: Optional[str] = None

    @property
    def from_offset(self) -> int:
        """Zero-based ``from`` offset used for Elasticsearch pagination."""
        return (max(1, self.page) - 1) * max(1, self.page_size)


@dataclass
class Document:
    """A single Elasticsearch search hit."""

    id: str
    index: str
    score: Optional[float]
    source: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResult:
    """The outcome of a search: matching documents plus pagination metadata."""

    query: SearchQuery
    total: int
    took_ms: int = 0
    documents: list[Document] = field(default_factory=list)

    @property
    def page_count(self) -> int:
        """Total number of pages for the result set given the query page size."""
        size = max(1, self.query.page_size)
        return max(1, (self.total + size - 1) // size)

    @property
    def is_empty(self) -> bool:
        """``True`` when no documents were returned for the current page."""
        return not self.documents
