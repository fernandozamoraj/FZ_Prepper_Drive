#!/bin/bash
# kit.sh (offline prepper kit v1.20.1): run a kit command on macOS. See README.md, or ./kit.sh --help
#   ./kit.sh setup | download | build-map | build-routing | build-places | build-bible | build-all | all
# Uses the kit's portable Python (runtime/); if it isn't there yet, downloads it first (~25 MB).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
if [ "$(uname -m)" = "arm64" ]; then P=mac-arm64; T=aarch64-apple-darwin; else P=mac-x64; T=x86_64-apple-darwin; fi
PY="$HERE/runtime/$P/python/bin/python3"
if [ ! -x "$PY" ]; then
  echo "Getting portable Python for $P..."
  R=20261026; V=3.12.16
  mkdir -p "$HERE/runtime/$P"
  curl -fL --retry 3 "https://github.com/astral-sh/python-build-standalone/releases/download/$R/cpython-$V+$R-$T-install_only.tar.gz" \
    | tar -xz -C "$HERE/runtime/$P"
fi
exec "$PY" -I "$HERE/scripts/kit.py" "$@"
