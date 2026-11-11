#!/bin/sh
# Builds dist/TotKProgressMap-linux-x86_64 (one file). Needs Python 3.10+ with venv.
# The Linux build shows the map in the browser, so pywebview is left out. Build on the oldest system
# you want to support: the binary needs that system's glibc or newer.
set -e
cd "$(dirname "$0")"
PY="${PYTHON:-python3}"
[ -x build/venv/bin/python ] || "$PY" -m venv build/venv
. build/venv/bin/activate
grep -v '^pywebview' requirements.txt > build/requirements-linux.txt
python -m pip install --upgrade -r build/requirements-linux.txt pyinstaller
python -m PyInstaller --noconfirm --clean --onefile \
  --name TotKProgressMap-linux-x86_64 \
  --add-data "web:web" \
  --hidden-import zstandard --hidden-import texture2ddecoder \
  --hidden-import PIL.WebPImagePlugin --hidden-import PIL.PngImagePlugin \
  --hidden-import segno --hidden-import certifi --exclude-module webview \
  server.py
echo
echo "Built: $(pwd)/dist/TotKProgressMap-linux-x86_64"
