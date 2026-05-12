# Windows Production Build Prompt — PeopleFinder (embedded Elasticsearch + `tc_index`)

> Hand this prompt to whoever (engineer or AI) builds the Windows release. It
> defines the deliverable, the hard constraints, the exact packaging strategy,
> and the acceptance criteria. **It is a packaging/build task only — application
> behaviour, the Elasticsearch integration, the queries and the UI must NOT
> change.**

---

## 0. Goal (one sentence)

Produce **one Windows installer (`PeopleFinder-Setup.exe`)** that an end user
double-clicks once; afterwards they open **PeopleFinder** from the Start Menu and
search by name / phone / email and get results — with **Python, Elasticsearch
(+ Java), and the full ~22 GB `tc_index` dataset all embedded inside the build**,
working **completely offline**, with **zero configuration** and **zero visible
backend**.

---

## 1. What exists today (do not touch)

* PySide6 desktop app. Entry point `main.py` → `app/gui/app.py` → `MainWindow`.
* Search pipeline: `app/controllers/app_controller.py` → `app/services/search_service.py`
  → `app/services/query_builder.py` (ES Query-DSL) → `app/database/es_client.py`
  (the official `elasticsearch` Python client) → Elasticsearch.
* Config (`app/config/settings.py`, optionally `.env`): `ES_HOST=https://localhost:9200`,
  `ES_USERNAME=elastic`, `ES_PASSWORD=admin123`, `ES_INDEX=tc_index`,
  `ES_VERIFY_CERTS=false`, `ES_TIMEOUT=30`.
* Startup already verifies the backend and waits on cluster health
  (`AppController.connection_status()` → ping → `GET /` → `GET /_cluster/health`
  → `HEAD /tc_index` → `GET /tc_index/_count`, all logged).
* `tc_index` currently holds ≈302 million documents (~22 GB).

**Constraint:** none of the above changes. Same client, same queries, same
search logic, same UI, same `tc_index`, same dataset (no reduction). The build
must make `https://localhost:9200` + `elastic`/`admin123` + `verify_certs=False`
work on the end user's machine *exactly as the code already expects it*, so the
application code needs **no changes at all** (the only new code is a small
deploy-layer "start/stop the embedded Elasticsearch" module — see §4).

---

## 2. Non-negotiable requirements

1. **One file delivered to the user:** `PeopleFinder-Setup.exe` (volume-split files allowed if needed).
2. **No prerequisites for the user:** no Python, no Java, no Elasticsearch, no Visual C++ runtime install, no service install they have to do. Everything is inside the installer.
3. **No configuration for the user:** no editing files, no setting hosts/ports/passwords, no creating an index, no loading data.
4. **`tc_index` (~22 GB, ~302M docs) is embedded in the build** and installed automatically; the user never sees, copies, or manages a database.
5. **Fully offline after install:** no downloads, no internet calls, no telemetry. (Downloading the Elasticsearch + JRE archives once *during the build* is fine; the *installer* is self-contained.)
6. **Elasticsearch runs hidden in the background**, started automatically when the app launches, stopped when the app (or Windows) closes — no console window, no tray icon the user must manage.
7. **Application functionality unchanged** — verified by diff: only `packaging/`, build scripts, and a new `app/services/embedded_es.py` (+ a one-call hook in startup) may be added.

---

## 3. Target stack & versions (pin and record them)

| Layer | Choice |
|---|---|
| End-user OS | Windows 10/11 64-bit |
| Python | 3.12.x — **private, bundled** (via PyInstaller; user installs nothing) |
| GUI | PySide6 — unchanged |
| Search engine | **Elasticsearch** — bundled, run as a local single node |
| Java | A **private OpenJDK/JRE** matching the bundled ES version's requirement (Adoptium/Temurin or Liberica) — never system Java |
| ES client | existing `elasticsearch` Python package — unchanged (note: keep client major version compatible with the bundled server) |
| App freezer | PyInstaller 6.x — **one-folder, windowed** |
| Installer | Inno Setup 6.3+ (`ISCC.exe`) |

> **License / redistribution — must be settled, not skipped.** Choose an
> Elasticsearch build you are permitted to redistribute for this use case (e.g.
> an Apache-2.0 7.10.2 build, or an SSPL/Elastic-License build under terms that
> allow it) and a redistributable OpenJDK build. Pin exact versions and record
> the licensing basis in `packaging/README.md`. The bundled ES major/minor must
> be able to open the `tc_index` shards (snapshot/restore handles this within the
> supported range; a raw data-dir copy does not — see §5 Step A).

