#!/bin/bash
# regenerate-all.sh (offline prepper kit v1.12.0): rebuild the whole kit from the internet on macOS.
# Needs ~200 GB free disk, 24+ GB RAM for the map/routing builds, and many hours (Wikipedia is ~120 GB).
# Safe to stop and re-run: finished steps are skipped and downloads resume.
set -euo pipefail
cd "$(dirname "$0")"
./kit.sh setup
./kit.sh download
./kit.sh build-all
echo "All done. Start the kit with: python3 bin/intranet.py --open   (or double-click drive-root/Start Prepper Kit (Mac).command after make-drive.sh)"
