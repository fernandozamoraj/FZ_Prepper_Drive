#!/bin/bash
# build-routing.sh (v1.6.0): build the offline car-directions graph from build/us.osm.pbf.
# Takes 1-2 hours and up to ~18 GB of RAM; writes routing/graph-us/ (several GB).
# Safe to re-run: it deletes the old graph first. Log: routing/build.log
set -euo pipefail
cd "$(dirname "$0")"
JAVA=/opt/homebrew/opt/openjdk@21/bin/java
[ -x "$JAVA" ] || JAVA=java
[ -f ../build/us.osm.pbf ] || { echo "Missing ../build/us.osm.pbf (the OpenStreetMap US extract)"; exit 1; }
rm -rf graph-us
mkdir -p logs
echo "Building routing graph... (log: $(pwd)/build.log)"
"$JAVA" -Xmx18g -Xms4g -jar graphhopper-web-11.1.jar import config.yml > build.log 2>&1
echo "Done. Graph in $(pwd)/graph-us ($(du -sh graph-us | cut -f1))"
