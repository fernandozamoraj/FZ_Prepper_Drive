#!/bin/bash
# regenerate-all.sh (offline prepper kit v1.13.2): rebuild the whole kit from the internet on macOS.
# Needs ~200 GB free disk, 24+ GB RAM for the map/routing builds, and many hours (Wikipedia is ~120 GB).
# Safe to stop and re-run: finished steps are skipped and downloads resume.
set -euo pipefail
cd "$(dirname "$0")"
./kit.sh install all
echo "All done. Start the kit with: ./kit.sh start"
