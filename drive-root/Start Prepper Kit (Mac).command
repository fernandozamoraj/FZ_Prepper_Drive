#!/bin/bash
# Start Prepper Kit (Mac), offline prepper kit v1.14.1. Double-click this file to start the kit.
# It uses the kit's own portable Python (runtime/), so nothing needs to be installed and no internet is needed.
# Works when it sits next to the offline-prepper-kit folder (drive root) or inside it.
cd "$(dirname "$0")" || exit 1
if [ -f "offline-prepper-kit/bin/intranet.py" ]; then KIT="$PWD/offline-prepper-kit"; else KIT="$PWD"; fi
if [ "$(uname -m)" = "arm64" ]; then PY="$KIT/runtime/mac-arm64/python/bin/python3"
else PY="$KIT/runtime/mac-x64/python/bin/python3"; fi
[ -x "$PY" ] || PY="$(command -v python3)"
printf '\033]0;Prepper Kit\007'   # window title
clear
echo "=============================================="
echo "   OFFLINE PREPPER KIT"
echo "   Library, Bible, maps and directions"
echo "=============================================="
echo
if [ ! -f "$KIT/bin/intranet.py" ] || [ -z "$PY" ]; then
  echo "Could not find the kit's files next to this launcher."
  echo "Keep this file next to the 'offline-prepper-kit' folder."
  read -r -p "Press Return to close." _; exit 1
fi
"$PY" -I "$KIT/bin/intranet.py" --open
echo
echo "The Prepper Kit has stopped. You can close this window."
