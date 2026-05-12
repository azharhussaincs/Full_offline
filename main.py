#!/usr/bin/env python3
"""Application entry point for the Offline Elasticsearch Explorer.

Run it directly from the project root::

    python main.py

It configures logging first, then launches the PySide6 desktop GUI.  All of the
real logic lives under the :mod:`app` package; this module only wires things up.
"""
from __future__ import annotations

import sys
from pathlib import Path


def main() -> int:
    """Configure logging and start the GUI; return the process exit code."""
    # Make the project root importable no matter which directory we were run from.
    project_root = Path(__file__).resolve().parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from app.config.logging_config import configure_logging

    log = configure_logging()
    log.info("Bootstrapping application…")

    try:
        from app.gui.app import run

        return run(sys.argv)
    except Exception:  # noqa: BLE001 - last-resort guard so failures get logged
        log.exception("Fatal error while running the application")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
