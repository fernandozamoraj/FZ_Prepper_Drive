#!/usr/bin/env python3
"""places_extract.py (offline prepper kit v1.12.0): pyosmium version of the osmium-tool commands in
build-places, for Windows and Macs without osmium-tool. Needs pyosmium 4 (pip install osmium).

Usage: places_extract.py us.osm.pbf places.geojsonseq states.geojson
  places.geojsonseq: one GeoJSON point per city/town/village/hamlet node, with all its tags
  states.geojson:    state outlines (admin_level=4 boundary relations) as (multi)polygons
"""
import json
import os
import sys
import tempfile

import osmium

if not hasattr(osmium, "BackReferenceWriter"):
    sys.exit(f"pyosmium {osmium.__version__} is too old (need 4.0+). Install osmium-tool instead "
             "(brew install osmium-tool) and run build-places again.")


def tags(obj):
    return {t.k: t.v for t in obj.tags}


def main(pbf, places_out, states_out):
    n = 0
    flt = osmium.filter.TagFilter(*[("place", k) for k in ("city", "town", "village", "hamlet")])
    with open(places_out, "w", encoding="utf-8") as f:
        for node in osmium.FileProcessor(pbf, osmium.osm.NODE).with_filter(flt):
            if not node.location.valid():
                continue
            f.write(json.dumps({"type": "Feature", "properties": tags(node), "geometry": {
                "type": "Point", "coordinates": [node.location.lon, node.location.lat]}}, ensure_ascii=False) + "\n")
            n += 1
    print(f"{n} place nodes")

    # Like `osmium tags-filter r/admin_level=4`: the boundary relations plus the ways and nodes they use
    small = os.path.join(tempfile.mkdtemp(), "states.osm.pbf")
    with osmium.BackReferenceWriter(small, ref_src=pbf, overwrite=True) as w:
        for rel in osmium.FileProcessor(pbf, osmium.osm.RELATION).with_filter(
                osmium.filter.TagFilter(("admin_level", "4"))):
            w.add_relation(rel)
    geo = osmium.geom.GeoJSONFactory()
    feats = []
    for area in osmium.FileProcessor(small).with_areas().with_filter(osmium.filter.EntityFilter(osmium.osm.AREA)):
        if area.from_way() or area.tags.get("admin_level") != "4":
            continue
        try:
            geom = json.loads(geo.create_multipolygon(area))
        except RuntimeError:
            continue  # broken outline
        feats.append({"type": "Feature", "properties": tags(area), "geometry": geom})
    with open(states_out, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": feats}, f)
    print(f"{len(feats)} state outlines")


if __name__ == "__main__":
    main(*sys.argv[1:4])
