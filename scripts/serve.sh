#!/usr/bin/env bash
# Serve the Elm frontend on http://localhost:8765
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PY:-.venv/bin/python}"
exec "$PY" -m http.server 8765 --directory .
