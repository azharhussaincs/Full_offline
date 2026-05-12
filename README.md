# PeopleFinder

A **fully-offline, premium desktop application** for searching people in an
Elasticsearch index — built with **Python** and **PySide6 (Qt 6)** on a clean,
modular architecture.

The experience is intentionally tiny:

> **Open the app → type a name, phone number or e-mail → press Search → read clean profile cards.**

That's it. No tables, no JSON, no `_id` / `_score`, no sidebars, menus or
developer controls — just a polished, SaaS-style UI.

---

## ✨ What it looks like

**Initial state** — an inviting prompt:

```
                              PeopleFinder
              Search the directory by name, phone number or e-mail
        ┌──────────────────────────────────────────────┐  ┌────────┐  ┌───────┐
        │ 🔍  Search by name, phone number or e-mail…   │  │ Search │  │ Clear │
        └──────────────────────────────────────────────┘  └────────┘  └───────┘
   ────────────────────────────────────────────────────────────────────────────
                                   ╭───╮
                                   │ 🔍 │
                                   ╰───╯
                              Find a person
            Search by name, phone number or e-mail address to see
                         matching profiles here.
   ────────────────────────────────────────────────────────────────────────────
                                                              ● Connected
```

**Results** — each match is an elegant profile card (rounded corners, soft
shadow, aligned labels, generous spacing, selectable values):

```
   ┌──────────────────────────────────────────────────────────────────────┐
   │  ╭────╮   Ali Khan                                                    │
   │  │ AK │   ─────────────────────────────────────────────────────────   │
   │  ╰────╯   PHONE       0300 1234567                                     │
   │           EMAIL       ali.khan@gmail.com                              │
   │           ADDRESS     Gulberg III, Lahore, Pakistan                   │
   └──────────────────────────────────────────────────────────────────────┘
   ┌──────────────────────────────────────────────────────────────────────┐
   │  ╭────╮   Sara Ahmed                                                   │
   │  │ SA │   ─────────────────────────────────────────────────────────   │
   │  ╰────╯   PHONE       +44 20 7946 0102                                │
   │           EMAIL       sara.ahmed@example.org                          │
   └──────────────────────────────────────────────────────────────────────┘
                            ┌─────────────────────┐
                            │  Show more results  │
                            └─────────────────────┘
   ────────────────────────────────────────────────────────────────────────
   Showing 20 of 1,284 matches                              ● Connected
```

* **Searching** → a smooth spinner + "Searching… / Looking for "…"".
* **No results** → a friendly empty-state ("No matches found …").
* **Errors** → a clean popup ("We couldn't reach the data service…").

The UI never freezes — every Elasticsearch call runs on a background thread.

---

## 🎨 Design

* Premium **light** theme — clean, minimal, lots of whitespace, one indigo
  accent, hair-line borders, soft shadows, rounded corners.
* Modern input field with an inline search glyph and a built-in clear button;
  elegant primary / ghost buttons with hover & pressed states.
* Card-based results with a coloured monogram avatar per person, a thin divider,
  and a perfectly-aligned `LABEL → value` grid (values wrap cleanly, never
  collide, and are selectable so a phone/e-mail can be copied).
* Responsive: content is centred with a sensible maximum width and reflows
  gracefully when the window is resized; results scroll inside their own area.

---

## 🗂 Project structure

```
Fully_offline/
├── main.py                       # Entry point  ->  python main.py
├── run.sh                        # Launcher (activates ./venv, runs main.py)
├── requirements.txt              # elasticsearch, PySide6, python-dotenv
├── .env.example                  # Copy to ".env" and edit
├── .gitignore
├── README.md
│
├── app/
│   ├── config/
│   │   ├── settings.py           # Immutable Settings dataclass, loaded from .env / env
│   │   └── logging_config.py     # configure_logging() + get_logger()
│   ├── database/
│   │   └── es_client.py          # ESClient — lazy singleton wrapper around Elasticsearch
│   ├── models/
│   │   ├── search_models.py      # SearchType, SearchQuery, Document, SearchResult
│   │   └── profile.py            # Profile, ProfileField, ProfilePage  (UI view-models)
│   ├── services/
│   │   ├── index_service.py      # exists / count / mapping-fields
│   │   ├── query_builder.py      # build robust, mapping-aware Elasticsearch Query-DSL
│   │   └── search_service.py     # run searches, map raw hits -> domain objects
│   ├── controllers/
│   │   └── app_controller.py     # AppController.find(text) -> ProfilePage   (no Qt imports)
│   ├── utils/
│   │   ├── detector.py           # auto-detect name / phone / e-mail
│   │   ├── validators.py         # input validation
│   │   ├── profile_mapper.py     # raw _source dict  ->  clean Profile (Name/Phone/Email/Address…)
│   │   ├── export.py             # (kept for reuse; not used by the UI)
│   │   └── history.py            # quiet, on-disk recent-search log (not shown in the UI)
│   └── gui/
│       ├── app.py                # create_application() / run()
│       ├── theme.py              # colour tokens + the Qt Style Sheet (premium light theme)
│       ├── icons.py              # programmatically-drawn icons (no asset files)
│       ├── workers.py            # Worker(QThread) — run blocking calls off the UI thread
│       ├── main_window.py        # MainWindow — header + results + footer, wires it together
│       └── widgets/
│           ├── search_header.py  # title + tagline + search field + Search/Clear buttons
│           ├── results_view.py   # stacked: initial / loading / results(scroll+cards) / no-results
│           ├── result_card.py    # ResultCard — one elegant profile card
│           ├── avatar.py         # Avatar — circular monogram with a name-derived colour
│           ├── spinner.py        # Spinner — smooth indeterminate loading arc
│           ├── states.py         # MessageState / LoadingState — the centred empty/loading screens
│           └── status_footer.py  # StatusFooter — results summary + connection dot
│
├── tools/
│   └── seed_data.py              # OPTIONAL: insert a few sample people into the index for testing
├── logs/                         # created at runtime — rotating log files
└── exports/                      # created at runtime (only used if you call the export utility)
```

