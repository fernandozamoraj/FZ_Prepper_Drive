#!/bin/bash
# start-router.sh (v1.6.0): run the offline directions server on 127.0.0.1:8989.
# serve-maps.py forwards the map page's /route requests here. Stop with Ctrl+C (or kill the PID).
set -euo pipefail
cd "$(dirname "$0")"
JAVA=/opt/homebrew/opt/openjdk@21/bin/java
[ -x "$JAVA" ] || JAVA=java
[ -f graph-us/properties ] || { echo "No routing graph yet: run routing/build-routing.sh first"; exit 1; }
mkdir -p logs
# MMAP: the 8.5 GB graph is read from disk on demand, so the router needs little RAM (laptop or Pi)
exec "$JAVA" -Xmx3g -Ddw.graphhopper.graph.dataaccess.default_type=MMAP -jar graphhopper-web-11.1.jar server config.yml
