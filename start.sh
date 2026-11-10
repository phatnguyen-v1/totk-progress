#!/bin/sh
# Run TotK Progress Map from source on Linux. The page walks you through setup on first start.
# Uses the system Python when it already has the packages, otherwise a .venv next to the code.
set -e
cd "$(dirname "$0")"
if [ -x .venv/bin/python ]; then
  PY=.venv/bin/python
elif python3 -c "import zstandard, texture2ddecoder, PIL, segno" 2>/dev/null; then
  PY=python3
else
  python3 -m venv .venv
  .venv/bin/python -m pip install -r requirements.txt
  PY=.venv/bin/python
fi
exec "$PY" server.py "$@"
