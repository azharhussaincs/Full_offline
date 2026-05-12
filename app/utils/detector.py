"""Heuristic search-type detection.

Given a free-text query string this module decides whether it most likely
represents an **e-mail address**, a **phone number** or a **person's name**,
and exposes the field names commonly used for each so the query builder can add
boosted clauses on them when they exist in the index mapping.

The detection is intentionally simple, fast and dependency-free.
"""
from __future__ import annotations

import re

from app.models.search_models import SearchType

# --- Pre-compiled patterns -------------------------------------------------
# Permissive e-mail check (good enough for routing, not for RFC validation).
_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")
# Phone numbers: optional leading "+", then digits / spaces / dashes / dots / parens.
_PHONE_RE = re.compile(r"^\+?[0-9][0-9 \-().]{4,18}[0-9]$")
_DIGIT_RE = re.compile(r"\d")

#: Field-name candidates per detected type (lower-cased; matched case-insensitively).
FIELD_CANDIDATES: dict[SearchType, list[str]] = {
    SearchType.NAME: [
        "name", "full_name", "fullname", "first_name", "firstname", "last_name",
        "lastname", "middle_name", "username", "user_name", "display_name",
        "person_name", "owner", "owner_name", "title", "contact_name", "alias",
    ],
    SearchType.EMAIL: [
        "email", "email_address", "emailaddress", "mail", "e_mail", "user_email",
        "contact_email", "primary_email", "work_email",
    ],
    SearchType.PHONE: [
        "phone", "phone_number", "phonenumber", "phone_no", "mobile", "mobile_number",
        "mobile_no", "cell", "cell_phone", "contact", "contact_number", "contact_no",
        "tel", "telephone", "msisdn", "number", "whatsapp", "landline",
    ],
}


def detect_search_type(text: str) -> SearchType:
    """Classify *text* as :class:`SearchType` ``EMAIL``, ``PHONE`` or ``NAME``.

    Empty / whitespace-only input is reported as :data:`SearchType.GENERIC`.

    >>> detect_search_type("john.doe@example.com")
    <SearchType.EMAIL: 'email'>
    >>> detect_search_type("+1 (415) 555-0199")
    <SearchType.PHONE: 'phone'>
    >>> detect_search_type("Ali Hassan")
    <SearchType.NAME: 'name'>
    """
    value = (text or "").strip()
    if not value:
        return SearchType.GENERIC
    if _EMAIL_RE.match(value):
        return SearchType.EMAIL
    digit_count = len(_DIGIT_RE.findall(value))
    if _PHONE_RE.match(value) and digit_count >= 6:
        return SearchType.PHONE
    # A pure run of >= 6 digits (no separators) is almost certainly an id or phone.
    if value.isdigit() and len(value) >= 6:
        return SearchType.PHONE
    return SearchType.NAME


def candidate_fields(search_type: SearchType) -> list[str]:
    """Return the list of common field names associated with *search_type*."""
    return list(FIELD_CANDIDATES.get(search_type, []))
