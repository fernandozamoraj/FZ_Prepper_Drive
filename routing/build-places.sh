#!/bin/bash
# build-places.sh (v1.6.0): make map-viewer/places.json, the offline town search list
# (every city, town, village and hamlet node in build/us.osm.pbf, tagged with its state).
# Takes a few minutes, low memory. First run creates routing/.venv with shapely (needs internet once).
set -euo pipefail
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || { python3 -m venv .venv && .venv/bin/pip -q install shapely; }
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
osmium tags-filter ../build/us.osm.pbf n/place=city,town,village,hamlet -o "$TMP/places.osm.pbf" --overwrite
osmium export "$TMP/places.osm.pbf" -f geojsonseq -o "$TMP/places.geojsonseq" --overwrite --geometry-types=point
osmium tags-filter ../build/us.osm.pbf r/admin_level=4 -o "$TMP/states.osm.pbf" --overwrite
osmium export "$TMP/states.osm.pbf" -f geojson -o states.geojson --overwrite --geometry-types=polygon
.venv/bin/python make_places.py "$TMP/places.geojsonseq" states.geojson ../map-viewer/places.json
