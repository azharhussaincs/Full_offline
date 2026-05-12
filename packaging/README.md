# Packaging PeopleFinder for Windows (embedded Elasticsearch + `tc_index`)

This turns the existing Python + PySide6 + Elasticsearch app into **one Windows
installer** (`PeopleFinder-Setup.exe`) that bundles:

* a private Python runtime + PySide6 (the user installs nothing),
* the application — **unchanged**: same `elasticsearch` client, same queries,
  same search logic, same UI,
* a private **Elasticsearch** distribution (including its own JDK), and
* the full **`tc_index`** data directory (~22 GB).

After installing, the user opens **PeopleFinder** from the Start Menu and
searches by name / phone / email. Elasticsearch runs hidden in the background
(started by the app, stopped on exit), there is **no configuration**, and it
works **completely offline**. Nothing about the application's behaviour changes —
only packaging.

> The full design rationale is in `packaging/WINDOWS_PRODUCTION_BUILD_PROMPT.md`.

---

## What changed in the app (the *only* code change)

* **New:** `app/services/embedded_es.py` — a small "managed local Elasticsearch"
  module: locates the bundled ES (`<app>\elasticsearch\`), starts it as a hidden
  child process pointed at `%LOCALAPPDATA%\PeopleFinder\es-data`, waits until it
  answers, and stops it on exit. When there is **no** bundled ES (a normal source
  checkout) every function is a **no-op**, so development is unaffected.
* **Hook (2 lines):** `AppController.connection_status()` calls
  `embedded_es.ensure_started()` before its existing checks; `AppController.shutdown()`
  calls `embedded_es.stop()`. Nothing else in the app is touched.

The bundled Elasticsearch is configured so the app's existing connection
settings work verbatim: `https://localhost:9200`, user `elastic`, password
`admin123`, `verify_certs=False`, index `tc_index`.

---

## Files in this folder

| File | Purpose |
|---|---|
| `WINDOWS_PRODUCTION_BUILD_PROMPT.md` | The engineering prompt / design spec. |
| `PeopleFinder.spec` | PyInstaller recipe — freezes the app and bundles `runtime/elasticsearch/`. |
| `configure_bundled_es.py` | Prepares a downloaded ES distribution for bundling (base settings; optionally sets the `elastic` password). |
| `make_icon.py` | Renders `app.ico` from the app's built-in icon (called by the build script). |
| `installer.iss` | Inno Setup script — packs the frozen app + `runtime/es-data/` into one `.exe`. |
| `build_windows.bat` | One-shot build: venv → checks → icon → PyInstaller → Inno Setup. |

Build outputs (git-ignored): `packaging/build/`, `packaging/dist/`,
`packaging/Output/`, `packaging/app.ico`, `runtime/`, `.build-venv/`.

Related: `tools/prepare_es_payload.py` builds `runtime/es-data/` from your live
`tc_index`.

---

## Prerequisites (on the **build** machine only)

1. **Windows 64-bit**, **Python 3.10–3.12** on `PATH`.
2. **Inno Setup 6.3+** — <https://jrsoftware.org/isdl.php> (gives you `ISCC.exe`).
3. An **Elasticsearch distribution** matching your source cluster's version
   (Windows `.zip`, which includes its own `jdk/`).
4. Filesystem (or snapshot) access to the live `tc_index`.
5. Lots of free disk: roughly **3× the data size** during the build (the raw
   `es-data`, the PyInstaller copy is small but the Inno Setup compression pass
   needs scratch space, plus the finished installer).

The build script makes its own venv (`.build-venv`) and installs
`requirements.txt` + `pyinstaller` — nothing to set up by hand.

---

## Step 1 — prepare the bundled Elasticsearch distribution

1. Download the Elasticsearch **Windows `.zip`** for the version your source
   cluster runs (check it: `GET https://localhost:9200/` → `.version.number`).
   Extract it to `runtime\elasticsearch\` (so `runtime\elasticsearch\bin\elasticsearch.bat`
   exists, and `runtime\elasticsearch\jdk\` is present).
2. Configure it for bundling:
   ```bat
   python packaging\configure_bundled_es.py --es-home runtime\elasticsearch
   ```
   This writes the required base settings to `config\elasticsearch.yml`
   (`discovery.type: single-node`, `network.host: _local_`, `http.port: 9200`,
   geoip downloader off, enrollment off, …).

   The `elastic` password and the TLS certificates live in *data* and *config*
   respectively, so what you do next depends on Step 2:
   * If you build the data payload by **cold copy with `--source-config`**
     (recommended), the source node's `config/` (TLS + keystore) and its
     `.security` index come along — `elastic`/`admin123` already works; nothing
     more to do here.
   * If you build it by **snapshot/restore** (no `.security` restored), also run:
     ```bat
     python packaging\configure_bundled_es.py --es-home runtime\elasticsearch ^
         --set-password --data-dir runtime\es-data --verify
     ```
     after Step 2 — it does the one-time `ELASTIC_PASSWORD=admin123` first-start
     so the password is stored in the payload, lets ES auto-generate TLS certs,
     and verifies `elastic`/`admin123` over HTTPS.

> **Trim it** (optional, to shrink the bundle): remove `modules\x-pack-ml`,
> `modules\x-pack-watcher`, `modules\ingest-geoip` & `modules\ingest-user-agent`
> data, unused docs — **and test after each removal** (ES rejects missing
> modules). Keep `jdk\`. (Beside ~22 GB of data this is noise; trimming is
> optional.)

---

## Step 2 — build the `tc_index` data payload (`runtime\es-data\`)

**Option A — cold copy (simplest; needs the source ES stopped):**
```bat
:: stop your source Elasticsearch first!
python tools\prepare_es_payload.py --mode cold-copy ^
    --source-data  "C:\path\to\elasticsearch\data" ^
    --source-config "C:\path\to\elasticsearch\config" ^
    --out runtime\es-data --es-home runtime\elasticsearch --verify
```
Copies the source node's `data\` (the `tc_index` index *and* the `.security`
index, so `elastic`/`admin123` keeps working) to `runtime\es-data\`, and its
`config\` (TLS, keystore) into `runtime\elasticsearch\config\`. `--verify`
briefly launches the bundled ES on the copy and checks `GET /tc_index/_count`
plus a couple of sample searches.

**Option B — snapshot/restore (keeps the source ES running):**
```bat
:: the SOURCE cluster must have  path.repo: [ "D:\es-snap-repo" ]  in its
:: elasticsearch.yml (then restart it); the tool tells you if it doesn't.
python tools\prepare_es_payload.py --mode snapshot ^
    --host https://localhost:9200 --user elastic --password admin123 --insecure ^
    --repo-path "D:\es-snap-repo" ^
    --out runtime\es-data --es-home runtime\elasticsearch --verify
```
Then run the `configure_bundled_es.py --set-password …` command from Step 1.

After this, `runtime\es-data\` is the payload (≈ your `tc_index` size) and
`runtime\elasticsearch\` is the configured distribution.

---

## Step 3 — build the installer

```bat
packaging\build_windows.bat
```

It runs all six steps (venv → verify `runtime\elasticsearch` → verify
`runtime\es-data` → icon → PyInstaller → Inno Setup) and, on success, prints:

```
packaging\Output\PeopleFinder-Setup.exe
```

Prefer to run it yourself? From the project root:
```bat
python -m venv .build-venv
.build-venv\Scripts\python -m pip install -r requirements.txt pyinstaller
.build-venv\Scripts\python packaging\make_icon.py
.build-venv\Scripts\python -m PyInstaller packaging\PeopleFinder.spec --noconfirm ^
    --distpath packaging\dist --workpath packaging\build
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\installer.iss
```

---

## What the end user gets

* **One file:** `PeopleFinder-Setup.exe`. Double-click → choose folder/drive → Install.
* Installs the app + bundled Elasticsearch to `C:\Program Files\PeopleFinder\`
  and the `tc_index` data to `C:\Users\<user>\AppData\Local\PeopleFinder\es-data\`
  (a writable per-user location — no admin needed at runtime, no slow first-run copy).
* Start-Menu (and optionally Desktop) shortcut: **PeopleFinder**.
* Opening it shows a brief "Starting search engine…" while Elasticsearch comes
  up (longest on the first cold launch), then the search box. Search by name /
  phone / email → results from `tc_index` — identical to the existing system.
* Closing the app stops Elasticsearch automatically. No console, no tray icon,
  no port the user deals with.
* Uninstall via *Add/Remove Programs* stops Elasticsearch and removes everything,
  including `%LOCALAPPDATA%\PeopleFinder\` (the ~22 GB data dir, logs, history).
* **No** Python, **no** Java, **no** Elasticsearch to install; **no** configuration; **no** internet.

---

## Notes & tuning

* **Installer size / build time.** A ~22 GB payload makes a large installer, and
  `Compression=lzma2/max` + `SolidCompression=yes` is slow and RAM-hungry to
  build (Lucene segments are already fairly compact, so don't expect much
  shrink). While iterating, set `Compression=lzma2/fast` (or `none`) in
  `installer.iss`. To fit fixed-size media, uncomment `DiskSpanning` /
  `DiskSliceSize` there to split into volumes.
* **Port 9200.** The app's config uses port 9200; the bundled node binds 9200.
  If something else already uses 9200 on the user's machine, ES will fail to
  start and the app's status check will report "not connected" (logged in
  `%LOCALAPPDATA%\PeopleFinder\logs\app.log` and `…\es-logs\`).
* **Heap.** `embedded_es.py` sets the ES heap (`-Xms/-Xmx`) to ~¼ of RAM, clamped
  to 1–4 GB. Tune `_heap_opts()` if needed.
* **Version match.** The bundled Elasticsearch must be able to open the
  `tc_index` shards. A cold copy requires the *same* version as the source; a
  snapshot/restore works across versions within Elasticsearch's supported range.
  Keep the `elasticsearch` Python client major version compatible with the
  bundled server (`requirements.txt`).
* **Code signing.** For a polished release, sign `PeopleFinder.exe` (inside
  `packaging\dist\PeopleFinder\` before running ISCC) and the resulting
  `PeopleFinder-Setup.exe` with `signtool.exe` + your certificate (Inno Setup
  also has a `SignTool` directive). A large unsigned installer plus a background
  `java.exe` on a socket will trip Defender/SmartScreen otherwise.
* **Rebuild after a code change only** (data unchanged): just re-run
  `build_windows.bat` — it reuses `runtime\elasticsearch\` and `runtime\es-data\`.
* **Logs / diagnostics on the user's machine:** `%LOCALAPPDATA%\PeopleFinder\logs\app.log`
  (the app — including the ES start/stop, the verification chain, query bodies
  and hit counts) and `%LOCALAPPDATA%\PeopleFinder\es-logs\` (Elasticsearch itself).
