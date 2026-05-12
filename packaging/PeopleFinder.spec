# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller recipe for PeopleFinder — one-folder, windowed.
#
#   pyinstaller packaging/PeopleFinder.spec --noconfirm \
#       --distpath packaging/dist --workpath packaging/build
#
# Produces  packaging/dist/PeopleFinder/  containing:
#   PeopleFinder.exe          the app (with a private Python + PySide6)
#   _internal/...             Python runtime / libraries
#   elasticsearch/...         the bundled Elasticsearch distribution (incl. its
#                             own jdk/) — copied verbatim from  runtime/elasticsearch/
#
# The ~22 GB Elasticsearch DATA directory (runtime/es-data/) is intentionally
# NOT bundled here — the Inno Setup installer (installer.iss) ships it straight
# to  %LOCALAPPDATA%\PeopleFinder\es-data .  At runtime, app/services/embedded_es.py
# launches  <app>\elasticsearch\bin\elasticsearch.bat  with  -Epath.data=<that dir>.

import os
import sys

# `Tree` is normally injected into the spec namespace by PyInstaller; fall back
# to an explicit import just in case.
try:
    Tree  # type: ignore[name-defined]  # noqa: B018
except NameError:  # pragma: no cover
    from PyInstaller.building.datastruct import Tree  # type: ignore

_spec_dir = os.path.abspath(globals().get("SPECPATH", os.getcwd()))
_project_root = os.path.abspath(os.path.join(_spec_dir, os.pardir))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# --- bundled Elasticsearch -------------------------------------------------- #
_es_src = os.path.join(_project_root, "runtime", "elasticsearch")
if not os.path.isfile(os.path.join(_es_src, "bin", "elasticsearch.bat")) and \
   not os.path.isfile(os.path.join(_es_src, "bin", "elasticsearch")):
    raise SystemExit(
        "runtime/elasticsearch/ is missing or doesn't look like an Elasticsearch "
        "distribution.\nDownload + configure it first (see packaging/README.md and "
        "packaging/configure_bundled_es.py)."
    )
_es_tree = Tree(_es_src, prefix="elasticsearch")

# --- icon (optional) -------------------------------------------------------- #
_icon = os.path.join(_spec_dir, "app.ico")
_icon = _icon if os.path.isfile(_icon) else None

# --- trim Qt modules the app never uses ------------------------------------- #
_excludes = [
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick",
    "PySide6.QtWebChannel", "PySide6.QtWebSockets",
    "PySide6.QtQml", "PySide6.QtQuick", "PySide6.QtQuick3D", "PySide6.QtQuickWidgets",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.Qt3DInput", "PySide6.Qt3DLogic",
    "PySide6.Qt3DAnimation", "PySide6.Qt3DExtras",
    "PySide6.QtMultimedia", "PySide6.QtMultimediaWidgets",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtGraphs",
    "PySide6.QtPositioning", "PySide6.QtLocation", "PySide6.QtSensors",
    "PySide6.QtBluetooth", "PySide6.QtNfc", "PySide6.QtSerialPort", "PySide6.QtSerialBus",
    "PySide6.QtDesigner", "PySide6.QtUiTools", "PySide6.QtTest", "PySide6.QtHelp",
    "PySide6.QtSql", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
    "tkinter", "test", "unittest", "pydoc_data",
]

_hidden = [
    # The ES client + transport (and its TLS/HTTP deps) — pulled in via es_client.py,
    # listed explicitly so nothing is missed.
    "elasticsearch", "elastic_transport", "urllib3", "certifi", "dotenv",
    # Imported lazily from inside functions:
    "app.services.embedded_es",
]

block_cipher = None

a = Analysis(
    [os.path.join(_project_root, "main.py")],
    pathex=[_project_root],
    binaries=[],
    datas=[],
    hiddenimports=_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=_excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="PeopleFinder",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,                  # windowed GUI — no console window
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    _es_tree,                       # -> dist/PeopleFinder/elasticsearch/...
    strip=False,
    upx=False,
    upx_exclude=[],
    name="PeopleFinder",
)
