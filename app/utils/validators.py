"""Input-validation helpers used across the application (GUI + services)."""
from __future__ import annotations

#: Hard upper bound on the length of a search query string.
MAX_QUERY_LENGTH = 1024

_FORBIDDEN_INDEX_CHARS = set(' \t\n\\/*?"<>|,#')


class ValidationError(ValueError):
    """Raised when user-supplied input fails validation.

    Subclasses :class:`ValueError`, so callers that only care about "bad input"
    can catch the broader type.
    """


def validate_search_text(text: str, *, allow_empty: bool = False) -> str:
    """Validate and normalise a search query string.

    Strips surrounding whitespace.  Raises :class:`ValidationError` when the
    value is empty (unless *allow_empty* is ``True``) or longer than
    :data:`MAX_QUERY_LENGTH`.

    Returns:
        The cleaned (trimmed) string.
    """
    cleaned = (text or "").strip()
    if not cleaned and not allow_empty:
        raise ValidationError(
            "Please enter a name, e-mail address or phone number to search for."
        )
    if len(cleaned) > MAX_QUERY_LENGTH:
        raise ValidationError(
            f"Search text is too long (maximum {MAX_QUERY_LENGTH} characters)."
        )
    return cleaned


def validate_index_name(name: str) -> str:
    """Validate an Elasticsearch index name (best-effort, offline-friendly).

    Returns the lower-cased name.  Raises :class:`ValidationError` on obviously
    invalid input (empty, contains forbidden characters, or starts with
    ``-``/``_``/``+``).
    """
    cleaned = (name or "").strip()
    if not cleaned:
        raise ValidationError("Index name cannot be empty.")
    if any(ch in _FORBIDDEN_INDEX_CHARS for ch in cleaned):
        raise ValidationError(
            'Invalid index name — it may not contain spaces or any of \\ / * ? " < > | , #'
        )
    if cleaned[0] in {"-", "_", "+"}:
        raise ValidationError("Index name may not start with '-', '_' or '+'.")
    return cleaned.lower()
