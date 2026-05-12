#!/usr/bin/env python3
r"""Prepare a fresh Elasticsearch distribution for bundling — *build-time tool*.

The packaged app bundles ``runtime/elasticsearch/`` (a private ES distribution,
including its own ``jdk/``).  For the application's existing connection settings
to work verbatim — ``https://localhost:9200``, user ``elastic`` / password
``admin123``, ``verify_certs=False`` — the bundled distribution must be:

* single-node (``discovery.type: single-node``),
* bound to loopback on port 9200,
* security **enabled** with HTTPS (a self-signed cert is fine — the app uses
  ``verify_certs=False``),
* with the built-in ``elastic`` user's password set to ``admin123``.

This script handles the config; the ``elastic`` password lives in the
``.security`` system index inside ``path.data``, so it depends on how you built
the data payload:

* **cold-copy payload** (``tools/prepare_es_payload.py --mode cold-copy`` *with
  ``--source-config``*): the source node's ``config/`` (TLS, keystore) and its
  ``.security`` index are already there — ``elastic``/``admin123`` already works.
  Just run this script *without* ``--set-password`` to make sure the base
  settings are right.

* **snapshot/restore payload** (no ``.security`` restored): run this script
  *with* ``--set-password --data-dir runtime\es-data`` — it does the one-time
  ``ELASTIC_PASSWORD=admin123`` first-start so the password ends up in the
  payload, and (if no TLS is configured yet) lets ES auto-generate certs.

Usage examples::

    # cold-copy payload: just normalise the base settings
    python packaging/configure_bundled_es.py --es-home runtime\elasticsearch

    # snapshot payload: also set the elastic password in the data dir
    python packaging/configure_bundled_es.py --es-home runtime\elasticsearch ^
        --set-password --data-dir runtime\es-data --verify
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import ssl
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
from typing import Optional

_PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Settings we make sure are present in config/elasticsearch.yml (key -> value, YAML scalar).
_REQUIRED_SETTINGS = {
    "cluster.name": "peoplefinder",
    "node.name": "peoplefinder-node",
    "network.host": "_local_",
    "http.port": "9200",
    "discovery.type": "single-node",
    "ingest.geoip.downloader.enabled": "false",
    "xpack.security.enrollment.enabled": "false",
    "xpack.ml.enabled": "false",
}


def _normalise_yml(es_home: Path) -> Path:
    cfg = es_home / "config" / "elasticsearch.yml"
    cfg.parent.mkdir(parents=True, exist_ok=True)
    existing = cfg.read_text(encoding="utf-8") if cfg.is_file() else ""
    lines = existing.splitlines()
    present_keys = set()
    for ln in lines:
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        if ":" in s:
            present_keys.add(s.split(":", 1)[0].strip())
    appended = []
    for key, val in _REQUIRED_SETTINGS.items():
        if key not in present_keys:
            appended.append(f"{key}: {val}")
    if appended:
        block = "\n# --- added by configure_bundled_es.py ---\n" + "\n".join(appended) + "\n"
        cfg.write_text((existing.rstrip() + "\n" if existing.strip() else "") + block, encoding="utf-8")
        print(f"  updated {cfg}:")
        for a in appended:
            print(f"    + {a}")
    else:
        print(f"  {cfg} already has the required settings.")
    return cfg


# --- launch helpers (mirror tools/prepare_es_payload.py) -------------------- #
def _es_launcher(es_home: Path) -> list[str]:
    bat, sh = es_home / "bin" / "elasticsearch.bat", es_home / "bin" / "elasticsearch"
    if os.name == "nt" and bat.is_file():
        return ["cmd.exe", "/c", str(bat)]
    if sh.is_file():
        return [str(sh)]
    if bat.is_file():
        return ["cmd.exe", "/c", str(bat)]
    raise FileNotFoundError(f"No elasticsearch launcher under {es_home/'bin'}")


def _ping(url: str, user: str = "", password: str = "", insecure: bool = True, timeout: int = 10) -> bool:
    headers = {"Accept": "application/json"}
    if user:
        headers["Authorization"] = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()
    ctx = None
    if url.lower().startswith("https"):
        ctx = ssl.create_default_context()
        if insecure:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
    try:
        req = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            json.loads(r.read().decode() or "{}")
        return True
    except Exception:  # noqa: BLE001
        return False


def _start(es_home: Path, data_dir: Path, http_port: int, extra_env: Optional[dict]) -> subprocess.Popen:
    logs, tmp = data_dir.parent / "_cfg-es-logs", data_dir.parent / "_cfg-es-tmp"
    for d in (data_dir, logs, tmp):
        d.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    if (es_home / "jdk").is_dir():
        env["ES_JAVA_HOME"] = str(es_home / "jdk")
        env.pop("JAVA_HOME", None)
    env["ES_TMPDIR"] = str(tmp)
    env["ES_JAVA_OPTS"] = (env.get("ES_JAVA_OPTS", "") + " -Xms1g -Xmx1g").strip()
    if extra_env:
        env.update(extra_env)
    cmd = _es_launcher(es_home) + [
        f"-Epath.data={data_dir}", f"-Epath.logs={logs}",
        "-Enetwork.host=_local_", f"-Ehttp.port={http_port}", "-Ediscovery.type=single-node",
    ]
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    out = open(logs / "stdout.log", "ab", buffering=0)  # noqa: SIM115
    print(f"  starting Elasticsearch on :{http_port} (logs: {logs/'stdout.log'}) …")
    return subprocess.Popen(cmd, cwd=str(es_home), env=env, stdout=out, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, creationflags=flags)


def _stop(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        else:
            proc.terminate()
        proc.wait(timeout=30)
    except Exception:  # noqa: BLE001
        try:
            proc.kill()
        except Exception:  # noqa: BLE001
            pass


def set_password_and_verify(es_home: Path, data_dir: Path, *, http_port: int = 19211) -> int:
    """First-start ES with ELASTIC_PASSWORD=admin123 so the password is baked into *data_dir*."""
    proc = _start(es_home, data_dir, http_port, extra_env={"ELASTIC_PASSWORD": "admin123"})
    https = f"https://127.0.0.1:{http_port}"
    http = f"http://127.0.0.1:{http_port}"
    try:
        ready = None
        for _ in range(150):
            if proc.poll() is not None:
                print(f"  ! Elasticsearch exited early (code {proc.returncode}). Check the logs.", file=sys.stderr)
                return 4
            if _ping(https, "elastic", "admin123"):
                ready = https
                break
            if _ping(http):
                ready = http
                break
            time.sleep(2)
        if ready is None:
            print("  ! Elasticsearch did not come up.", file=sys.stderr)
            return 4
        if ready == http:
            print("  note: this node is running on HTTP (security/TLS not enabled in config).")
            print("        The app expects HTTPS — make sure config/elasticsearch.yml enables")
            print("        xpack.security + TLS, or copy a source config that does. (cold-copy --source-config)")
        else:
            print("  ✓ elastic / admin123 works over HTTPS — password is set in the data dir.")
    finally:
        _stop(proc)
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Configure a bundled Elasticsearch distribution.")
    p.add_argument("--es-home", default=str(_PROJECT_ROOT / "runtime" / "elasticsearch"),
                   help="The Elasticsearch distribution to configure (runtime/elasticsearch).")
    p.add_argument("--set-password", action="store_true",
                   help="Also do a one-time start with ELASTIC_PASSWORD=admin123 against --data-dir.")
    p.add_argument("--data-dir", default=str(_PROJECT_ROOT / "runtime" / "es-data"),
                   help="The es-data payload (where the .security index / password live).")
    p.add_argument("--verify", action="store_true", help="(implied by --set-password) verify elastic/admin123 afterwards.")
    args = p.parse_args(argv)

    es_home = Path(args.es_home).expanduser().resolve()
    if not (es_home / "bin").is_dir():
        print(f"--es-home does not look like an Elasticsearch distribution: {es_home}", file=sys.stderr)
        return 2

    print(f"Configuring bundled Elasticsearch at {es_home}")
    _normalise_yml(es_home)

    if args.set_password:
        data_dir = Path(args.data_dir).expanduser().resolve()
        if not data_dir.exists():
            print(f"--data-dir not found: {data_dir}\n(build the payload first: tools/prepare_es_payload.py)", file=sys.stderr)
            return 2
        rc = set_password_and_verify(es_home, data_dir)
        if rc != 0:
            return rc

    print("\nDone. runtime/elasticsearch is ready to bundle (see packaging/PeopleFinder.spec).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
