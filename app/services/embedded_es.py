"""Managed *embedded* Elasticsearch — the deploy-layer glue for the Windows build.

This is the **only** new application module added for packaging.  It does **not**
touch the search/query/UI code.  All it does is:

* find a private Elasticsearch distribution bundled next to the frozen ``.exe``
  (``<app dir>\\elasticsearch\\``), with the ~22 GB ``tc_index`` data directory
  installed under ``%LOCALAPPDATA%\\PeopleFinder\\es-data``;
* start that Elasticsearch as a **hidden background child process**, configured
  so the application's existing connection settings (``https://localhost:9200``,
  user ``elastic`` / pass ``admin123``, ``verify_certs=False``) work verbatim —
  no application config change;
* wait until it answers (so the rest of the app, which already pings the cluster
  and checks ``GET /tc_index/_count`` on start-up, "just works");
* shut it down cleanly when the app exits (and best-effort on crash via
  ``atexit``).

When **no** bundled Elasticsearch is present — i.e. running from a normal source
checkout — every function here is a **no-op**, so development behaviour (connect
to whatever Elasticsearch the developer is running) is completely unchanged.

The bundled Elasticsearch's *configuration* (single-node, HTTPS, the ``elastic``
password, etc.) is prepared at build time — see ``packaging/README.md`` and
``packaging/configure_bundled_es.py``.  This module only handles the lifecycle.
"""
from __future__ import annotations

import atexit
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Callable, Optional

from app.config.logging_config import get_logger
from app.config.settings import settings

logger = get_logger("embedded_es")

# The HTTP port the application's settings expect ("https://localhost:9200").
_HTTP_PORT = 9200

# How long to wait for the embedded node to become reachable on a cold start
# (opening a multi-GB index on first run can take a while).
_READY_TIMEOUT_S = float(os.getenv("PEOPLEFINDER_ES_READY_TIMEOUT", "300"))

# Module-level state (the app is single-instance; one node per process).
_lock = threading.RLock()
_proc: Optional[subprocess.Popen] = None
_started_by_us = False
_atexit_registered = False

StatusCb = Callable[[str], None]


# --------------------------------------------------------------------------- #
# Path resolution
# --------------------------------------------------------------------------- #
def _is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def _app_dir() -> Path:
    """Directory containing the running executable (frozen) or the project root."""
    if _is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _candidate_es_homes() -> list[Path]:
    base = _app_dir()
    meipass = getattr(sys, "_MEIPASS", None)
    homes = [base / "elasticsearch", base / "runtime" / "elasticsearch"]
    if meipass:
        homes.append(Path(meipass) / "elasticsearch")
    env_home = os.getenv("PEOPLEFINDER_ES_HOME", "").strip()
    if env_home:
        homes.insert(0, Path(env_home))
    return homes


def find_bundled_es_home() -> Optional[Path]:
    """Return the path of the bundled Elasticsearch home, or ``None`` if absent.

    A directory is accepted only if it actually looks like an ES distribution
    (has ``bin/elasticsearch.bat`` or ``bin/elasticsearch``).
    """
    for home in _candidate_es_homes():
        try:
            if (home / "bin" / "elasticsearch.bat").is_file() or (home / "bin" / "elasticsearch").is_file():
                return home
        except OSError:
            continue
    return None


def _writable_dir() -> Path:
    """A directory the embedded node may write to (data / logs / tmp / config copy)."""
    env_dir = os.getenv("PEOPLEFINDER_ES_DATA_HOME", "").strip()
    if env_dir:
        return Path(env_dir).expanduser()
    local = os.getenv("LOCALAPPDATA") or os.getenv("APPDATA")
    if local:
        return Path(local) / "PeopleFinder"
    if os.name == "nt":
        return Path.home() / "AppData" / "Local" / "PeopleFinder"
    return Path.home() / ".peoplefinder"


def es_data_dir() -> Path:
    """Where the ~22 GB ``tc_index`` data directory lives (``path.data``)."""
    return _writable_dir() / "es-data"


def es_logs_dir() -> Path:
    return _writable_dir() / "es-logs"


def _es_tmp_dir() -> Path:
    return _writable_dir() / "es-tmp"


