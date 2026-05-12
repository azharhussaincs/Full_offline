"""View-models for the user-facing UI.

The GUI never sees raw Elasticsearch documents — it only ever works with
:class:`Profile` objects (a clean person card) and :class:`ProfilePage`
(one page of such cards plus paging info).  No ``_id`` / ``_score`` / ``_index``
or other technical metadata ever reaches the screen.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Final

#: Elasticsearch refuses ``from + size > index.max_result_window`` (default
#: 10 000); we never offer to load past that.
MAX_LOADABLE_RESULTS: Final[int] = 10_000


@dataclass(frozen=True)
class ProfileField:
    """A single labelled value shown inside a profile card (e.g. ``Phone → …``)."""

    label: str
    value: str


@dataclass(frozen=True)
class Profile:
    """A clean, display-ready representation of one matching record."""

    name: str
    fields: tuple[ProfileField, ...] = ()

    @property
    def display_name(self) -> str:
        """The name to show — falls back to ``"Unknown"`` when missing."""
        return self.name.strip() if self.name and self.name.strip() else "Unknown"

    @property
    def initials(self) -> str:
        """Up to two upper-case initials derived from the name (for the avatar)."""
        name = self.display_name
        if name == "Unknown":
            return "?"
        parts = [p for p in re.split(r"[\s._/\\-]+", name) if p and p[0].isalnum()]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()


@dataclass
class ProfilePage:
    """One page of search results, already mapped to :class:`Profile` objects."""

    query: str
    detected_type: str
    profiles: list[Profile] = field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 25
    took_ms: int = 0

    @property
    def loaded_through(self) -> int:
        """How many results have been served up to and including this page."""
        return min(self.page * self.page_size, self.total, MAX_LOADABLE_RESULTS)

    @property
    def has_more(self) -> bool:
        """Whether another page can be fetched (respecting the result-window cap)."""
        return self.loaded_through < min(self.total, MAX_LOADABLE_RESULTS)
