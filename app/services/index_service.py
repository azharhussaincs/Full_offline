"""Index-level Elasticsearch operations: listing, existence checks, mappings, counts.

All methods are read-only and degrade gracefully — if the cluster is
unreachable or an index is missing they return an empty result rather than
raising, so the GUI can keep working.
"""
from __future__ import annotations

from typing import Any, Optional

from elasticsearch import NotFoundError

from app.config.logging_config import get_logger
from app.config.settings import settings
from app.database.es_client import ESClient

logger = get_logger("services.index")


class IndexService:
    """Read-only helpers for working with Elasticsearch indices."""

    def __init__(self, es_client: Optional[ESClient] = None) -> None:
        self._es = es_client or ESClient.instance()

    # ------------------------------------------------------------------ #
    def list_indices(self) -> list[dict[str, Any]]:
        """Return all indices with health / status / doc-count / size metadata.

        Uses the ``_cat/indices`` API which yields plain dicts that are easy to
        display in a table widget.  The list is sorted by index name.
        """
        resp = self._es.client.cat.indices(format="json", expand_wildcards="all")
        rows: list[dict[str, Any]] = [dict(r) for r in resp]
        rows.sort(key=lambda r: str(r.get("index", "")))
        logger.debug("Listed %d indices", len(rows))
        return rows

    def index_exists(self, index: Optional[str] = None) -> bool:
        """Return ``True`` if *index* (default: the configured index) exists."""
        index = index or settings.es_index
        try:
            return bool(self._es.client.indices.exists(index=index))
        except Exception as exc:  # noqa: BLE001
            logger.warning("indices.exists check failed for %r: %s", index, exc)
            return False

    def count(self, index: Optional[str] = None) -> int:
        """Return the number of documents in *index* (0 if missing/unreachable)."""
        index = index or settings.es_index
        try:
            resp = dict(self._es.client.count(index=index))
            return int(resp.get("count", 0))
        except NotFoundError:
            return 0
        except Exception as exc:  # noqa: BLE001
            logger.warning("count failed for %r: %s", index, exc)
            return 0

    def get_mapping_fields(self, index: Optional[str] = None) -> list[str]:
        """Return a sorted list of dotted *leaf* field names from *index*'s mapping.

        Multi-fields (e.g. ``name.keyword``) are included.  If the index has no
        mapping or does not exist, an empty list is returned.
        """
        index = index or settings.es_index
        try:
            resp = dict(self._es.client.indices.get_mapping(index=index))
        except NotFoundError:
            logger.info("Index %r not found while reading mapping", index)
            return []
        except Exception as exc:  # noqa: BLE001
            logger.warning("get_mapping failed for %r: %s", index, exc)
            return []

        fields: set[str] = set()
        for body in resp.values():
            properties = ((body or {}).get("mappings") or {}).get("properties") or {}
            self._collect_fields(properties, "", fields)
        return sorted(fields)

    # ------------------------------------------------------------------ #
    def _collect_fields(self, properties: dict[str, Any], prefix: str, out: set[str]) -> None:
        """Recursively flatten an ES ``properties`` block into dotted field names."""
        for name, body in properties.items():
            if not isinstance(body, dict):
                continue
            path = f"{prefix}{name}"
            sub_props = body.get("properties")
            if isinstance(sub_props, dict):
                self._collect_fields(sub_props, f"{path}.", out)
                continue
            out.add(path)
            for sub_name in (body.get("fields") or {}):
                out.add(f"{path}.{sub_name}")