---

## 4. The only new code allowed: `app/services/embedded_es.py` (+ one hook)

A small "managed local Elasticsearch" module. Responsibilities — nothing more:

* **Resolve paths (frozen-aware):** locate the bundled ES home, the bundled JRE,
  and a **writable** data/logs/config directory. Elasticsearch *must* write to a
  user-writable location — use `%LOCALAPPDATA%\PeopleFinder\` (Program Files is
  read-only at runtime). The installer should place the 22 GB data dir there
  directly (see §5 Step D) so first launch doesn't have to copy it.
* **Make `https://localhost:9200` + `elastic:admin123` work as the app expects.**
  Configure the embedded node so the existing client config is correct verbatim:
  * `network.host: 127.0.0.1`, `http.port: 9200` (the value the app uses).
  * `discovery.type: single-node`.
  * `path.data` / `path.logs` → the writable dir; `path.repo` if you used snapshots.
  * `xpack.security.enabled: true` with **HTTPS** enabled using a bundled (or
    first-run-generated) self-signed cert — the app uses `verify_certs=False`, so
    a self-signed cert is fine.
  * Set the built-in `elastic` user's password to `admin123` — either via
    `bin\elasticsearch-reset-password -u elastic -i` / `--auto`-then-set during
    the build payload prep, or by baking it into the ES keystore
    (`bin\elasticsearch-keystore`), or by first-run `ELASTIC_PASSWORD=admin123`
    with security auto-config. Whatever is chosen, it must be deterministic and
    require no user action.
  * `ingest.geoip.downloader.enabled: false`, `xpack.ml.enabled: false`,
    `bootstrap.memory_lock: false`. Bound the heap (`-Xms`/`-Xmx`, e.g. 1–2 GB or
    scaled to RAM with a cap) via `jvm.options.d` / `ES_JAVA_OPTS`. Point
    `ES_JAVA_HOME` at the bundled JRE.

  *(Alternative, if a single one-line config change is acceptable: disable
  security on the embedded node and point the app at `http://127.0.0.1:9200` via
  an env/config value. Default to the security-on path above so the app config is
  literally unchanged.)*

