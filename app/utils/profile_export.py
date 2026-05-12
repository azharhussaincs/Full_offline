"""Export search results to clean, professional **CSV** and **PDF** reports.

The exporters work exclusively on :class:`~app.models.profile.Profile`
view-models — i.e. only the user-facing information already shown on screen
(Name, Phone, E‑mail, Address and any other humanised fields).  No ``_id`` /
``_score`` / ``_index`` or any other Elasticsearch metadata is ever written.

* :func:`write_csv`  — a tidy spreadsheet (one row per person; one column per
  field, padded so every column lines up).  UTF‑8 with a BOM so Excel opens it
  cleanly.
* :func:`write_pdf`  — a styled, paginated report (title, context line, a
  bordered table).  Rendered with Qt's built‑in :class:`QTextDocument` /
  :class:`QPdfWriter` — no third‑party dependency.

:func:`build_report_html` (used by the PDF exporter) and everything above the
PDF function are pure-Python / Qt-free; ``PySide6`` is imported lazily, only
inside :func:`write_pdf`.
"""
from __future__ import annotations

import csv
import datetime as _dt
import re
from html import escape
from pathlib import Path
from typing import Sequence

from app.config.logging_config import get_logger
from app.models.profile import Profile

logger = get_logger("utils.profile_export")

DEFAULT_APP_NAME = "PeopleFinder"

#: Field labels promoted to the front of the column order when they are present.
_PRIORITY_LABELS = (
    "Phone", "Mobile", "Email", "E‑mail", "E-mail",
    "Address", "City", "State", "Country",
    "CNIC", "National ID", "Passport", "ID",
    "Date of Birth", "Age", "Gender",
)


# --------------------------------------------------------------------------- #
# Data shaping
# --------------------------------------------------------------------------- #
def ordered_field_labels(profiles: Sequence[Profile]) -> list[str]:
    """The union of all field labels across *profiles* in a sensible order.

    "Important" labels (phone, e‑mail, address, …) come first; everything else
    follows in the order it was first encountered.
    """
    first_seen: list[str] = []
    known: set[str] = set()
    for profile in profiles:
        for fld in profile.fields:
            if fld.label not in known:
                known.add(fld.label)
                first_seen.append(fld.label)
    priority = [lbl for lbl in _PRIORITY_LABELS if lbl in known]
    seen_priority = set(priority)
    rest = [lbl for lbl in first_seen if lbl not in seen_priority]
    return priority + rest


def build_table(profiles: Sequence[Profile]) -> tuple[list[str], list[list[str]]]:
    """Return ``(header, rows)`` — ``header`` starts with ``"Name"``; each row is
    the person's display name followed by one cell per label (blank if missing)."""
    labels = ordered_field_labels(profiles)
    header = ["Name", *labels]
    rows: list[list[str]] = []
    for profile in profiles:
        values = {fld.label: fld.value for fld in profile.fields}
        rows.append([profile.display_name, *(values.get(lbl, "") for lbl in labels)])
    return header, rows


def _generated_stamp() -> str:
    return _dt.datetime.now().strftime("%d %B %Y, %H:%M")


def _context_line(query: str, exported: int, total: int) -> str:
    parts: list[str] = []
    if query:
        parts.append(f'Query: "{query}"')
    if total and total > exported:
        parts.append(f"{exported:,} of {total:,} matches")
    else:
        parts.append(f"{exported:,} {'record' if exported == 1 else 'records'}")
    parts.append(f"Generated {_generated_stamp()}")
    return "    •    ".join(parts)


def suggested_filename(query: str, extension: str) -> str:
    """A friendly default save name, e.g. ``peoplefinder-sunny-20260512-0704.csv``."""
    stub = re.sub(r"[^\w\-]+", "-", (query or "results").strip(), flags=re.UNICODE).strip("-_")
    stub = (stub or "results")[:40]
    stamp = _dt.datetime.now().strftime("%Y%m%d-%H%M")
    ext = extension.lower().lstrip(".")
    return f"peoplefinder-{stub}-{stamp}.{ext}"


