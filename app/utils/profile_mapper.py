"""Maps an arbitrary Elasticsearch ``_source`` document onto a clean
:class:`~app.models.profile.Profile` (Name / Phone / Email / Address + a few
extra humanised fields).

Goals:

* never expose technical metadata (``_id``, ``_score``, ``_index`` …);
* be tolerant of *any* field naming — ``name`` / ``NAME`` / ``full_name`` /
  ``first_name``+``last_name`` all become "Name", etc.;
* present values in a friendly way (lists joined with commas, nested objects
  flattened to a readable line, ISO timestamps trimmed to a date, booleans as
  Yes/No).

This module is pure and dependency-free, so it is trivial to unit-test.
"""
from __future__ import annotations

import re
from typing import Any

from app.models.profile import Profile, ProfileField

# --- field-name vocabularies (all compared after normalisation) -------------
_NAME_KEYS = {
    "name", "full_name", "fullname", "display_name", "displayname", "person_name",
    "contact_name", "customer_name", "client_name", "account_name", "owner_name",
    "username", "user_name", "alias", "nick_name", "nickname",
}
_FIRST_KEYS = {"first_name", "firstname", "given_name", "givenname", "fname", "first"}
_MIDDLE_KEYS = {"middle_name", "middlename", "mname", "middle"}
_LAST_KEYS = {"last_name", "lastname", "surname", "family_name", "familyname", "lname", "last"}
_EMAIL_KEYS = {
    "email", "email_address", "emailaddress", "emailid", "email_id", "e_mail",
    "mail", "user_email", "useremail", "contact_email", "primary_email", "work_email",
}
_PHONE_KEYS = {
    "phone", "phone_number", "phonenumber", "phoneno", "phone_no", "mobile",
    "mobile_number", "mobilenumber", "mobile_no", "mob", "cell", "cell_phone",
    "cellphone", "contact", "contact_number", "contactnumber", "contact_no", "tel",
    "telephone", "telephone_number", "msisdn", "whatsapp", "landline", "number", "ph",
}
_ADDRESS_KEYS = {
    "address", "addr", "full_address", "fulladdress", "mailing_address",
    "residential_address", "home_address", "postal_address", "location", "place",
}
# Parts that, when present individually, are merged into a single "Address" line.
_ADDRESS_PART_ORDER = (
    "house", "house_no", "house_number", "flat", "flat_no", "building", "block",
    "street", "street_address", "road", "address_line1", "address_line_1", "line1",
    "address_line2", "address_line_2", "line2", "address_line3", "line3", "area",
    "locality", "neighbourhood", "neighborhood", "sector", "village", "town", "city",
    "district", "tehsil", "county", "state", "province", "region", "postal_code",
    "postalcode", "postcode", "zip", "zip_code", "zipcode", "pincode", "country",
    "nationality",
)
_ADDRESS_PART_SET = set(_ADDRESS_PART_ORDER)

# Keys that must never be shown to the user.
_SKIP_KEYS = {
    "_id", "_index", "_score", "_type", "_source", "_routing", "_version", "_seq_no",
    "_primary_term", "_ignored", "id", "uuid", "guid", "_uid", "doc_id", "document_id",
    "record_id", "rowid", "row_id", "score", "index", "highlight", "sort", "shard",
}
_SKIP_PREFIXES = ("_",)

# A few notoriously ugly keys -> nice labels.
_LABEL_ALIASES = {
    "asondate": "As On Date", "as_on_date": "As On Date", "asof": "As Of",
    "dob": "Date of Birth", "date_of_birth": "Date of Birth", "birthdate": "Date of Birth",
    "birth_date": "Date of Birth", "age": "Age",
    "cnic": "CNIC", "nic": "NIC", "nid": "National ID", "national_id": "National ID",
    "ssn": "SSN", "ntn": "NTN", "tin": "TIN", "tax_id": "Tax ID",
    "passport": "Passport No.", "passport_no": "Passport No.", "passport_number": "Passport No.",
    "father_name": "Father's Name", "fathername": "Father's Name", "fathers_name": "Father's Name",
    "mother_name": "Mother's Name", "spouse_name": "Spouse's Name",
    "gender": "Gender", "sex": "Gender", "marital_status": "Marital Status", "nationality": "Nationality",
    "tags": "Tags", "labels": "Labels", "remarks": "Remarks", "notes": "Notes", "comments": "Notes",
    "company": "Company", "employer": "Employer", "organization": "Organisation",
    "organisation": "Organisation", "designation": "Designation", "job_title": "Job Title",
    "title": "Title", "role": "Role", "occupation": "Occupation", "profession": "Profession",
    "department": "Department", "branch": "Branch", "status": "Status", "account_status": "Status",
    "website": "Website", "url": "Website", "linkedin": "LinkedIn", "twitter": "Twitter",
    "registered_on": "Registered On", "joined_on": "Joined On", "created_at": "Created",
    "updated_at": "Updated", "last_seen": "Last Seen", "source": "Source",
}

# Preferred display order for the "extra" fields (labels not in this map keep
# their natural document order, placed after the known ones). Lower = earlier.
_EXTRA_LABEL_PRIORITY = {
    label: i for i, label in enumerate((
        "Father's Name", "Mother's Name", "Spouse's Name", "Date of Birth", "Age",
        "Gender", "Marital Status", "Nationality", "CNIC", "NIC", "National ID",
        "Passport No.", "SSN", "NTN", "TIN", "Tax ID", "Company", "Employer",
        "Organisation", "Designation", "Job Title", "Title", "Role", "Occupation",
        "Profession", "Department", "Branch", "Website", "LinkedIn", "Twitter",
        "Status", "Source", "Registered On", "Joined On", "Created", "Updated",
        "Last Seen", "As On Date", "As Of", "Remarks", "Notes", "Tags", "Labels",
    ))
}

