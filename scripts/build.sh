#!/usr/bin/env bash
# Rebuild the DB, re-export JSON, recompile Elm.
set -euo pipefail
cd "$(dirname "$0")/.."

PY="${PY:-.venv/bin/python}"
$PY build_db.py --fresh
$PY export.py
elm make src/Main.elm --optimize --output=elm.js
echo "✓ build complete"
