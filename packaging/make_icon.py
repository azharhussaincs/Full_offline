#!/usr/bin/env python3
"""Render the application icon to ``packaging/app.ico`` (used by the .exe + installer).

The app draws its icon programmatically (``app.gui.icons``), so there's no asset
file in the repo.  PyInstaller and Inno Setup want a real ``.ico``; this produces
one.  Called automatically by ``packaging/build_windows.bat``; run by hand with::

    python packaging/make_icon.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


def main() -> int:
    # Headless rendering — no display needed.
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6.QtWidgets import QApplication  # noqa: F401  (constructed for the pixmap pipeline)

    app = QApplication.instance() or QApplication([])  # noqa: F841

    from app.gui import icons

    out = _PROJECT_ROOT / "packaging" / "app.ico"
    image = icons.app_icon(256).pixmap(256, 256).toImage()
    if image.isNull():
        print("Could not render the icon image.", file=sys.stderr)
        return 1
    if image.save(str(out), "ICO"):
        print(f"Wrote {out} ({out.stat().st_size:,} bytes).")
        return 0
    # Some Qt builds lack the ICO writer — fall back to a PNG so the build can
    # still pick something up (PyInstaller/Inno Setup also accept .png-less builds).
    png = out.with_suffix(".png")
    image.save(str(png), "PNG")
    print(f"Wrote {png} (this Qt build has no ICO writer; the build will proceed without a custom .ico).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