# --------------------------------------------------------------------------- #
# CSV
# --------------------------------------------------------------------------- #
def write_csv(profiles: Sequence[Profile], path: str | Path) -> Path:
    """Write *profiles* to *path* as a clean, tabular UTF‑8 CSV.  Returns the path."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    header, rows = build_table(profiles)
    # ``utf-8-sig`` writes a BOM so spreadsheet apps detect UTF‑8 automatically.
    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)
    logger.info("Exported %d profile(s) to CSV: %s", len(profiles), path)
    return path


# --------------------------------------------------------------------------- #
# PDF (report)
# --------------------------------------------------------------------------- #
_ACCENT = "#4f46e5"
_INK = "#1c2330"
_MUTE = "#6b7280"
_FAINT = "#9aa1ad"
_GRID = "#d6dae1"
_ZEBRA = "#f5f6f9"


def build_report_html(profiles: Sequence[Profile], *, query: str = "", total: int = 0,
                      app_name: str = DEFAULT_APP_NAME) -> str:
    """Build the HTML used for the PDF report (a title, a context line, a table)."""
    header, rows = build_table(profiles)

    head_cells = "".join(
        f'<td bgcolor="{_ACCENT}" style="color:#ffffff;font-weight:bold;'
        f'{"width:30px;" if i == 0 else ""}">{escape(col)}</td>'
        for i, col in enumerate(["#", *header])
    )

    body_rows = []
    for index, row in enumerate(rows, start=1):
        bg = "#ffffff" if index % 2 else _ZEBRA
        cells = [f'<td bgcolor="{bg}" style="color:{_FAINT};">{index}</td>']
        for col_idx, value in enumerate(row):
            text = escape(value) if value else "&#8212;"
            colour = _INK if col_idx == 0 else "#39414e"
            weight = "font-weight:bold;" if col_idx == 0 else ""
            empty_colour = "" if value else f"color:{_FAINT};"
            cells.append(
                f'<td bgcolor="{bg}" style="color:{colour};{weight}{empty_colour}">{text}</td>'
            )
        body_rows.append(f"<tr>{''.join(cells)}</tr>")

    context = escape(_context_line(query, len(rows), total))
    safe_app = escape(app_name)
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="font-family:'Helvetica Neue','Segoe UI',Arial,sans-serif;color:{_INK};">
  <table width="100%" cellspacing="0" cellpadding="0"><tr><td>
    <div style="font-size:19pt;font-weight:bold;color:{_ACCENT};letter-spacing:0.3px;">{safe_app}</div>
    <div style="font-size:11pt;color:{_MUTE};margin-top:1px;">Search Results Report</div>
  </td></tr></table>
  <p style="font-size:8.5pt;color:{_FAINT};margin-top:9px;margin-bottom:14px;">{context}</p>
  <table width="100%" cellspacing="0" cellpadding="6" border="1"
         style="border-color:{_GRID};font-size:8.5pt;">
    <tr>{head_cells}</tr>
    {''.join(body_rows)}
  </table>
  <p style="font-size:7.5pt;color:{_FAINT};margin-top:16px;">
    This report contains only user-facing directory information &#8212; generated by {safe_app}.
  </p>
</body></html>"""


def write_pdf(profiles: Sequence[Profile], path: str | Path, *, query: str = "",
              total: int = 0, app_name: str = DEFAULT_APP_NAME) -> Path:
    """Render *profiles* to *path* as a styled, paginated PDF report.  Returns the path.

    Uses Qt's :class:`QTextDocument` / :class:`QPdfWriter` — imported here so the
    rest of this module stays Qt-free.
    """
    from PySide6.QtCore import QMarginsF
    from PySide6.QtGui import QPageLayout, QPageSize, QPdfWriter, QTextDocument

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    writer = QPdfWriter(str(path))
    writer.setPageSize(QPageSize(QPageSize.A4))
    writer.setPageMargins(QMarginsF(15, 14, 15, 16), QPageLayout.Unit.Millimeter)
    writer.setTitle(f"{app_name} — Search Results")
    writer.setCreator(app_name)

    document = QTextDocument()
    document.setDocumentMargin(0)
    document.setHtml(build_report_html(profiles, query=query, total=total, app_name=app_name))
    document.print_(writer)

    logger.info("Exported %d profile(s) to PDF: %s", len(profiles), path)
    return path
