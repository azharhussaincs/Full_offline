"""Builds Elasticsearch Query-DSL from a :class:`~app.models.search_models.SearchQuery`.

Design goals:

* **Robust by default** — always include broad ``multi_match`` clauses over
  *every* field (``["*"]``) plus ``lenient: true`` so a query works regardless
  of the index mapping (string typed into a numeric field won't blow up).
* **Smart when possible** — when the search type is detected (name / e-mail /
  phone) *and* the mapping contains the usual field names for that type, add
  boosted clauses on those fields so the most relevant hits float to the top.
* **Modes** — ``smart`` (default), ``contains`` (substring via wildcard) and
  ``exact`` (phrase / term).

If even the rich query is rejected by Elasticsearch, the search service falls
back to :func:`simple_search_body`.
"""
from __future__ import annotations

import re
from typing import Any, Optional

from app.config.logging_config import get_logger
from app.models.search_models import SearchQuery, SearchType
from app.utils.detector import candidate_fields

logger = get_logger("services.query_builder")

# Lucene query-string reserved characters that must be escaped (we keep '*' for wildcards).
_QS_SPECIAL = re.compile(r'([+\-=&|!(){}\[\]^"~:\\/])')


def _escape_query_string(text: str) -> str:
    """Escape Lucene ``query_string`` reserved characters, preserving alnum/spaces/'*'."""
    return _QS_SPECIAL.sub(r"\\\1", text)


def _resolve_field(name: str, available: list[str]) -> Optional[str]:
    """Return the actual mapping field matching *name* case-insensitively.

    If the mapping is unknown (``available`` empty) the name is returned as-is —
    querying an unmapped field is harmless (it simply matches nothing).
    """
    if not available:
        return name
    lower = name.lower()
    for field in available:
        if field.lower() == lower:
            return field
    return None


def _keyword_variant(field: str, available: list[str]) -> str:
    """Return ``"<field>.keyword"`` if that multi-field exists, else *field*."""
    if available and f"{field}.keyword" in available:
        return f"{field}.keyword"
    return field


def build_search_body(query: SearchQuery, available_fields: Optional[list[str]] = None) -> dict[str, Any]:
    """Return the Elasticsearch ``query`` clause for *query*.

    Args:
        query: the parsed search request.
        available_fields: dotted field names from the index mapping (may be empty/None).

    Returns:
        A Query-DSL dict — e.g. ``{"match_all": {}}`` or ``{"bool": {...}}``.
    """
    available = list(available_fields or [])
    text = (query.text or "").strip()

    # No text, or an explicit "browse everything" request -> match all.
    if not text or query.search_type == SearchType.ALL:
        return {"match_all": {}}

    # Which fields should receive extra weight / dedicated clauses?
    if query.fields:
        targets = [f for f in (_resolve_field(name, available) for name in query.fields) if f]
    else:
        targets = [f for f in (_resolve_field(name, available) for name in candidate_fields(query.search_type)) if f]

    mode = (query.match_mode or "smart").lower()
    should: list[dict[str, Any]] = []

    # --- exact phrase / term mode -----------------------------------------
    if mode == "exact":
        if targets:
            for field in targets:
                should.append({"match_phrase": {field: {"query": text}}})
                should.append({"term": {_keyword_variant(field, available): {"value": text}}})
        else:
            should.append({"multi_match": {"query": text, "fields": ["*"], "type": "phrase", "lenient": True}})
        return {"bool": {"should": should, "minimum_should_match": 1}}

    # --- smart / contains modes -------------------------------------------
    should.append({"multi_match": {
        "query": text, "fields": ["*"], "type": "best_fields", "operator": "and", "lenient": True,
    }})
    should.append({"multi_match": {
        "query": text, "fields": ["*"], "type": "phrase_prefix", "lenient": True,
    }})

    if mode == "contains" and " " not in text:
        escaped = _escape_query_string(text)
        should.append({"query_string": {
            "query": f"*{escaped}*", "fields": ["*"], "analyze_wildcard": True, "lenient": True,
        }})

    # Boost matches on the field names commonly used for the detected type.
    # We deliberately only use ``match`` here (it supports ``lenient`` and works
    # on text *and* keyword fields) — ``match_phrase_prefix`` would 400 on a
    # ``keyword`` field, and prefix behaviour is already covered by the global
    # ``multi_match`` "phrase_prefix" clause above.
    for field in targets:
        should.append({"match": {field: {"query": text, "boost": 3.0, "lenient": True}}})

    # --- phone-number specific extras (digit normalisation) ---------------
    if query.search_type == SearchType.PHONE:
        digits = re.sub(r"\D", "", text)
        if digits and digits != text:
            should.append({"multi_match": {"query": digits, "fields": ["*"], "lenient": True}})
        if digits:
            for field in targets:
                should.append({"wildcard": {_keyword_variant(field, available): {"value": f"*{digits}*"}}})

    if not should:  # extremely defensive — should never happen
        return {"multi_match": {"query": text, "fields": ["*"], "lenient": True}}
    return {"bool": {"should": should, "minimum_should_match": 1}}


def simple_search_body(text: str) -> dict[str, Any]:
    """A minimal, always-valid query used as a fallback if the rich query fails."""
    text = (text or "").strip()
    if not text:
        return {"match_all": {}}
    return {"multi_match": {"query": text, "fields": ["*"], "lenient": True}}