_DATE_RE = re.compile(r"^(\d{4}-\d{1,2}-\d{1,2})(?:[ T]\d{2}:\d{2}(?::\d{2})?(?:\.\d+)?)?(?:Z|[+\-]\d{2}:?\d{2})?$")
_EMPTY_TOKENS = {"", "null", "none", "nil", "n/a", "na", "-", "--", "—", "undefined"}


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #
def _norm_key(key: Any) -> str:
    return re.sub(r"[\s\-]+", "_", str(key).strip().lower())


def _is_empty(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in _EMPTY_TOKENS
    if isinstance(value, (list, tuple, set, dict)):
        return len(value) == 0
    return False


def _humanize(key: Any) -> str:
    norm = _norm_key(key)
    if norm in _LABEL_ALIASES:
        return _LABEL_ALIASES[norm]
    text = re.sub(r"[_\-]+", " ", str(key).strip())
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text)   # splitCamelCase
    text = re.sub(r"\s+", " ", text).strip()
    return text.title() if text else "Detail"


def _stringify(value: Any) -> str:
    """Render *value* as a clean, human-readable string."""
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (list, tuple, set)):
        parts = [_stringify(v) for v in value if not _is_empty(v)]
        return ", ".join(dict.fromkeys(p for p in parts if p))
    if isinstance(value, dict):
        parts = [f"{_humanize(k)}: {_stringify(v)}" for k, v in value.items() if not _is_empty(v)]
        return "  ·  ".join(parts)
    text = str(value).strip()
    match = _DATE_RE.match(text)
    if match:
        return match.group(1)
    return re.sub(r"\s+", " ", text)


def _dedupe(values: list[str]) -> list[str]:
    return [v for v in dict.fromkeys(v.strip() for v in values) if v]


def _join_address(value: Any) -> str:
    if isinstance(value, dict):
        ordered: list[str] = []
        used: set[str] = set()
        for part in _ADDRESS_PART_ORDER:
            for key, val in value.items():
                if _norm_key(key) == part and not _is_empty(val):
                    ordered.append(_stringify(val))
                    used.add(_norm_key(key))
        for key, val in value.items():
            if _norm_key(key) not in used and not _is_empty(val):
                ordered.append(_stringify(val))
        return ", ".join(_dedupe(ordered))
    if isinstance(value, (list, tuple, set)):
        return ", ".join(_dedupe([_stringify(v) for v in value if not _is_empty(v)]))
    return _stringify(value)


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def document_to_profile(source: dict[str, Any] | None) -> Profile:
    """Convert an Elasticsearch ``_source`` dict into a clean :class:`Profile`."""
    source = source or {}

    name_value: str | None = None
    first = middle = last = None
    phones: list[str] = []
    emails: list[str] = []
    addresses: list[str] = []
    address_parts: dict[str, Any] = {}
    extras: list[tuple[str, str]] = []

    for raw_key, raw_value in source.items():
        key = _norm_key(raw_key)
        if key in _SKIP_KEYS or any(key.startswith(p) for p in _SKIP_PREFIXES):
            continue
        if _is_empty(raw_value):
            continue

        if name_value is None and key in _NAME_KEYS:
            name_value = _stringify(raw_value)
        elif key in _FIRST_KEYS:
            first = _stringify(raw_value)
        elif key in _MIDDLE_KEYS:
            middle = _stringify(raw_value)
        elif key in _LAST_KEYS:
            last = _stringify(raw_value)
        elif key in _EMAIL_KEYS or key.endswith("_email") or key.endswith("email") or key == "mail":
            emails.append(_stringify(raw_value))
        elif key in _PHONE_KEYS or key.endswith("_phone") or key.endswith("phone") \
                or key.endswith("mobile") or key.endswith("_mobile") or key.endswith("_number") and ("phone" in key or "mobile" in key or "contact" in key):
            phones.append(_stringify(raw_value))
        elif key in _ADDRESS_KEYS:
            addresses.append(_join_address(raw_value))
        elif key in _ADDRESS_PART_SET:
            address_parts[raw_key] = raw_value
        else:
            value_str = _stringify(raw_value)
            if value_str:
                extras.append((_humanize(raw_key), value_str))

    if not name_value:
        combo = " ".join(p for p in (first, middle, last) if p and p.strip())
        name_value = combo.strip() or None

    fields: list[ProfileField] = []
    phone_str = ", ".join(_dedupe(phones))
    email_str = ", ".join(_dedupe(emails))
    parts_addr = _join_address(address_parts) if address_parts else ""
    addr_str = ", ".join(_dedupe(addresses + ([parts_addr] if parts_addr else [])))

    if phone_str:
        fields.append(ProfileField("Phone", phone_str))
    if email_str:
        fields.append(ProfileField("Email", email_str))
    if addr_str:
        fields.append(ProfileField("Address", addr_str))

    # Show the remaining details in a sensible order (Python's sort is stable,
    # so anything not in the priority map keeps its original document order).
    extras.sort(key=lambda label_value: _EXTRA_LABEL_PRIORITY.get(label_value[0], 10_000))
    for label, value in extras:
        fields.append(ProfileField(label, value))

    return Profile(name=name_value or "Unknown", fields=tuple(fields))