* **Port handling:** port 9200 matches the app's config; if it's already in use,
  detect it, log it, and surface a clean error ("another program is using port
  9200"). (Do not silently move ports — that would require an app-config change.)
* **Launch ES as a hidden background child process** of the app
  (`elasticsearch.bat` / the binary, `CREATE_NO_WINDOW`, stdio → app log). It
  dies with the app and needs no admin at runtime. *(Option B: register/start a
  Windows service — heavier; only if a persistent daemon is genuinely wanted.)*
* **Wait for readiness:** poll `GET https://127.0.0.1:9200/_cluster/health` until
  `yellow`/`green` (single-node ⇒ `yellow` is normal), with a generous timeout
  (a 22 GB index can take a while to open on first/cold start) and a "Starting…"
  UI state. *(The app's existing `connection_status()` already polls health — the
  bootstrap just has to make sure ES is up first.)*
* **Single-instance guard:** never start a second ES on the same data dir (that
  corrupts it). If the app is already running, reuse the node or exit cleanly.
  Use a PID/lock file; reap a stale PID on next start.
* **Graceful shutdown** on app exit *and* on crash: terminate the ES process
  tree (and its `java.exe`); idempotent `stop()`; hook it into the Qt
  `closeEvent` and `atexit`. A force-killed UI must not leave a zombie ES.

**The one hook:** in app startup (e.g. `app/gui/app.py` / `main.py`), before the
ES client is first used: `embedded_es.start()` (show "Starting…"); on shutdown:
`embedded_es.stop()`. That's it. Search, query-builder, UI: untouched.

---

## 5. Build pipeline (run once, on a build machine that can reach the current `tc_index`)

### Step A — produce a portable Elasticsearch data directory containing `tc_index`

Script this in `tools/prepare_es_payload.py`. Prefer **snapshot & restore** (clean, version-portable):

1. On the source cluster, register an `fs` snapshot repo and
   `PUT /_snapshot/<repo>/<snap>?wait_for_completion=true` for `tc_index`.
2. Start a *throwaway local* Elasticsearch — **the exact build you will bundle** —
   with an empty `path.data`; restore the snapshot into it; optionally
   `POST /tc_index/_flush` + `POST /tc_index/_forcemerge?max_num_segments=1` for a
   smaller, faster read-mostly index; then **shut it down cleanly**.
3. The resulting `path.data` directory is the payload (call it `runtime/es-data/`).
4. Verify: start a throwaway ES on `runtime/es-data/`, confirm
   `GET /tc_index/_count` equals the source count, run a few sample name/phone/
   email queries, then stop it. Record the doc count.

*(Alternative — raw cold copy: only if the source node already runs the exact
bundled version and can be stopped; copy its `path.data`. Less portable.)*

### Step B — assemble the embedded runtime (`runtime/`)

* Download once and extract the chosen Elasticsearch distribution → `runtime/elasticsearch/`.
* Provide a private JRE → `runtime/jre/` (or keep the JDK the ES archive bundles).
* Trim to shrink: remove `modules/x-pack-ml`, `modules/x-pack-watcher`,
  `modules/ingest-geoip` & `modules/ingest-user-agent` data, the bundled `jdk/` if
  you ship a separate JRE, unused `*.bat`, docs/examples — **and test after each
  removal** (ES rejects missing modules). Pre-place certs/keystore/`jvm.options.d`
  as appropriate (the *effective* runtime config still gets written into the
  writable dir at first run).
* Put the Step A payload at `runtime/es-data/`.

### Step C — freeze the app with PyInstaller (`packaging/PeopleFinder.spec`)

* One-folder, `console=False`. (One-file is **forbidden** here — extracting tens
  of GB to a temp dir on every launch is unusable.)
* `datas`: include `runtime/elasticsearch/` and `runtime/jre/` so they land
  inside `dist/PeopleFinder/`. **Do NOT** run the 22 GB `runtime/es-data/`
  through PyInstaller — the installer ships it as a separate payload (Step D).
* `hiddenimports`: add `elasticsearch`, `elastic_transport`, `urllib3`, `certifi`
  if PyInstaller misses them. Exclude unused heavy Qt modules (WebEngine, Quick3D,
  Multimedia, Charts, …) to keep the bundle lean.
* Output: `packaging/dist/PeopleFinder/` = `PeopleFinder.exe` + `_internal/…` +
  `elasticsearch/…` + `jre/…`.

### Step D — build the installer (`packaging/installer.iss`, Inno Setup 6.3+)

* `[Files]`:
  * `dist\PeopleFinder\*` → `{app}` (recurse).
  * `runtime\es-data\*` → **`{localappdata}\PeopleFinder\es-data`** (writable
    immediately, no first-run 22 GB copy). The uninstaller must remove it (it's
    the 22 GB).
* `[Setup]`: `Compression=lzma2/max`, `SolidCompression=yes`,
  `DisableDirPage=no` (let the user pick the install drive — it's a big app),
  `PrivilegesRequired=admin`, `ArchitecturesInstallIn64BitMode=x64compatible`,
  a stable `AppId` GUID. Optional `DiskSpanning`/`DiskSliceSize` to split the
  large installer into fixed-size volumes for USB/DVD.
* `[Icons]`: Start-Menu + optional Desktop shortcut → `{app}\PeopleFinder.exe`.
* `[Run]`: optionally launch after install.
* Uninstall (`[UninstallRun]` / `[UninstallDelete]` / `[Code]`): first stop ES
  (kill `PeopleFinder.exe` and its `java.exe`/`elasticsearch` children, or stop
  the service if used), then remove `{app}` and `{localappdata}\PeopleFinder\`
  (es-data, logs, history). Be explicit about the data dir.
* Output: `packaging\Output\PeopleFinder-Setup.exe`.

### Step E — one-shot build script (`packaging/build_windows.bat`)

`create build venv → pip install (PySide6, elasticsearch, python-dotenv, pyinstaller) → tools\prepare_es_payload.py (or verify runtime/ already populated) → pyinstaller packaging\PeopleFinder.spec → ISCC packaging\installer.iss`. Fail loudly if `runtime\elasticsearch`, `runtime\jre`, or `runtime\es-data` is missing or `es-data` is implausibly small.

---

## 6. End-user experience (the acceptance experience)

1. Double-click `PeopleFinder-Setup.exe` → choose folder/drive → Install. The
   wizard reports the (large) space needed.
2. Open **PeopleFinder** from the Start Menu. A brief "Starting…" appears while
   the embedded Elasticsearch comes up (longest on the first/cold launch).
3. The search box appears. Type a **name / phone number / email** → Enter →
   instant, clean profile cards from `tc_index` — identical results to the
   current system (same engine, same queries).
4. Close the window → embedded Elasticsearch is shut down automatically. No
   console, no tray icon, no port the user ever deals with.
5. Reboot → reopen → ES starts again from the same local data dir. Still offline,
   still zero config.
6. Uninstall via *Add/Remove Programs* → ES stopped, everything removed
   (including the per-user 22 GB data dir).

---

## 7. Acceptance criteria — the build is "done" only when ALL pass

* [ ] The deliverable is one `PeopleFinder-Setup.exe` (optionally + volume files). Nothing else handed to the user.
* [ ] On a **clean Windows 10/11 VM with no Python, no Java, no Elasticsearch, no internet**: install → launch → search by name/phone/email → correct results, with no prompts, no config, no manual steps.
* [ ] The embedded node serves `https://localhost:9200`, `elastic`/`admin123`, `verify_certs=False` — i.e. the app's existing config is correct **with no code change**.
* [ ] `GET /tc_index/_count` on the embedded node equals the recorded source count; mapping/analyzers match the original. No dataset reduction.
* [ ] `git diff` shows **only** packaging files, build scripts, and `app/services/embedded_es.py` + a one-call startup hook — search/query/UI code unchanged.
* [ ] App start reliably starts ES; app close reliably stops it; force-killing the UI leaves no zombie `java.exe`; a second launch never starts a second ES on the same data dir.
* [ ] ES data lives in a writable per-user location; the app works without admin rights after install. First launch never needs ~44 GB free transiently.
* [ ] Uninstall removes everything (incl. the 22 GB data dir) and leaves no running ES.
* [ ] First-launch and warm-launch times measured and documented; default heap bounded and sane on small (8 GB) and large (64 GB) machines.
* [ ] Bundled Elasticsearch build and JRE: licensing/redistribution verified and documented; versions pinned.

---

## 8. Risks & decisions to call out explicitly (don't hand-wave)

* **Installer size & build time.** ~22 GB data dir → a multi-GB installer and a
  slow `lzma2/max` + solid-compression pass (lots of RAM/time). Lucene segments
  are already fairly compact, so expect less shrink than plain text. Decide: one
  big file vs. `DiskSpanning` volumes. (Use `Compression=lzma2/fast` while
  iterating.)
* **Java is required.** Bundle a private JRE/JDK (or use an ES distro that
  bundles one); never depend on system Java; match the Java version to the ES
  version.
* **Port 9200 conflict.** Matching the app's fixed config means a hard dependency
  on 9200 being free. Detect and report cleanly; document it.
* **First-run data placement.** Install `es-data` straight to
  `%LOCALAPPDATA%\PeopleFinder\es-data` so it's writable with no copy. Installing
  to Program Files and copying 22 GB on first run = very slow first launch +
  needs ~44 GB free transiently.
* **Antivirus / SmartScreen.** A large unsigned installer plus a background
  `java.exe` listening on a socket will trip Defender/SmartScreen. Plan code
  signing (`signtool` on `PeopleFinder.exe` *inside* `dist\PeopleFinder\` before
  ISCC, and on `PeopleFinder-Setup.exe`); consider an EV certificate for
  reputation. Inno Setup also has a `SignTool` directive.
* **ES version pinning.** The bundled ES must open the `tc_index` shards
  (snapshot/restore handles cross-version within support range; a raw copy does
  not). Pin and test. Also keep the `elasticsearch` Python client major version
  compatible with the bundled server.
* **Resource use on the user's box.** ES + JVM idle RAM (hundreds of MB to GBs).
  Document it; cap the heap.
* **Upgrades.** Keep the same `AppId` so a new installer replaces the old app;
  decide whether a new release also ships a refreshed `es-data`.

---

## 9. Deliverables checklist

1. `app/services/embedded_es.py` — start/stop/health of the local embedded ES, configured so the existing app config works verbatim — **plus the single startup/shutdown hook**. No other app changes.
2. `tools/prepare_es_payload.py` — snapshot/restore → `runtime/es-data/`, with verification (doc count + sample queries).
3. `runtime/` assembly instructions/script — pinned ES distro + private JRE, trimmed and tested, plus the `es-data/` payload.
4. `packaging/PeopleFinder.spec`, `packaging/installer.iss`, `packaging/build_windows.bat`, `packaging/README.md` (build steps, pinned versions, license basis, recorded `tc_index` doc count, measured installer size, first/warm launch times, default heap).
5. A clean-VM test report covering every item in §7.

**Bottom line: keep the application and its Elasticsearch integration exactly as
they are. Only build, package, and embed — Elasticsearch and `tc_index` are
bundled, never replaced, never reduced.**
