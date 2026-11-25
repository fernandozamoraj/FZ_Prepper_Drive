#!/usr/bin/env bash
# Offline prepper kit: serve all finished Kiwix libraries to the local network, v1.9.0
# Usage: ./serve.sh [port]   (default 8080). Stop with Ctrl+C.
# Works from the Mac copy or from the thumb drive (it uses the folder this script lives in).
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
PORT="${1:-8080}"
LOG="$HERE/download.log"
ZIMS=()
for f in "$HERE"/kiwix/*.zim; do
  [ -e "$f" ] || continue
  # Skip a file that's still downloading (not yet marked OK in the download log)
  if pgrep -f "download.sh|kit.py download" >/dev/null && ! grep -q "OK  $(basename "$f")" "$LOG" 2>/dev/null; then
    echo "skip (still downloading): $(basename "$f")"; continue
  fi
  ZIMS+=("$f")
done
[ ${#ZIMS[@]} -eq 0 ] && { echo "No finished .zim files in $HERE/kiwix"; exit 1; }

IP=$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "<this-mac-ip>")
echo "Serving ${#ZIMS[@]} libraries."
echo "  On this Mac:            http://localhost:$PORT"
echo "  On phones/other devices: http://$IP:$PORT   (same Wi-Fi network)"
# Custom home page: one search box with library groups (home/index.html)
INDEX=()
[ -f "$HERE/home/index.html" ] && INDEX=(--customIndex "$HERE/home/index.html")
# Kit header bar (Home · Library · Bible · Maps) on every library page: serve home/nav.js as /nav.js and
# replace the viewer's settings script with one that loads it. Format: <url> <mimetype> <file>, one per line.
# (Paths must not contain spaces; the kit folder and /Volumes/PKNY_256 don't.)
CUSTOM="${TMPDIR:-/tmp}/prepper-kit-kiwix-resources.txt"
if [ -f "$HERE/home/nav.js" ] && [ -f "$HERE/home/viewer_settings.js" ]; then
  printf '/nav.js application/javascript %s\n/viewer_settings.js application/javascript %s\n' \
    "$HERE/home/nav.js" "$HERE/home/viewer_settings.js" > "$CUSTOM"
  export KIWIX_SERVE_CUSTOMIZED_RESOURCES="$CUSTOM"
fi
exec "$HERE/bin/kiwix-serve" --port "$PORT" ${INDEX[@]+"${INDEX[@]}"} "${ZIMS[@]}"
