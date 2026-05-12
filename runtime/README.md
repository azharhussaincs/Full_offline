# `runtime/` — large build inputs (not committed)

This directory holds the two big artefacts that the Windows installer embeds.
Neither is committed to git; you create them once on the build machine.

```
runtime/
├── elasticsearch/    a full Elasticsearch distribution (Windows .zip, extracted),
│                     including its own bundled jdk/ — version-matched to your
│                     source cluster, and configured by
│                     packaging/configure_bundled_es.py
└── es-data/          the Elasticsearch DATA directory that contains the tc_index
                      index (~22 GB) — produced by tools/prepare_es_payload.py
```

Quick start (see `packaging/README.md` for details):

```bat
:: 1. download + extract a matching Elasticsearch .zip into runtime\elasticsearch\
:: 2. configure it for bundling
python packaging\configure_bundled_es.py --es-home runtime\elasticsearch

:: 3. build the data payload from your live tc_index (stop your source ES first)
python tools\prepare_es_payload.py --mode cold-copy ^
    --source-data  "C:\path\to\elasticsearch\data" ^
    --source-config "C:\path\to\elasticsearch\config" ^
    --out runtime\es-data --es-home runtime\elasticsearch --verify

:: 4. build the installer
packaging\build_windows.bat
```
