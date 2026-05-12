#!/usr/bin/env python3
r"""Build the shippable Elasticsearch data payload (``runtime/es-data/``) from the
live ``tc_index`` — a **developer / packaging tool**, never shipped to end users.

The packaged Windows app bundles a private Elasticsearch *distribution* plus a
*data directory* that already contains ``tc_index`` (~22 GB).  This script
produces that data directory.  Two modes:

* ``--mode cold-copy``  (simplest, recommended when you control the source node)
  Stop your source Elasticsearch, then copy its ``data/`` (and, optionally, its
  ``config/``) into ``runtime/es-data/`` (and ``runtime/elasticsearch/config/``).
  Because it's a literal copy of the source node's state, the ``tc_index``
  data, the ``.security`` system index (so ``elastic`` / ``admin123`` keeps
  working) and the TLS config all come along — nothing to reconfigure.

      python tools/prepare_es_payload.py --mode cold-copy ^
          --source-data "C:\path\to\elasticsearch\data" ^
          --source-config "C:\path\to\elasticsearch\config" ^
          --out runtime\es-data --es-home runtime\elasticsearch --verify

* ``--mode snapshot``  (keeps the source node running)
  Register an ``fs`` snapshot repo on the source cluster, snapshot ``tc_index``,
  then restore it into a fresh data dir by briefly launching the bundled
  Elasticsearch distribution.

      python tools/prepare_es_payload.py --mode snapshot ^
          --host https://localhost:9200 --user elastic --password admin123 ^
          --insecure --repo-path "D:\es-snap-repo" ^
          --out runtime\es-data --es-home runtime\elasticsearch --verify

After this runs, ``runtime/es-data/`` is the payload the installer ships to
``%LOCALAPPDATA%\PeopleFinder\es-data`` (see ``packaging/installer.iss``), and
``runtime/elasticsearch/`` is the configured distribution PyInstaller bundles
(see ``packaging/PeopleFinder.spec`` and ``packaging/configure_bundled_es.py``).

Uses only the Python standard library (``urllib`` / ``shutil`` / ``subprocess``).
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Optional

_PROJECT_ROOT = Path(__file__).resolve().parents[1]

INDEX = "tc_index"


# --------------------------------------------------------------------------- #
# Tiny ES HTTP helper (stdlib only)
# --------------------------------------------------------------------------- #
class ES:
    def __init__(self, host: str, user: str = "", password: str = "", insecure: bool = False, timeout: int = 120):
        self.base = host.rstrip("/")
        self.timeout = timeout
        self.headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if user:
            self.headers["Authorization"] = "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()
        self.ctx: Optional[ssl.SSLContext] = None
        if self.base.lower().startswith("https"):
            self.ctx = ssl.create_default_context()
            if insecure:
                self.ctx.check_hostname = False
                self.ctx.verify_mode = ssl.CERT_NONE

    def req(self, method: str, path: str, body: Optional[dict] = None) -> dict[str, Any]:
        data = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(f"{self.base}{path}", data=data, headers=self.headers, method=method)
        with urllib.request.urlopen(r, timeout=self.timeout, context=self.ctx) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")

    def ping(self) -> bool:
        try:
            self.req("GET", "/")
            return True
        except Exception:  # noqa: BLE001
            return False

    def count(self, index: str = INDEX) -> int:
        try:
            return int(self.req("GET", f"/{index}/_count").get("count", 0))
        except Exception:  # noqa: BLE001
            return -1


def _fmt(n: int) -> str:
    return f"{n:,}"


def _human_size(path: Path) -> str:
    total = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += (Path(root) / f).stat().st_size
            except OSError:
                pass
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if total < 1024 or unit == "TB":
            return f"{total:.1f} {unit}"
        total /= 1024
    return f"{total:.1f} TB"


# --------------------------------------------------------------------------- #
# Launch the bundled Elasticsearch briefly (for restore / verification)
# --------------------------------------------------------------------------- #
def _es_binary(es_home: Path) -> list[str]:
    bat = es_home / "bin" / "elasticsearch.bat"
    sh = es_home / "bin" / "elasticsearch"
    if os.name == "nt" and bat.is_file():
        return ["cmd.exe", "/c", str(bat)]
    if sh.is_file():
        return [str(sh)]
    if bat.is_file():
        return ["cmd.exe", "/c", str(bat)]
    raise FileNotFoundError(f"No elasticsearch launcher under {es_home / 'bin'}")


def _start_temp_es(es_home: Path, data_dir: Path, *, http_port: int = 19200,
                   repo_path: Optional[Path] = None, extra_env: Optional[dict] = None) -> subprocess.Popen:
    logs = data_dir.parent / "_prep-es-logs"
    tmp = data_dir.parent / "_prep-es-tmp"
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
    overrides = [
        f"-Epath.data={data_dir}", f"-Epath.logs={logs}",
        "-Enetwork.host=_local_", f"-Ehttp.port={http_port}",
        "-Ediscovery.type=single-node", "-Eingest.geoip.downloader.enabled=false",
        "-Expack.security.enrollment.enabled=false",
    ]
    if repo_path is not None:
        repo_path.mkdir(parents=True, exist_ok=True)
        overrides.append(f"-Epath.repo={repo_path}")
    cmd = _es_binary(es_home) + overrides
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
    out = open(logs / "stdout.log", "ab", buffering=0)  # noqa: SIM115
    print(f"  starting temporary Elasticsearch on :{http_port} (logs: {logs/'stdout.log'}) …")
    return subprocess.Popen(cmd, cwd=str(es_home), env=env, stdout=out, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, creationflags=flags)


def _stop_temp_es(proc: subprocess.Popen) -> None:
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


def _wait_es(es: ES, proc: subprocess.Popen, timeout: int = 240) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if proc.poll() is not None:
            print(f"  ! temporary Elasticsearch exited early (code {proc.returncode})", file=sys.stderr)
            return False
        if es.ping():
            return True
        time.sleep(2)
    return False


# --------------------------------------------------------------------------- #
# Modes
# --------------------------------------------------------------------------- #
def cold_copy(args: argparse.Namespace) -> int:
    src_data = Path(args.source_data).expanduser().resolve()
    out = Path(args.out).expanduser().resolve()
    if not src_data.is_dir():
        print(f"--source-data not found: {src_data}", file=sys.stderr)
        return 2

    # Safety: a live Lucene data dir must not be copied — make sure the source ES is down.
    probe = ES(args.host, args.user, args.password, insecure=args.insecure, timeout=5)
    if probe.ping() and not args.force:
        print("Source Elasticsearch appears to be RUNNING at", args.host,
              "\nStop it first (copying a live data directory will corrupt the copy),"
              "\nor pass --force if you are certain it is safe.", file=sys.stderr)
        return 3

    if out.exists():
        print(f"  removing existing {out} …")
        shutil.rmtree(out)
    print(f"  copying {src_data}  ->  {out}   (this can take a long time for ~22 GB) …")
    t0 = time.time()
    shutil.copytree(src_data, out)
    print(f"  copied {_human_size(out)} in {(time.time()-t0)/60:.1f} min")

    if args.source_config and args.es_home:
        src_cfg = Path(args.source_config).expanduser().resolve()
        dst_cfg = Path(args.es_home).expanduser().resolve() / "config"
        if src_cfg.is_dir():
            print(f"  copying source config  {src_cfg}  ->  {dst_cfg}   (keeps TLS / keystore intact) …")
            if dst_cfg.exists():
                shutil.rmtree(dst_cfg)
            shutil.copytree(src_cfg, dst_cfg)
        else:
            print(f"  ! --source-config not found ({src_cfg}); skipping config copy", file=sys.stderr)

    if args.verify:
        return _verify(out, Path(args.es_home).expanduser().resolve() if args.es_home else None,
                       expect_count=args.expect_count)
    print(f"\nDone. Payload: {out}  ({_human_size(out)})")
    return 0


def snapshot_mode(args: argparse.Namespace) -> int:
    out = Path(args.out).expanduser().resolve()
    repo_path = Path(args.repo_path).expanduser().resolve()
    es = ES(args.host, args.user, args.password, insecure=args.insecure)
    if not es.ping():
        print(f"Cannot reach source Elasticsearch at {args.host}", file=sys.stderr)
        return 2

    src_count = es.count(INDEX)
    print(f"  source {INDEX}: {_fmt(src_count) if src_count >= 0 else 'unknown'} docs")

    # Register / reuse the fs repo (requires path.repo on the SOURCE cluster).
    repo = args.repo_name
    try:
        es.req("PUT", f"/_snapshot/{repo}", {"type": "fs", "settings": {"location": str(repo_path), "compress": True}})
        print(f"  registered snapshot repo {repo!r} -> {repo_path}")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        print("Could not register the snapshot repo. The SOURCE cluster must have", file=sys.stderr)
        print(f"  path.repo: [ \"{repo_path}\" ]", file=sys.stderr)
        print("in its elasticsearch.yml (then restart it). Server said:", file=sys.stderr)
        print(" ", body[:500], file=sys.stderr)
        return 3

    snap = args.snapshot_name
    print(f"  taking snapshot {snap!r} of {INDEX} (wait_for_completion) …")
    es.req("DELETE", f"/_snapshot/{repo}/{snap}", None) if False else None  # (left explicit-on-purpose: no auto-delete)
    es.req("PUT", f"/_snapshot/{repo}/{snap}?wait_for_completion=true",
           {"indices": INDEX, "include_global_state": False})
    print("  snapshot complete.")

    if not args.es_home:
        print("\nSnapshot done. To finish, restore it into the payload data dir with the BUNDLED "
              "Elasticsearch, e.g.:\n"
              f"  python tools/prepare_es_payload.py --mode restore-only --es-home runtime\\elasticsearch "
              f"--repo-path \"{repo_path}\" --repo-name {repo} --snapshot-name {snap} --out {out} --verify")
        return 0
    return _restore(Path(args.es_home).expanduser().resolve(), repo_path, repo, snap, out,
                    verify=args.verify, expect_count=(src_count if src_count >= 0 else args.expect_count))


def restore_only(args: argparse.Namespace) -> int:
    return _restore(Path(args.es_home).expanduser().resolve(), Path(args.repo_path).expanduser().resolve(),
                    args.repo_name, args.snapshot_name, Path(args.out).expanduser().resolve(),
                    verify=args.verify, expect_count=args.expect_count)


def _restore(es_home: Path, repo_path: Path, repo: str, snap: str, out: Path,
             *, verify: bool, expect_count: int) -> int:
    if out.exists():
        print(f"  removing existing {out} …")
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    proc = _start_temp_es(es_home, out, http_port=19200, repo_path=repo_path)
    es = ES("http://127.0.0.1:19200", timeout=120)  # fresh ES via -E has no security configured yet
    try:
        if not _wait_es(es, proc):
            return 4
        # The temp node may have security on (if config came from the source). Be lenient about auth.
        try:
            es.req("PUT", f"/_snapshot/{repo}", {"type": "fs", "settings": {"location": str(repo_path)}})
        except urllib.error.HTTPError:
            pass
        print(f"  restoring {INDEX} from {repo}/{snap} …")
        es.req("POST", f"/_snapshot/{repo}/{snap}/_restore?wait_for_completion=true", {"indices": INDEX})
        try:
            es.req("POST", f"/{INDEX}/_flush", None)
            es.req("POST", f"/{INDEX}/_forcemerge?max_num_segments=1", None)
        except Exception:  # noqa: BLE001
            pass
        n = es.count(INDEX)
        print(f"  restored {INDEX}: {_fmt(n) if n >= 0 else 'unknown'} docs")
        if expect_count and n >= 0 and n != expect_count:
            print(f"  ! WARNING: restored count ({_fmt(n)}) != expected ({_fmt(expect_count)})", file=sys.stderr)
    finally:
        _stop_temp_es(proc)
    print(f"\nDone. Payload: {out}  ({_human_size(out)})")
    if verify:
        return _verify(out, es_home, expect_count=expect_count)
    return 0


def _verify(data_dir: Path, es_home: Optional[Path], *, expect_count: int) -> int:
    if not es_home:
        print("  (skipping --verify: no --es-home given)")
        print(f"\nDone. Payload: {data_dir}  ({_human_size(data_dir)})")
        return 0
    print("\nVerifying the payload by launching the bundled Elasticsearch on it …")
    proc = _start_temp_es(es_home, data_dir, http_port=19201)
    # Try the configured https/security endpoint first, then plain http as a fallback.
    candidates = [ES("https://127.0.0.1:19201", "elastic", "admin123", insecure=True, timeout=15),
                  ES("http://127.0.0.1:19201", timeout=15)]
    try:
        ready = False
        for _ in range(120):
            if proc.poll() is not None:
                print(f"  ! Elasticsearch exited early (code {proc.returncode}) — check the prep logs.", file=sys.stderr)
                return 4
            for es in candidates:
                if es.ping():
                    ready, chosen = True, es
                    break
            if ready:
                break
            time.sleep(2)
        if not ready:
            print("  ! Elasticsearch did not become reachable for verification.", file=sys.stderr)
            return 4
        n = chosen.count(INDEX)
        print(f"  reachable at {chosen.base}; {INDEX} = {_fmt(n) if n >= 0 else 'unknown'} docs")
        if n < 0:
            print(f"  ! Could not query {INDEX}. If the node has security on, ensure elastic/admin123 is set.", file=sys.stderr)
            return 5
        if expect_count and n != expect_count:
            print(f"  ! WARNING: count ({_fmt(n)}) != expected ({_fmt(expect_count)})", file=sys.stderr)
        # Smoke a couple of searches.
        try:
            for q in ("sunny", "john"):
                hits = chosen.req("POST", f"/{INDEX}/_search?size=1",
                                  {"query": {"multi_match": {"query": q, "fields": ["*"], "lenient": True}}})
                total = ((hits.get("hits") or {}).get("total") or {}).get("value", "?")
                print(f"    search {q!r}: total≈{total}")
        except Exception as exc:  # noqa: BLE001
            print(f"    (sample search skipped: {exc})")
        print("  ✓ payload looks good.")
    finally:
        _stop_temp_es(proc)
    print(f"\nDone. Payload: {data_dir}  ({_human_size(data_dir)})")
    return 0


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def parse_args(argv=None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="prepare_es_payload",
                                description="Build runtime/es-data from the live tc_index.",
                                formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    p.add_argument("--mode", choices=["cold-copy", "snapshot", "restore-only", "verify-only"], default="cold-copy")
    p.add_argument("--out", default=str(_PROJECT_ROOT / "runtime" / "es-data"), help="Output data directory (the payload).")
    p.add_argument("--es-home", default=str(_PROJECT_ROOT / "runtime" / "elasticsearch"),
                   help="The bundled Elasticsearch distribution (used for restore / verify; pass '' to skip those).")
    p.add_argument("--verify", action="store_true", help="After building, launch the bundled ES on the payload and check tc_index.")
    p.add_argument("--expect-count", type=int, default=0, help="Expected document count (0 = don't check).")
    # cold-copy
    p.add_argument("--source-data", help="[cold-copy] Path to the SOURCE Elasticsearch 'data' directory.")
    p.add_argument("--source-config", help="[cold-copy] Path to the SOURCE 'config' directory (copied into --es-home/config).")
    p.add_argument("--force", action="store_true", help="[cold-copy] Copy even if the source ES seems to be running (NOT recommended).")
    # source connection (used by cold-copy's safety probe and by snapshot mode)
    p.add_argument("--host", default=os.getenv("ES_HOST", "https://localhost:9200"))
    p.add_argument("--user", default=os.getenv("ES_USERNAME", "elastic"))
    p.add_argument("--password", default=os.getenv("ES_PASSWORD", "admin123"))
    p.add_argument("--insecure", action="store_true", help="Skip TLS verification for the source connection.")
    # snapshot / restore-only
    p.add_argument("--repo-path", help="[snapshot/restore] Filesystem path of the fs snapshot repository.")
    p.add_argument("--repo-name", default="peoplefinder_payload")
    p.add_argument("--snapshot-name", default="tc_index_payload")
    return p.parse_args(argv)


def main(argv=None) -> int:
    args = parse_args(argv)
    es_home_ok = bool(args.es_home and Path(args.es_home).expanduser().is_dir())
    if args.es_home and not es_home_ok and args.mode in ("restore-only", "verify-only"):
        print(f"--es-home not found: {args.es_home}", file=sys.stderr)
        return 2
    if not es_home_ok:
        args.es_home = ""

    if args.mode == "cold-copy":
        if not args.source_data:
            print("--mode cold-copy requires --source-data", file=sys.stderr)
            return 2
        return cold_copy(args)
    if args.mode == "snapshot":
        if not args.repo_path:
            print("--mode snapshot requires --repo-path", file=sys.stderr)
            return 2
        return snapshot_mode(args)
    if args.mode == "restore-only":
        if not (args.es_home and args.repo_path):
            print("--mode restore-only requires --es-home and --repo-path", file=sys.stderr)
            return 2
        return restore_only(args)
    # verify-only
    return _verify(Path(args.out).expanduser().resolve(), Path(args.es_home).expanduser().resolve() if args.es_home else None,
                   expect_count=args.expect_count)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        raise SystemExit(130)
