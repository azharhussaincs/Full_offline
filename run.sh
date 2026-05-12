#!/usr/bin/env bash

# ---------------------------------------------------------------------------
# Convenience launcher.
#   * activates ./venv if it exists
#   * starts the desktop application
# Usage:  ./run.sh
# ---------------------------------------------------------------------------
set -euo pipefail

cd "$(dirname "$0")"

if [[ -d "venv" ]]; then
  # shellcheck disable=SC1091
  source venv/bin/activate
elif [[ -d ".venv" ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

exec python main.py "$@"
