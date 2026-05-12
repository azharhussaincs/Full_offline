"""Result-export utilities (CSV / JSON) plus small data-shaping helpers.

These functions take :class:`~app.models.search_models.Document` instances and
either serialise them to a string (for the clipboard) or write them to disk.
Nested documents are flattened with dotted keys so they fit neatly into a CSV
or a grid view.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Iterable

from app.config.logging_config import get_logger
from app.models.search_models import Document

logger = get_logger("utils.export")

#: Export formats understood by :func:`export_documents`.
SUPPORTED_FORMATS = ("csv", "json")


# --------------------------------------------------------------------------- #
# Data-shaping helpers
# --------------------------------------------------------------------------- #
def flatten_dict(data: Any, parent_key: str = "", sep: str = ".") -> dict[str, Any]:
    """Flatten a nested dict / list structure into a single-level *dotted* dict.

    * nested dicts -> ``parent.child`` keys
    * lists of objects -> positional keys (``items.0.name``)
    * lists of scalars -> kept as a compact JSON string
    * a non-dict top-level value -> returned under the key ``"value"``

    >>> flatten_dict({"a": {"b": 1}, "tags": ["x", "y"]})
    {'a.b': 1, 'tags': '["x", "y"]'}
    """
    items: dict[str, Any] = {}
    if isinstance(data, dict):
        for key, value in data.items():
            new_key = f"{parent_key}{sep}{key}" if parent_key else str(key)
            if isinstance(value, dict):
                items.update(flatten_dict(value, new_key, sep))
            elif isinstance(value, list):
                if value and all(isinstance(v, dict) for v in value):
                    for i, item in enumerate(value):
                        items.update(flatten_dict(item, f"{new_key}{sep}{i}", sep))
                else:
                    items[new_key] = json.dumps(value, ensure_ascii=False, default=str)
            else:
                items[new_key] = value
    elif isinstance(data, list):
        items[parent_key or "value"] = json.dumps(data, ensure_ascii=False, default=str)
    else:
        items[parent_key or "value"] = data
    return items


def document_to_record(doc: Document, *, include_meta: bool = True) -> dict[str, Any]:
    """Convert a :class:`Document` into a flat dict suitable for CSV / JSON output."""
    record: dict[str, Any] = {}
    if include_meta:
        record["_id"] = doc.id
        record["_index"] = doc.index
        record["_score"] = doc.score
    record.update(flatten_dict(doc.source))
    return record


def documents_to_json_str(documents: Iterable[Document], *, indent: int = 2) -> str:
    """Serialise *documents* to a pretty JSON array string (metadata + ``_source``)."""
    payload = [
        {"_id": d.id, "_index": d.index, "_score": d.score, "_source": d.source}
        for d in documents
    ]
    return json.dumps(payload, indent=indent, ensure_ascii=False, default=str)


# --------------------------------------------------------------------------- #
# File exporters
# --------------------------------------------------------------------------- #
def export_to_json(documents: list[Document], path: Path) -> Path:
    """Write *documents* to *path* as a UTF-8 JSON array.  Returns the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(documents_to_json_str(documents), encoding="utf-8")
    logger.info("Exported %d document(s) to %s", len(documents), path)
    return path


def export_to_csv(documents: list[Document], path: Path) -> Path:
    """Write *documents* to *path* as CSV.

    The column set is the union of all (flattened) keys across the documents,
    preserving first-seen order; missing values become empty cells.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    records = [document_to_record(d) for d in documents]

    fieldnames: list[str] = []
    seen: set[str] = set()
    for record in records:
        for key in record:
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames or ["_id"], extrasaction="ignore")
        writer.writeheader()
        for record in records:
            writer.writerow({key: _csv_cell(value) for key, value in record.items()})
    logger.info("Exported %d document(s) to %s", len(documents), path)
    return path


def export_documents(documents: list[Document], fmt: str, path: Path) -> Path:
    """Dispatch to the CSV or JSON exporter based on *fmt* (``"csv"`` / ``"json"``)."""
    normalised = (fmt or "").lower().lstrip(".")
    if normalised == "json":
        return export_to_json(documents, path)
    if normalised == "csv":
        return export_to_csv(documents, path)
    raise ValueError(f"Unsupported export format: {fmt!r}. Use one of {SUPPORTED_FORMATS}.")


# --------------------------------------------------------------------------- #
# Internal
# --------------------------------------------------------------------------- #
def _csv_cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value)