def _es_conf_dir(es_home: Path) -> Path:
    """A *writable* config dir for the node, seeded once from the bundled config.

    Elasticsearch normally only reads its config dir, but to be safe on a
    read-only ``Program Files`` install we keep the working config under
    ``%LOCALAPPDATA%`` and copy the bundled config into it on first run.
    """
    conf = _writable_dir() / "es-config"
    try:
        bundled = es_home / "config"
        if not conf.is_dir() and bundled.is_dir():
            shutil.copytree(bundled, conf)
            logger.info("Seeded embedded-ES config dir: %s", conf)
        elif bundled.is_dir():
            # Refresh files that the bundle owns but keep anything ES generated
            # at runtime (e.g. nothing, normally) — a shallow refresh is enough.
            for name in ("elasticsearch.yml", "jvm.options", "log4j2.properties"):
                src = bundled / name
                if src.is_file():
                    shutil.copy2(src, conf / name)
            certs = bundled / "certs"
            if certs.is_dir() and not (conf / "certs").exists():
                shutil.copytree(certs, conf / "certs")
            ks = bundled / "elasticsearch.keystore"
            if ks.is_file() and not (conf / "elasticsearch.keystore").exists():
                shutil.copy2(ks, conf / "elasticsearch.keystore")
    except OSError as exc:
        logger.warning("Could not prepare a writable ES config dir (%s); using the bundled one", exc)
        return es_home / "config"
    return conf


