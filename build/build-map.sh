#!/usr/bin/env bash
# Build the whole-US offline map: maps/offline-region-new.pmtiles (swap in when done)
set -eu
cd ~/offline-prepper-kit/build
U=https://download.geofabrik.de/north-america/us/us-261121.osm.pbf
for n in 1 2 3 4 5; do curl -sfL --retry 5 -C - -o us.osm.pbf "$U" && break; sleep 30; done
echo "downloaded: $(du -h us.osm.pbf | cut -f1)"
/opt/homebrew/opt/openjdk@21/bin/java -Xmx14g -jar ../bin/planetiler.jar --osm-path=us.osm.pbf \
  --storage=mmap --nodemap-type=array --download_dir=sources \
  --output=../maps/offline-region-new.pmtiles --force > planetiler.log 2>&1
echo "built: $(du -h ../maps/offline-region-new.pmtiles | cut -f1)"