### What each file does (short version)

* **`main.py`** — makes the project root importable, configures logging, calls
  `app.gui.app.run()`. The only thing you run.
* **`app/config/settings.py`** — reads `.env` / environment **once** into an
  immutable `settings` object (Elasticsearch host/credentials/index, page size,
  logging). The single source of configuration; credentials are never hard-coded.
* **`app/config/logging_config.py`** — rotating file log (`logs/app.log`,
  5 × 2 MB) + console; `get_logger("x")` → namespaced child logger.
* **`app/database/es_client.py`** — the **only** module that imports the raw
  Elasticsearch client; lazy singleton (`ESClient.instance()`) with `ping()`,
  `cluster_info()`, `client`, `close()`. `verify_certs` is driven by
  `ES_VERIFY_CERTS` (off by default for self-signed/offline clusters; TLS
  warnings are silenced in that case).
* **`app/models/search_models.py`** — framework-agnostic search dataclasses.
* **`app/models/profile.py`** — the **only** shape the UI sees: `Profile`
  (name + ordered `ProfileField`s, plus avatar `initials`) and `ProfilePage`
  (a page of profiles with `total` / `has_more`). No `_id`/`_score`/etc. — ever.
* **`app/services/index_service.py`** — read-only index helpers (`index_exists`,
  `count`, `get_mapping_fields`).
* **`app/services/query_builder.py`** — turns a query into Query-DSL: a broad
  `multi_match` over **all** fields (`["*"]`, `lenient`) so it works on *any*
  mapping, **plus** boosted `match` clauses on the field names commonly used for
  the detected type (name / phone / e-mail) when they exist in the mapping;
  digit-normalised phone matching. `simple_search_body()` is the always-valid
  fallback used if Elasticsearch ever rejects the rich query.
* **`app/services/search_service.py`** — executes searches (with the safe
  fallback retry), memoises each index's field list, maps raw hits → `Document`s.
* **`app/controllers/app_controller.py`** — the façade the GUI calls.
  `connection_status()` and `find(text, page, page_size) -> ProfilePage`
  (validates input, auto-detects type, searches, maps each hit through
  `profile_mapper`). **No Qt imports** — this layer + the services could back a
  CLI or a REST API unchanged.
* **`app/utils/detector.py`** — `detect_search_type()` (regex heuristics) plus
  the per-type candidate field names.
* **`app/utils/profile_mapper.py`** — maps an arbitrary `_source` dict onto a
  clean `Profile`: finds the name (`name` / `NAME` / `full_name` /
  `first_name`+`last_name` …), phone(s), e-mail(s) and address (joining nested
  `{street, city, country}` objects or `city`/`state`/… parts into one line),
  humanises any remaining useful fields, formats values nicely (lists →
  comma-joined, ISO timestamps → date, booleans → Yes/No), and **drops all
  technical metadata**.
* **`app/utils/validators.py`** — `validate_search_text()` etc.
* **`app/utils/export.py`** / **`history.py`** — reusable helpers kept for
  future use; the export utility is not wired into this minimal UI, and search
  history is recorded quietly to disk but never shown.
* **`app/gui/app.py`** — builds the `QApplication`, applies the theme, shows the
  window.
* **`app/gui/theme.py`** — all the colours + the global Qt Style Sheet.
* **`app/gui/icons.py`** — the app icon and the search glyph, drawn at runtime.
* **`app/gui/workers.py`** — `Worker(QThread)`: runs `fn(*args)` off the UI
  thread and emits `succeeded` / `failed`.
* **`app/gui/main_window.py`** — `MainWindow`: header (search) on top, the
  results area in the middle, the status footer at the bottom; connects the
  signals; runs all data work via `Worker`.
