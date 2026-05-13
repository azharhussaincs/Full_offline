# PeopleFinder — Complete Windows Setup & Deployment Guide

> A beginner-friendly, step-by-step manual for installing, configuring and running the **PeopleFinder** desktop application on a fresh Windows 10/11 PC.
>
> Audience: a developer or technical user who has just received the source code on a new laptop and needs to get it running from zero.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Windows System Requirements](#2-windows-system-requirements)
3. [Installation Guide (step-by-step)](#3-installation-guide-step-by-step)
4. [Elasticsearch Setup on Windows](#4-elasticsearch-setup-on-windows)
5. [Configuration Section](#5-configuration-section)
6. [Windows Commands Cheat Sheet](#6-windows-commands-cheat-sheet)
7. [Environment Variables (`.env`)](#7-environment-variables-env)
8. [Project Structure](#8-project-structure)
9. [How to Run the Project](#9-how-to-run-the-project)
10. [Common Errors & Fixes](#10-common-errors--fixes)
11. [How to Change the Elasticsearch Password](#11-how-to-change-the-elasticsearch-password)
12. [Data & Storage](#12-data--storage)
13. [Building the `.EXE` / Windows Installer](#13-building-the-exe--windows-installer)
14. [Updating the Project Later](#14-updating-the-project-later)
15. [Security Recommendations](#15-security-recommendations)

---

## 1. Project Overview

### What it does

**PeopleFinder** is a **fully-offline desktop application** that lets a user search a directory of people by **name**, **phone number**, or **e-mail address**. The user types a value, presses **Search**, and the app shows clean profile cards (name + phone + email + address) on a polished, minimal UI.

It is a **read-only search client** for a large Elasticsearch index named **`tc_index`** (~302 million documents in production). All search work runs against the local Elasticsearch instance — **no internet is required**.

### Major technologies

| Technology | Purpose |
|---|---|
| **Python 3.10 – 3.12** | Application language |
| **PySide6 (Qt 6)** | Desktop GUI framework |
| **Elasticsearch 8.x / 9.x** | Search backend that holds `tc_index` |
| **`elasticsearch` Python client (v8.13+)** | Talks to Elasticsearch over HTTPS |
| **`python-dotenv`** | Loads configuration from `.env` |
| **PyInstaller + Inno Setup** *(packaging only)* | Builds the one-click Windows installer |

### Architecture (briefly)

```
┌──────────────────┐    ┌───────────────────┐    ┌─────────────────────┐
│  GUI (PySide6)   │ -> │   AppController    │ -> │   Service layer      │
│  Qt widgets,     │    │   (Qt-free)        │    │   (query builder,    │
│  threads         │    │                    │    │    search service,   │
│                  │    │                    │    │    index service)    │
└──────────────────┘    └───────────────────┘    └─────────┬───────────┘
                                                            │
                                                            v
                                                  ┌────────────────────┐
                                                  │ ESClient singleton │
                                                  │ (elasticsearch-py) │
                                                  └─────────┬──────────┘
                                                            │ HTTPS :9200
                                                            v
                                                   ┌─────────────────┐
                                                   │  Elasticsearch  │
                                                   │   (tc_index)    │
                                                   └─────────────────┘
```

* **Strict layering**: GUI → Controllers → Services → Database. Anything below the controller is Qt-free and unit-testable.
* **Single configuration source** in `app/config/settings.py`, loaded once from `.env`.
* **Non-blocking UI** — every Elasticsearch call runs on a background `QThread`.
* **Singleton Elasticsearch client** — one lazy connection for the whole process.

### External dependencies & services

| Dependency | Required? | Notes |
|---|---|---|
| Elasticsearch (running locally) | **Yes** | Must be reachable at `https://localhost:9200` |
| Java (JDK 17+) | Yes, but bundled with Elasticsearch | The Windows `.zip` of Elasticsearch ships its own `jdk\` folder — you do **not** need to install Java separately. |
| Internet | **No** | Once installed, the app is 100% offline. |
| Database files | **Yes** | Elasticsearch's `tc_index` data directory must be present on disk. |

---

## 2. Windows System Requirements

| Item | Minimum | Recommended |
|---|---|---|
| **Operating system** | Windows 10 (64-bit, build 1909+) | Windows 11 (64-bit) |
| **RAM** | 8 GB | 16 GB+ (Elasticsearch is hungry) |
| **Free disk space** | 30 GB (for app + ES + small data) | **80 GB+** (for the full ~22 GB `tc_index` payload + working space) |
| **CPU** | 64-bit, x86-64 (any modern Intel/AMD) | 4 cores+ |
| **Python** | 3.10 | **3.12** |
| **Java (JDK)** | 17+ | Bundled with the Elasticsearch Windows `.zip` (no separate install) |
| **Git** | Latest | Latest |
| **Code editor** | Any | VS Code |
| **Browser** | Any | Chrome / Edge (used to verify ES is up) |

> **Tip:** Elasticsearch needs the user account to have at least ~4 GB of free RAM available; close heavy applications before launching.

---

## 3. Installation Guide (step-by-step)

This whole section assumes a brand-new Windows PC with **nothing installed**. Follow the steps in order.

### Step 3.1 — Install Python 3.12

1. Go to <https://www.python.org/downloads/windows/>.
2. Download the **latest stable Python 3.12 (Windows installer 64-bit)**.
3. Run the installer.
4. **Tick "Add python.exe to PATH"** on the very first screen (this is critical).
5. Click **Install Now**.
6. Verify in **Command Prompt** (press `Win + R`, type `cmd`, hit Enter):

   ```bat
   python --version
   pip --version
   ```

   You should see `Python 3.12.x` and a pip version.

### Step 3.2 — Install Git

1. Download from <https://git-scm.com/download/win>.
2. Run the installer with **default settings** (just keep clicking *Next*).
3. Verify:

   ```bat
   git --version
   ```

### Step 3.3 — Java (skip)

You normally do **not** need to install Java by hand because the Elasticsearch Windows `.zip` already contains its own JDK inside `<elasticsearch>\jdk\`. **Do not** download a separate JDK unless you specifically want to point Elasticsearch at it.

If you must install Java anyway, install **Eclipse Temurin JDK 17 LTS** from <https://adoptium.net/temurin/releases/?version=17>.

### Step 3.4 — Install Elasticsearch (full instructions in §4)

See [§4 Elasticsearch Setup on Windows](#4-elasticsearch-setup-on-windows) below for the full walk-through. The short version is:

1. Download Elasticsearch 8.x **Windows `.zip`** from elastic.co.
2. Extract to `C:\elasticsearch\`.
3. Run `bin\elasticsearch.bat`.

### Step 3.5 — Install VS Code (optional but recommended)

1. Download from <https://code.visualstudio.com/>.
2. Run the installer (default settings are fine; tick "*Add to PATH*" if asked).
3. Recommended extensions: **Python**, **Pylance**, **GitLens**.

### Step 3.6 — Get the project source code

Open **Command Prompt** in the folder where you want to keep the project (e.g. `C:\Projects\`) and clone or copy the source. If you received it as a zip, simply extract it.

```bat
cd C:\Projects
git clone <repository-url> Fully_offline
cd Fully_offline
```

If you already received the folder, just `cd` into it:

```bat
cd C:\Projects\Fully_offline
```

### Step 3.7 — Create a Python virtual environment

A virtual environment ("venv") keeps this project's Python packages isolated from the rest of your system.

```bat
python -m venv venv
```

This creates a `venv\` folder inside the project.

### Step 3.8 — Activate the virtual environment

Every time you open a new Command Prompt to work on the project, **activate** it first:

```bat
venv\Scripts\activate.bat
```

Or in PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
```

> If PowerShell refuses to run the script, run PowerShell **as Administrator** once and execute:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`

Your prompt should now start with `(venv)`. To leave the venv later: `deactivate`.

### Step 3.9 — Install Python dependencies

```bat
python -m pip install --upgrade pip
pip install -r requirements.txt
```

This pulls in:

* `elasticsearch>=8.13,<9` — the official Elasticsearch client
* `PySide6>=6.6,<7` — the Qt 6 GUI bindings
* `python-dotenv>=1.0` — `.env` loader

### Step 3.10 — Create your `.env` file

```bat
copy .env.example .env
```

Open `.env` in Notepad / VS Code and adjust if needed (defaults match Elasticsearch out-of-the-box — see [§5 Configuration](#5-configuration-section) and [§7 Environment Variables](#7-environment-variables-env)).

### Step 3.11 — Run the project

Make sure Elasticsearch is running (see §4) **first**, then:

```bat
python main.py
```

…or simply double-click **`run.bat`** in File Explorer.

The PeopleFinder window should open and the footer should say **● Connected** in green.

---

## 4. Elasticsearch Setup on Windows

### 4.1 Download

1. Go to <https://www.elastic.co/downloads/elasticsearch>.
2. Click the **Windows** tab.
3. Download the `.zip` file (e.g. `elasticsearch-8.14.3-windows-x86_64.zip`).

   > Pick the **same major version** that produced your `tc_index` data. The `packaging/README.md` explains how to check the version: `GET https://localhost:9200/` returns `.version.number`.

### 4.2 Extract

1. Right-click the `.zip` → **Extract All…**
2. Extract to `C:\elasticsearch\` (keep the path short — Windows has a 260-char limit; deep nested paths can break Elasticsearch).
3. The final folder layout should look like:

   ```
   C:\elasticsearch\
   ├── bin\
   │   ├── elasticsearch.bat
   │   ├── elasticsearch-reset-password.bat
   │   └── elasticsearch-users.bat
   ├── config\
   │   ├── elasticsearch.yml
   │   ├── jvm.options
   │   └── ...
   ├── data\
   ├── jdk\           <-- bundled Java; do NOT delete
   ├── lib\
   ├── logs\
   ├── modules\
   └── plugins\
   ```

### 4.3 First-time run (generates passwords & TLS certificates)

Open **Command Prompt** as your normal user (not admin):

```bat
cd C:\elasticsearch
bin\elasticsearch.bat
```

The first launch:

* generates a self-signed TLS certificate,
* prints the **auto-generated password for the `elastic` user** to the console,
* prints an enrollment token for Kibana,
* binds to **`https://localhost:9200`** (HTTP API) and **`9300`** (transport).

**Copy the printed `elastic` password somewhere safe** — you will need it. (Note: this app expects the password `admin123`; we'll change it in §4.7.)

Leave this Command Prompt window open. Closing it stops Elasticsearch.

### 4.4 Verify Elasticsearch is running

Open a **second** Command Prompt:

```bat
curl -k -u elastic:<password> https://localhost:9200
```

(The `-k` flag tells curl to ignore the self-signed certificate.)

You should get JSON containing `cluster_name`, `version.number`, etc. — that means Elasticsearch is up.

You can also paste **<https://localhost:9200>** into a browser. It will warn about an unsafe certificate (because it's self-signed) — click **Advanced → Proceed**. The browser will ask for a username and password; enter `elastic` and the password.

### 4.5 Default ports

| Port | Purpose |
|---|---|
| **9200** | HTTPS REST API (this app uses it) |
| **9300** | Internal node-to-node transport (not used by the app) |

### 4.6 Security (already enabled in 8.x)

Elasticsearch 8.x ships with **security enabled by default** — HTTPS, TLS, password-authenticated `elastic` user — exactly what this app expects. You do **not** need to enable security manually.

If you ever want to *disable* TLS (not recommended), edit `config\elasticsearch.yml` and set:

```yaml
xpack.security.enabled: false
```

…then restart Elasticsearch. **Do not do this on a shared machine.**

### 4.7 Change / set the `elastic` user password to `admin123`

The application's defaults expect the password **`admin123`**. To rotate the random one Elasticsearch generated on first run, use the bundled reset tool:

```bat
cd C:\elasticsearch
bin\elasticsearch-reset-password.bat -u elastic -i
```

The `-i` flag opens an **interactive prompt**: it asks you twice for a new password — type `admin123` both times. Press **Enter**, then `y` to confirm.

For a **non-interactive** reset (auto-generated random password printed to stdout, which you can then use):

```bat
bin\elasticsearch-reset-password.bat -u elastic
```

### 4.8 Reset the password if you've forgotten it

Same command — it works whether or not you remember the old password, as long as Elasticsearch is **running** and you have file-system access:

```bat
cd C:\elasticsearch
bin\elasticsearch-reset-password.bat -u elastic -i
```

If Elasticsearch refuses (e.g. the cluster is down), stop it, then run from inside the `bin\` folder while it boots.

For batch / non-interactive scripting:

```bat
bin\elasticsearch-reset-password.bat -u elastic -a -b
```

`-a` = auto-generate password, `-b` = batch (no prompts).

### 4.9 Update the password inside the project

The app reads the password from the **`.env`** file at the project root. See [§11 How to Change the Elasticsearch Password](#11-how-to-change-the-elasticsearch-password) for the precise file/line.

---

## 5. Configuration Section

All runtime configuration is **centralised**. There is exactly **one** place to edit:

> **File:** `.env` (at the project root — same folder as `main.py`)

The file is read once by `app/config/settings.py` and frozen into an immutable `settings` object. No other file reads `os.environ` directly.

### 5.1 What each variable means

| Variable | Default | Description |
|---|---|---|
| `ES_HOST` | `https://localhost:9200` | Elasticsearch URL. Must include the scheme (`https://`). |
| `ES_USERNAME` | `elastic` | Elasticsearch user. |
| `ES_PASSWORD` | `admin123` | Elasticsearch password. |
| `ES_INDEX` | `tc_index` | The index the app searches. |
| `ES_VERIFY_CERTS` | `false` | Set to `true` only if you have a valid CA. Self-signed certs → leave `false`. |
| `ES_TIMEOUT` | `30` | Request timeout in seconds. |
| `APP_NAME` | `PeopleFinder` | Shown in the window title. |
| `APP_PAGE_SIZE` | `20` | Results per page. |
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `LOG_DIR` | `logs` | Where rotating log files are written. |
| `HISTORY_FILE` | `search_history.json` | Quiet on-disk search history. |
| `HISTORY_MAX` | `50` | Max entries kept in the history file. |
| `EXPORT_DIR` | `exports` | Where exported results are written (currently unused by the UI). |

### 5.2 Which lines you usually need to change on a new laptop

Open **`.env`** and review these four lines first:

```env
ES_HOST=https://localhost:9200
ES_USERNAME=elastic
ES_PASSWORD=admin123
ES_INDEX=tc_index
```

* If your local Elasticsearch listens somewhere else (different port, different host) → change `ES_HOST`.
* If you used a different password during reset → change `ES_PASSWORD`.
* If your index has a different name → change `ES_INDEX`.

### 5.3 Where these values are consumed in code

* `app/config/settings.py` — lines **105–119** load every variable above into the immutable `Settings` dataclass. **Read-only file; you don't need to edit it.**
* `app/database/es_client.py` — the only module that actually talks to Elasticsearch. It reads `settings.es_host`, `settings.es_username`, `settings.es_password`, etc. **Don't edit this** — edit `.env` instead.

> **Rule of thumb:** *credentials and hosts never live in source code; they live in `.env`.*

### 5.4 If paths differ on your machine

* The app uses **paths relative to the project root** (so `logs/`, `exports/`, `search_history.json` always land next to `main.py`).
* If you want them somewhere else, set the variable to an **absolute** Windows path in `.env`. Example:

  ```env
  LOG_DIR=D:\PeopleFinderLogs
  EXPORT_DIR=D:\PeopleFinderExports
  HISTORY_FILE=D:\PeopleFinderLogs\search_history.json
  ```

* Backslashes inside `.env` do **not** need escaping in this format.

### 5.5 API keys / model paths

This project **does not** use any API keys or ML model files. The only secret is the Elasticsearch password.

---

## 6. Windows Commands Cheat Sheet

Everything below assumes you have already `cd`-ed into the project directory.

### 6.1 Command Prompt (`cmd.exe`)

```bat
:: open a Command Prompt at the project folder (right-click in File Explorer
:: → "Open in Terminal" → switch to Command Prompt)
cd C:\Projects\Fully_offline

:: create venv
python -m venv venv

:: activate venv
venv\Scripts\activate.bat

:: install deps
pip install -r requirements.txt

:: copy template
copy .env.example .env

:: run the app
python main.py

:: leave venv
deactivate
```

### 6.2 PowerShell

```powershell
cd C:\Projects\Fully_offline

python -m venv venv
.\venv\Scripts\Activate.ps1

pip install -r requirements.txt

Copy-Item .env.example .env

python main.py
```

### 6.3 Common Windows shortcuts

| Action | Command |
|---|---|
| Open Command Prompt | `Win + R` → `cmd` → Enter |
| Open PowerShell | `Win + R` → `powershell` → Enter |
| Kill a hung process | `Ctrl + C` in its terminal, or *Task Manager → End Task* |
| Show what's listening on port 9200 | `netstat -ano \| findstr 9200` |
| Kill PID 1234 | `taskkill /PID 1234 /F` |
| Check Python | `where python` |
| Check Java | `where java` |

> **Avoid** `bash`, `ls`, `cp`, `rm`, `source` — those are Linux commands and may not work in plain `cmd.exe`. Use `dir`, `copy`, `del`, `cd`, `call`, `.\venv\Scripts\activate.bat` instead.

---

## 7. Environment Variables (`.env`)

### 7.1 How to create the `.env` file

The repository ships a template named `.env.example`. **Copy** it to `.env`:

```bat
copy .env.example .env
```

Then open `.env` in Notepad or VS Code and edit.

### 7.2 Full example `.env`

```env
# --- Elasticsearch connection ----------------------------------------------
ES_HOST=https://localhost:9200
ES_USERNAME=elastic
ES_PASSWORD=admin123
ES_INDEX=tc_index
ES_VERIFY_CERTS=false
ES_TIMEOUT=30

# --- Application settings ---------------------------------------------------
APP_NAME=PeopleFinder
APP_PAGE_SIZE=20

# --- Logging ---------------------------------------------------------------
LOG_LEVEL=INFO
LOG_DIR=logs

# --- Search history & exports ----------------------------------------------
HISTORY_FILE=search_history.json
HISTORY_MAX=50
EXPORT_DIR=exports
```

### 7.3 How the variables are loaded

The loader lives in `app/config/settings.py`:

```python
load_dotenv(BASE_DIR / ".env", override=False)
```

Priority order (highest first):

1. Shell environment variables (anything already exported in the current `cmd.exe` / PowerShell session).
2. The `.env` file at the project root.
3. The hard-coded defaults inside `settings.py`.

That means a temporary override from the shell is easy:

```bat
set ES_PASSWORD=Different!Pass
python main.py
```

### 7.4 Security best practices

* **`.env` is listed in `.gitignore`** — never commit it.
* Do **not** paste real production passwords into Slack, GitHub issues, or screenshots.
* On Windows, restrict the `.env` file's permissions to your user account: right-click → **Properties → Security** → remove "Users" and "Everyone".
* Use a strong, unique Elasticsearch password in production; `admin123` is for **local development only**.
* If `ES_VERIFY_CERTS=false`, TLS warnings are silenced — that's fine for self-signed local certs but **never** appropriate over the internet.

---

## 8. Project Structure

```
Fully_offline/
├── main.py                       # Entry point  ->  python main.py
├── run.bat                       # Windows launcher (activates venv, runs main.py)
├── run.sh                        # Linux/macOS launcher (not used on Windows)
├── requirements.txt              # Runtime dependencies
├── requirements-build.txt        # Extra deps for building the .exe installer
├── .env.example                  # Template — copy to .env
├── .env                          # Real config (gitignored)
├── .gitignore
├── README.md                     # Original (Linux-focused) README
├── WINDOWS_SETUP_GUIDE.md        # <-- THIS FILE
│
├── app/                          # All application source code
│   ├── __init__.py
│   ├── config/
│   │   ├── settings.py           # Immutable Settings dataclass loaded from .env
│   │   └── logging_config.py     # Rotating file logs + console
│   ├── database/
│   │   └── es_client.py          # ESClient singleton — only file that imports `elasticsearch`
│   ├── models/
│   │   ├── search_models.py      # SearchType, SearchQuery, Document, SearchResult
│   │   └── profile.py            # Profile / ProfileField / ProfilePage (UI view-models)
│   ├── services/
│   │   ├── index_service.py      # exists / count / mapping helpers
│   │   ├── query_builder.py      # Builds robust Query-DSL
│   │   ├── search_service.py     # Executes searches, maps hits to domain objects
│   │   └── embedded_es.py        # Starts/stops bundled ES (used only by installer build)
│   ├── controllers/
│   │   └── app_controller.py     # AppController.find(text) -> ProfilePage  (Qt-free)
│   ├── utils/
│   │   ├── detector.py           # Auto-detect name / phone / e-mail
│   │   ├── validators.py
│   │   ├── profile_mapper.py     # Raw _source -> clean Profile
│   │   ├── profile_export.py
│   │   ├── export.py
│   │   └── history.py
│   └── gui/
│       ├── app.py                # create_application() / run()
│       ├── theme.py              # Qt Style Sheet
│       ├── icons.py
│       ├── workers.py            # QThread worker
│       ├── main_window.py        # MainWindow
│       └── widgets/
│           ├── search_header.py
│           ├── results_view.py
│           ├── result_card.py
│           ├── avatar.py
│           ├── spinner.py
│           ├── states.py
│           └── status_footer.py
│
├── tools/
│   ├── seed_data.py              # OPTIONAL: insert sample people for testing
│   └── prepare_es_payload.py     # Build runtime/es-data/ from a live tc_index
│
├── packaging/                    # Windows installer recipe
│   ├── build_windows.bat
│   ├── PeopleFinder.spec
│   ├── installer.iss
│   ├── configure_bundled_es.py
│   ├── make_icon.py
│   ├── README.md
│   └── WINDOWS_PRODUCTION_BUILD_PROMPT.md
│
├── runtime/                      # Created during the installer build
│   ├── elasticsearch/            # Bundled ES distribution (build-time only)
│   └── es-data/                  # Bundled tc_index data (build-time only)
│
├── logs/                         # Rotating log files (created at runtime)
├── exports/                      # Result exports (created at runtime)
└── venv/                         # Your local virtual environment (gitignored)
```

### File-by-file purpose (short version)

| File | What it does |
|---|---|
| `main.py` | Bootstraps logging and launches the GUI. The only file you run directly. |
| `app/config/settings.py` | Reads `.env` once into an immutable settings object. |
| `app/database/es_client.py` | Lazy singleton wrapper around the `elasticsearch` client. |
| `app/services/query_builder.py` | Builds a defensive Elasticsearch query that works on any mapping. |
| `app/services/search_service.py` | Runs searches, retries with a safe fallback, maps results. |
| `app/controllers/app_controller.py` | The façade the GUI calls. `find(text) → ProfilePage`. Qt-free. |
| `app/utils/profile_mapper.py` | Cleans Elasticsearch `_source` into `Profile` view-models. |
| `app/gui/main_window.py` | The PySide6 window: header + results + footer. |
| `app/services/embedded_es.py` | Used **only** when running from the packaged `.exe` — no-op in source mode. |
| `tools/seed_data.py` | Optional: inserts ~8 sample people for testing. |
| `packaging/build_windows.bat` | One-click installer build (venv → PyInstaller → Inno Setup). |

---

## 9. How to Run the Project

### 9.1 First-time startup (from scratch)

1. Make sure Python, Git, and Elasticsearch are installed (§3, §4).
2. Open **Command Prompt** at the project folder:

   ```bat
   cd C:\Projects\Fully_offline
   ```

3. Create and activate the venv:

   ```bat
   python -m venv venv
   venv\Scripts\activate.bat
   ```

4. Install dependencies:

   ```bat
   pip install -r requirements.txt
   ```

5. Copy the env template and edit if needed:

   ```bat
   copy .env.example .env
   notepad .env
   ```

6. Start Elasticsearch in a **separate** Command Prompt window (keep it open):

   ```bat
   cd C:\elasticsearch
   bin\elasticsearch.bat
   ```

   Wait until you see lines like `started` and `Cluster health status changed from [RED] to [GREEN]`.

7. (Optional) Seed sample people if your index is empty:

   ```bat
   python tools\seed_data.py
   ```

8. Run the app:

   ```bat
   python main.py
   ```

### 9.2 Normal startup (every day after that)

```bat
:: Terminal 1 — start Elasticsearch
cd C:\elasticsearch
bin\elasticsearch.bat

:: Terminal 2 — start the app
cd C:\Projects\Fully_offline
run.bat
```

`run.bat` automatically activates the venv if one exists, then runs `python main.py`.

### 9.3 What runs where

| Component | Where | Started by |
|---|---|---|
| Elasticsearch | `C:\elasticsearch\` | `bin\elasticsearch.bat` (manually) |
| PeopleFinder GUI | Project folder | `python main.py` or `run.bat` |
| Backend / REST API | *(none)* — the desktop app talks to Elasticsearch directly |

There is **no separate backend** to start. The GUI is the front-end and is also the back-end client.

### 9.4 Order of operations

1. **Always start Elasticsearch first.** It can take 30 – 60 seconds to become responsive.
2. Wait until `https://localhost:9200` answers (you can test with `curl -k -u elastic:admin123 https://localhost:9200`).
3. **Then** start the PeopleFinder GUI. The footer should say **● Connected**.

### 9.5 Closing things

* **Close the GUI** by clicking the window's X button.
* **Stop Elasticsearch** by pressing `Ctrl + C` in its Command Prompt window.

---

## 10. Common Errors & Fixes

| # | Symptom | Cause | Fix |
|---|---|---|---|
| 1 | **`'python' is not recognized as an internal or external command`** | Python is not on PATH. | Re-run the Python installer and tick **"Add python.exe to PATH"**, or add `C:\Users\<you>\AppData\Local\Programs\Python\Python312\` to your PATH manually. |
| 2 | **`ModuleNotFoundError: No module named 'PySide6'`** (or `elasticsearch`, `dotenv`) | The venv isn't active, or `pip install` wasn't run. | `venv\Scripts\activate.bat` then `pip install -r requirements.txt`. |
| 3 | Footer shows **● Not connected** | Elasticsearch isn't running, wrong host/port, wrong credentials, or TLS mismatch. | Check that `bin\elasticsearch.bat` is running. Open `https://localhost:9200` in a browser. Verify `.env` values. Check `logs\app.log`. |
| 4 | **Connection refused / `ConnectionError`** | Elasticsearch hasn't finished booting yet, or port 9200 is blocked. | Wait 30–60s after starting ES. Check `netstat -ano \| findstr 9200`. Check Windows Defender Firewall (§10.10). |
| 5 | **`SSL: CERTIFICATE_VERIFY_FAILED`** | `ES_VERIFY_CERTS=true` but the cert is self-signed. | Set `ES_VERIFY_CERTS=false` in `.env`. |
| 6 | **`AuthenticationException: 401`** | Wrong username or password. | Reset password: `bin\elasticsearch-reset-password.bat -u elastic -i`. Then update `ES_PASSWORD` in `.env`. |
| 7 | Popup: **"The directory could not be found …"** | `ES_INDEX` doesn't exist on the cluster. | Run `python tools\seed_data.py`, or point `ES_INDEX` at a real index. Check with: `curl -k -u elastic:admin123 https://localhost:9200/_cat/indices?v`. |
| 8 | **Port 9200 already in use** | Another Elasticsearch / Docker container / process is bound to 9200. | `netstat -ano \| findstr 9200` to find the PID, then `taskkill /PID <pid> /F`. Or change ES's `http.port` in `config\elasticsearch.yml`. |
| 9 | **`Java not found`** when starting ES | The bundled `jdk\` folder was deleted, or `JAVA_HOME` points elsewhere. | Re-extract Elasticsearch fresh. Or `set JAVA_HOME=` (empty) before running `bin\elasticsearch.bat`. |
| 10 | **Windows Defender / SmartScreen blocks the `.exe`** | Unsigned executable. | Click "More info" → "Run anyway". For a permanent fix, code-sign the binary. |
| 11 | **GUI window doesn't appear** | Qt platform plugin issue, or you're on a headless / RDP session. | Make sure you're on a real desktop session. Try `pip install --force-reinstall PySide6`. |
| 12 | **`PowerShell cannot run scripts`** when activating venv | Restrictive execution policy. | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` (PowerShell, as Administrator once). |
| 13 | **`pip install` fails with SSL errors** | Corporate proxy or expired cert store. | `pip install --upgrade certifi` and/or set `HTTPS_PROXY` env var. |
| 14 | **ES exits immediately with `bootstrap check failed`** | Linux-style limits / `vm.max_map_count`. | On Windows this rarely happens. If it does, check `config\elasticsearch.yml` — set `discovery.type: single-node`. |
| 15 | **CORS error in browser** (only relevant if you build a web front-end) | Browser blocks cross-origin XHR. | Add CORS settings in `elasticsearch.yml`: `http.cors.enabled: true` and `http.cors.allow-origin: "*"`. |

### 10.10 Windows Defender / Firewall

Windows Defender Firewall sometimes blocks Java (Elasticsearch is a Java process) the first time it binds to a port. If you see a "Windows Defender Firewall" pop-up, tick **Private networks** and click **Allow access**.

To manually allow it later:

```
Control Panel → Windows Defender Firewall → Allow an app through firewall
→ Change settings → Allow another app → Browse → C:\elasticsearch\jdk\bin\java.exe
```

---

## 11. How to Change the Elasticsearch Password

This is one of the most common configuration changes — read it carefully.

### 11.1 Reset the password inside Elasticsearch

```bat
cd C:\elasticsearch
bin\elasticsearch-reset-password.bat -u elastic -i
```

* `-u elastic` — target the built-in `elastic` superuser.
* `-i` — interactive (prompts you to type the new password twice).

Type your new password, confirm with `y`. Elasticsearch must be **running** for this to work.

**Alternative — non-interactive (auto-generate):**

```bat
bin\elasticsearch-reset-password.bat -u elastic -a -b
```

This prints a random password to stdout — copy it.

### 11.2 Update the password inside the project

The password lives **only** in the `.env` file. Open it:

```bat
notepad .env
```

Find this line:

```env
ES_PASSWORD=admin123
```

…and change it to your new value, e.g.:

```env
ES_PASSWORD=MyNewStrongPass!2026
```

Save and close. Restart the app:

```bat
python main.py
```

### 11.3 Where exactly is the password used in code?

You **do not need to change any source file** — the loading is centralised. For reference:

| File | Line(s) | What happens there |
|---|---|---|
| `.env` | line `ES_PASSWORD=…` | The value lives here. |
| `app/config/settings.py` | line 107 (`es_password=os.getenv("ES_PASSWORD", "admin123")`) | Reads it from the environment. |
| `app/database/es_client.py` | wherever `settings.es_password` is referenced | Passes it to the `elasticsearch` client. |

**Old vs. new — example diff in `.env`:**

```diff
- ES_PASSWORD=admin123
+ ES_PASSWORD=MyNewStrongPass!2026
```

That single line edit is the entire change. **Never** hard-code the password in any `.py` file.

### 11.4 Change the username too (optional)

If you also rotated the user (rare):

```env
ES_USERNAME=peoplefinder_app
ES_PASSWORD=Secret!2026
```

You can create a new application-specific user in Elasticsearch via the Users API or `bin\elasticsearch-users.bat`.

---

## 12. Data & Storage

### 12.1 Where Elasticsearch data lives

| Location | What it holds |
|---|---|
| `C:\elasticsearch\data\` | The Lucene shards for every index — including `tc_index`. **Do not delete.** |
| `C:\elasticsearch\config\` | `elasticsearch.yml`, TLS certs, keystore. **Do not delete.** |
| `C:\elasticsearch\logs\` | Server logs. Safe to clear when ES is stopped. |
| `<project>\logs\app.log` | App logs (rotating, 5 × 2 MB). Safe to clear. |
| `<project>\exports\` | Result exports (currently unused by the UI). |
| `<project>\search_history.json` | Quiet on-disk history of past searches. |

For the packaged Windows installer build, data is stored under:
* `%LOCALAPPDATA%\PeopleFinder\es-data\` — the `tc_index` Lucene shards (~22 GB).
* `%LOCALAPPDATA%\PeopleFinder\logs\` — app logs.
* `%LOCALAPPDATA%\PeopleFinder\es-logs\` — ES logs.

### 12.2 Back up the data

**Stop Elasticsearch first** (`Ctrl + C` in its terminal), then zip the data folder:

```bat
cd C:\
tar -a -cf elasticsearch-backup-2026-05-13.zip elasticsearch\data
```

(`tar` ships with Windows 10/11.)

For a **live** (running) backup, use the official Elasticsearch [snapshot/restore API](https://www.elastic.co/guide/en/elasticsearch/reference/current/snapshot-restore.html) — see `tools\prepare_es_payload.py` for an example.

### 12.3 Move the project to another Windows PC

1. On the **old** PC: stop Elasticsearch, stop the app.
2. Copy these to the **new** PC:
   * The whole project folder `Fully_offline\` (**excluding** `venv\` and `__pycache__\`).
   * The `C:\elasticsearch\` folder **including its `data\` subfolder** (this is where `tc_index` actually lives).
3. On the new PC:
   * Install Python (§3.1).
   * Recreate the venv: `python -m venv venv`, `pip install -r requirements.txt`.
   * Run `bin\elasticsearch.bat`.
   * Run `python main.py`.
4. **Do not** copy `venv\` or `node_modules` — they are platform-specific and large.

### 12.4 Folders you should NEVER delete

* `C:\elasticsearch\data\`
* `C:\elasticsearch\config\` (especially `certs\` and `elasticsearch.keystore`)
* `C:\elasticsearch\jdk\`
* `<project>\app\`
* `<project>\.env`

Folders that **are** safe to delete (will be recreated):

* `<project>\venv\`
* `<project>\__pycache__\` (any level)
* `<project>\logs\`
* `<project>\exports\`
* `C:\elasticsearch\logs\` (only while ES is stopped)

---

## 13. Building the `.EXE` / Windows Installer

The project ships a packaging recipe that turns it into **one** Windows installer (`PeopleFinder-Setup.exe`) which bundles:

* A private Python runtime + PySide6
* The application code (unchanged)
* A private Elasticsearch distribution (including its own JDK)
* The `tc_index` data directory

End users then install nothing else — no Python, no Java, no ES.

**The complete, authoritative guide is in [`packaging/README.md`](packaging/README.md).** This section is just a quick orientation.

### 13.1 Prerequisites on the **build** machine

| Tool | Where |
|---|---|
| Windows 64-bit, Python 3.10–3.12 on PATH | §3.1 |
| Inno Setup 6.3+ | <https://jrsoftware.org/isdl.php> (provides `ISCC.exe`) |
| Elasticsearch Windows `.zip` matching your source version | Extract to `runtime\elasticsearch\` |
| Access to the live `tc_index` (filesystem copy or snapshot) | Built into `runtime\es-data\` by `tools\prepare_es_payload.py` |
| ~3× the data size of free disk during the build | Lots of scratch space |

### 13.2 One-shot build

```bat
:: Place runtime\elasticsearch\ and runtime\es-data\ first (see packaging\README.md),
:: then:
packaging\build_windows.bat
```

It does: create build venv → install deps → verify bundled ES → generate icon → run **PyInstaller** → run **Inno Setup**.

On success it prints:

```
packaging\Output\PeopleFinder-Setup.exe
```

### 13.3 Manual equivalent

```bat
python -m venv .build-venv
.build-venv\Scripts\python -m pip install -r requirements.txt pyinstaller
.build-venv\Scripts\python packaging\make_icon.py
.build-venv\Scripts\python -m PyInstaller packaging\PeopleFinder.spec --noconfirm ^
    --distpath packaging\dist --workpath packaging\build
"C:\Program Files (x86)\Inno Setup 6\ISCC.exe" packaging\installer.iss
```

### 13.4 Large-file considerations

* The `tc_index` payload is roughly **22 GB**. The installer will be ~10–18 GB depending on Lucene compressibility.
* Use **`Compression=lzma2/fast`** in `installer.iss` while iterating; switch to `lzma2/max + SolidCompression=yes` for the final release build (much slower, ~30–60 min on a fast machine).
* To split the installer across DVDs/USB sticks, enable `DiskSpanning` / `DiskSliceSize` in `installer.iss`.
* Code-sign both `PeopleFinder.exe` and the final `PeopleFinder-Setup.exe` with `signtool.exe` and a code-signing certificate — otherwise Windows SmartScreen will warn users.

---

## 14. Updating the Project Later

When new code arrives (e.g. a Git pull or a fresh `.zip` from the maintainer):

```bat
:: 1. Stop the running app and (if running) Elasticsearch.

:: 2. Pull / replace source
cd C:\Projects\Fully_offline
git pull
:: or: extract the new zip on top of the folder

:: 3. Re-activate venv and update dependencies (in case requirements.txt changed)
venv\Scripts\activate.bat
pip install -r requirements.txt --upgrade

:: 4. Re-check .env in case new variables were added
fc /n .env .env.example

:: 5. Run
python main.py
```

If `.env.example` gained new variables, copy them across into your `.env` and adjust values.

To upgrade Elasticsearch (rare) — download the new Windows `.zip`, extract it next to the old one, copy `data\` and `config\` across, and adjust your `bin\elasticsearch.bat` shortcut. Always read the Elasticsearch upgrade notes for breaking changes.

---

## 15. Security Recommendations

* **Never commit `.env`.** It's already in `.gitignore` — keep it that way.
* **Rotate the `elastic` password** away from the default `admin123` before deploying outside a dev machine (see §11).
* **Restrict Elasticsearch to localhost.** The bundled `elasticsearch.yml` already sets `network.host: _local_` — keep it that way unless you really need network access.
* **Keep `ES_VERIFY_CERTS=false`** *only* with self-signed local certs. For any real deployment, install a proper CA-issued certificate and set it to `true`.
* **Run Elasticsearch as a non-admin Windows user.** It does not need elevated privileges.
* **Limit file-system permissions** on `.env`, `C:\elasticsearch\config\elasticsearch.keystore`, and `C:\elasticsearch\config\certs\` to your user account.
* **Code-sign** the installer before distributing (§13.4).
* **Patch regularly** — `pip install -r requirements.txt --upgrade` and watch the [Elasticsearch security advisories](https://www.elastic.co/community/security).
* **Back up `tc_index`** before any upgrade, password reset, or major change (§12.2).

---

## Quick reference card

```bat
:: Daily commands ------------------------------------------------------------

:: 1. start Elasticsearch (in its own terminal)
cd C:\elasticsearch && bin\elasticsearch.bat

:: 2. start the app
cd C:\Projects\Fully_offline && run.bat

:: Update the password ------------------------------------------------------
bin\elasticsearch-reset-password.bat -u elastic -i
notepad C:\Projects\Fully_offline\.env       :: edit ES_PASSWORD

:: Reinstall dependencies ---------------------------------------------------
cd C:\Projects\Fully_offline
venv\Scripts\activate.bat
pip install -r requirements.txt --upgrade

:: Build the installer ------------------------------------------------------
packaging\build_windows.bat
```

---

**Maintainer:** Azhar Hussain
**Last updated:** 2026-05-13
**App version:** 1.0.0