def _heap_opts() -> str:
    """Return ``-Xms.. -Xmx..`` sized to the machine (1 GB .. 4 GB; ~1/4 of RAM)."""
    gb = 1
    try:
        import ctypes

        if os.name == "nt":
            class _MEMSTAT(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
            st = _MEMSTAT()
            st.dwLength = ctypes.sizeof(_MEMSTAT)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(st)):
                total_gb = st.ullTotalPhys / (1024 ** 3)
                gb = max(1, min(4, int(total_gb // 4)))
        else:  # best effort on non-Windows (dev machines)
            pages = os.sysconf("SC_PHYS_PAGES")
            page = os.sysconf("SC_PAGE_SIZE")
            total_gb = (pages * page) / (1024 ** 3)
            gb = max(1, min(4, int(total_gb // 4)))
    except Exception:  # noqa: BLE001
        gb = 1
    return f"-Xms{gb}g -Xmx{gb}g"


# --------------------------------------------------------------------------- #
# Reachability
# --------------------------------------------------------------------------- #
def is_reachable(timeout: float = 2.0) -> bool:
    """Return ``True`` if Elasticsearch answers on ``https://localhost:9200``.

    Uses the application's own configured client so the check matches exactly
    how the rest of the app talks to ES.
    """
    try:
        from app.database.es_client import ESClient

        return bool(ESClient.instance().client.options(request_timeout=timeout).ping())
    except Exception:  # noqa: BLE001
        return False


# --------------------------------------------------------------------------- #
# Lifecycle
# --------------------------------------------------------------------------- #
def _spawn(es_home: Path) -> subprocess.Popen:
    data_dir = es_data_dir()
    logs_dir = es_logs_dir()
    tmp_dir = _es_tmp_dir()
    for d in (data_dir, logs_dir, tmp_dir):
        d.mkdir(parents=True, exist_ok=True)
    conf_dir = _es_conf_dir(es_home)

    env = dict(os.environ)
    env["ES_PATH_CONF"] = str(conf_dir)
    env["ES_TMPDIR"] = str(tmp_dir)
    # Use the JDK that ships inside the Elasticsearch distribution (no system Java).
    bundled_jdk = es_home / "jdk"
    if bundled_jdk.is_dir():
        env["ES_JAVA_HOME"] = str(bundled_jdk)
        env.pop("JAVA_HOME", None)
    env["ES_JAVA_OPTS"] = (env.get("ES_JAVA_OPTS", "") + " " + _heap_opts()).strip()

    # Settings overridden on the command line so the writable paths win regardless
    # of what's in the bundled elasticsearch.yml.
    overrides = [
        f"-Epath.data={data_dir}",
        f"-Epath.logs={logs_dir}",
        f"-Enetwork.host=_local_",
        f"-Ehttp.port={_HTTP_PORT}",
        f"-Ediscovery.type=single-node",
        f"-Eingest.geoip.downloader.enabled=false",
        f"-Expack.security.enrollment.enabled=false",
    ]

    if os.name == "nt":
        es_bin = es_home / "bin" / "elasticsearch.bat"
        cmd = ["cmd.exe", "/c", str(es_bin), *overrides]
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:  # pragma: no cover - only used if someone runs a Linux build
        es_bin = es_home / "bin" / "elasticsearch"
        cmd = [str(es_bin), *overrides]
        creationflags = 0

    log_path = logs_dir / "embedded-es-stdout.log"
    logger.info("Launching embedded Elasticsearch: home=%s data=%s heap=%s", es_home, data_dir, _heap_opts())
    logger.debug("Embedded ES command: %s", cmd)
    out = open(log_path, "ab", buffering=0)  # noqa: SIM115 - lives for the ES process lifetime
    proc = subprocess.Popen(
        cmd, cwd=str(es_home), env=env, stdout=out, stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL, creationflags=creationflags,
    )
    return proc


def _wait_until_ready(proc: subprocess.Popen, timeout: float, status: Optional[StatusCb]) -> bool:
    deadline = time.monotonic() + timeout
    last_log = 0.0
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            logger.error("Embedded Elasticsearch process exited early with code %s "
                         "(see es-logs/embedded-es-stdout.log)", proc.returncode)
            return False
        if is_reachable(timeout=2.0):
            logger.info("Embedded Elasticsearch is reachable on https://localhost:%d", _HTTP_PORT)
            return True
        now = time.monotonic()
        if now - last_log >= 5.0:
            remaining = int(deadline - now)
            msg = f"Starting search engine… ({remaining}s)"
            logger.info("Waiting for embedded Elasticsearch to come up (%ds left)…", remaining)
            if status:
                try:
                    status(msg)
                except Exception:  # noqa: BLE001
                    pass
            last_log = now
        time.sleep(1.0)
    logger.error("Timed out waiting for embedded Elasticsearch (%.0fs).", timeout)
    return False


def ensure_started(*, wait: bool = True, timeout: float = _READY_TIMEOUT_S,
                   status: Optional[StatusCb] = None) -> bool:
    """Make sure the embedded Elasticsearch is running.  Safe to call repeatedly.

    Behaviour:

    * If no bundled Elasticsearch is found (normal source checkout) → **no-op**,
      returns ``True`` (the app will connect to whatever ES the developer runs).
    * If Elasticsearch already answers on ``https://localhost:9200`` → returns
      ``True`` immediately (don't start a second one — that would corrupt the
      data directory).
    * Otherwise → spawn the bundled node and (when *wait*) block until it
      answers, or *timeout* elapses.

    Args:
        wait: block until the node is reachable (or timeout) before returning.
        timeout: seconds to wait for readiness.
        status: optional ``callable(str)`` to receive progress messages
            ("Starting search engine… (N s)").

    Returns:
        ``True`` if Elasticsearch is reachable (or there is nothing to start);
        ``False`` if the bundled node failed to come up in time.
    """
    global _proc, _started_by_us, _atexit_registered
    with _lock:
        es_home = find_bundled_es_home()
        if es_home is None:
            logger.info("No bundled Elasticsearch found — using the externally configured cluster as-is.")
            return True

        if _proc is not None and _proc.poll() is None and is_reachable():
            return True

        if is_reachable():
            # Something is already serving 9200 (a previously started instance,
            # or — in dev — the developer's own node). Reuse it; don't start ours.
            logger.info("Elasticsearch already reachable on :%d — reusing it; not starting the bundled node.", _HTTP_PORT)
            return True

        if not _atexit_registered:
            atexit.register(stop)
            _atexit_registered = True

        try:
            _proc = _spawn(es_home)
            _started_by_us = True
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to launch the bundled Elasticsearch")
            _proc = None
            _started_by_us = False
            return False

        if not wait:
            return True
        ok = _wait_until_ready(_proc, timeout, status)
        if not ok and _proc is not None and _proc.poll() is None:
            # It's running but not answering in time — leave it running; the app's
            # own connection check / "Loading…" state will surface the situation.
            logger.warning("Embedded Elasticsearch is running but not ready yet; "
                           "the application will keep trying.")
        return ok


def stop(timeout: float = 20.0) -> None:
    """Stop the embedded Elasticsearch we started.  Safe to call multiple times.

    Does nothing if we did not start a node (e.g. we reused an already-running
    instance, or there was no bundled ES at all).
    """
    global _proc, _started_by_us
    with _lock:
        proc, started = _proc, _started_by_us
        _proc, _started_by_us = None, False
    if proc is None or not started:
        return
    if proc.poll() is not None:
        return
    logger.info("Stopping embedded Elasticsearch (pid=%s)…", proc.pid)
    try:
        if os.name == "nt":
            # Kill the cmd.exe wrapper *and* its java.exe child.
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        else:  # pragma: no cover
            proc.terminate()
    except Exception:  # noqa: BLE001
        pass
    try:
        proc.wait(timeout=timeout)
    except Exception:  # noqa: BLE001
        try:
            proc.kill()
        except Exception:  # noqa: BLE001
            pass
    logger.info("Embedded Elasticsearch stopped.")


def status_summary() -> dict:
    """Small dict describing the embedded-ES situation (handy for diagnostics/logs)."""
    home = find_bundled_es_home()
    return {
        "bundled": home is not None,
        "es_home": str(home) if home else None,
        "data_dir": str(es_data_dir()),
        "running_pid": (_proc.pid if (_proc is not None and _proc.poll() is None) else None),
        "started_by_us": _started_by_us,
        "reachable": is_reachable(),
    }