* **`app/gui/widgets/…`** — the reusable components listed in the tree above.
* **`tools/seed_data.py`** — optional; inserts a few sample people (ids
  `sample-1…8`) so you have something to search. It **refuses** to write to /
  reset an index that already has more than 1,000 documents unless `--force` is
  given, so it can't clobber a populated index.

---

## 🔧 Requirements

* **Python 3.10+** (3.12+ recommended).
* **Linux** (also runs on macOS / Windows; the commands below are for Linux).
* A running **Elasticsearch** instance reachable at the URL in your `.env`
  (default `https://localhost:9200`). Tested against Elasticsearch 8.x and 9.x.
* On a headless box you also need basic Qt/X libraries, e.g. on Debian/Ubuntu:
  `sudo apt install libgl1 libxkbcommon0 libegl1 libfontconfig1`.

---

## 🚀 Setup & run — complete commands

```bash
# 0. Go to the project directory
cd /home/albaloshi/Desktop/Fully_offline

# 1. Create a virtual environment
python3 -m venv venv

# 2. Activate the virtual environment            (deactivate later with: deactivate)
source venv/bin/activate

# 3. Install the dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt

# 4. Create your .env from the template
cp .env.example .env
#    Defaults already match the assignment:
#      ES_HOST=https://localhost:9200
#      ES_USERNAME=elastic
#      ES_PASSWORD=admin123
#      ES_INDEX=tc_index
#      ES_VERIFY_CERTS=false

# 5. (OPTIONAL) Seed a few sample people so you have something to search
python tools/seed_data.py
#    -> refuses to touch an index that already has > 1,000 docs (use --force to override).
#    Remove the samples later with:
#      curl -k -u elastic:admin123 -XPOST \
#        "https://localhost:9200/tc_index/_delete_by_query?refresh=true" \
#        -H 'Content-Type: application/json' \
#        -d '{"query": {"ids": {"values": ["sample-1","sample-2","sample-3","sample-4","sample-5","sample-6","sample-7","sample-8"]}}}'

# 6. Run the application
python main.py
#    ...or simply:
./run.sh
```

> If `python3 -m venv venv` fails, install the venv package
> (`sudo apt install python3-venv`).

---

## 🖥 Using it

1. The footer shows **● Connected** (green) when the data service answers, or
   **● Not connected** (red) otherwise.
2. Type a **name**, **phone number** or **e-mail** and press **Enter** (or click
   **Search**). The app auto-detects what you typed — there's nothing to
   configure.
3. Read the **profile cards**. Select any value to copy it (e.g. a phone
   number). Click **Show more results** to load the next page.
4. **Clear** empties the box and returns to the start screen.

---

## 🧱 Architecture & best practices

* **Layered, dependency-directed**: `gui → controllers → services → database`,
  with `models` / `utils` at the bottom. Nothing imports "upwards"; the
  controller and everything below it are **Qt-free** and unit-testable.
* **Single configuration source** (`settings`, immutable, loaded once from
  `.env`); **credentials only in `.env`**, never in source.
* **Singleton ES client** — one lazily-created transport.
* **Non-blocking UI** — every Elasticsearch call runs on a `QThread`.
* **Defensive querying** — works on *any* mapping and falls back to a minimal
  query if Elasticsearch ever rejects the rich one; never crashes on an
  unreachable cluster or a missing index.
* **Strict UI/data separation** — the GUI only ever handles `Profile` /
  `ProfilePage` view-models, so technical metadata can't leak onto the screen.
* **Reusable components**, **type hints**, **docstrings** and **logging**
  throughout.

---

## 🔭 Future improvements

* Match highlighting on cards (Elasticsearch `highlight`).
* Optional **dark theme** toggle.
* Keyboard navigation between result cards; "copy card" / "copy all visible".
* Async client (`elasticsearch[async]` + `qasync`) instead of `QThread`.
* A FastAPI/CLI front-end reusing `AppController` + the service layer — the
  architecture already supports it.
* Field-mapping overrides per dataset (a small config to say "the address lives
  in field X"), and result export from the UI (the `export` utility already
  exists).
* PyInstaller packaging + a `.desktop` launcher; i18n / accessibility polish.

---

## ❓ Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| Footer says **Not connected** | Elasticsearch isn't running, wrong `ES_HOST`/credentials, or a TLS mismatch — check `.env` (keep `ES_VERIFY_CERTS=false` for self-signed certs). See `logs/app.log`. |
| Popup: *"The directory could not be found …"* | The configured index (`tc_index`) doesn't exist — seed it (`python tools/seed_data.py`) or point `ES_INDEX` at an existing index. |
| `qt.qpa.plugin: could not load the Qt platform plugin "xcb"` | Install the Qt/X libs (see *Requirements*) or run on a machine with a display / X-forwarding. |
| `ModuleNotFoundError: PySide6` | The virtualenv isn't active / deps aren't installed — `source venv/bin/activate && pip install -r requirements.txt`. |
| A search seems slow | Single-term name searches are instant; an exact phone lookup scans more fields and can take a second or two on a very large index — this is expected and the UI stays responsive. |
# Full_offline
