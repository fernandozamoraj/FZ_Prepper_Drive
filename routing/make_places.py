#!/usr/bin/env python3
"""make_places.py (v1.6.0): turn an osmium geojsonseq export of place nodes into a compact
search list for the map page: [[name, state, kind, lon, lat, population], ...] sorted biggest first.
The state comes from point-in-polygon against states.geojson (OSM admin_level=4), since OSM place
nodes rarely carry a state tag. Needs shapely (routing/.venv).

Usage: make_places.py places.geojsonseq states.geojson out.json
"""
import json
import sys

from shapely import STRtree
from shapely.geometry import Point, shape


def load_states(path):
    geoms, codes = [], []
    for f in json.load(open(path, encoding="utf-8"))["features"]:
        iso = f["properties"].get("ISO3166-2", "")
        if iso.startswith("US-") and len(iso) == 5:
            geoms.append(shape(f["geometry"]).buffer(0))
            codes.append(iso[3:])
    return STRtree(geoms), geoms, codes


def state_of(pt, tree, geoms, codes):
    for i in tree.query(pt, predicate="intersects"):
        return codes[i]
    i = tree.nearest(pt)  # coastal or island towns just outside the outline
    if geoms[i].distance(pt) < 0.25:
        return codes[i]
    return "AK" if pt.y > 51 else ""  # Alaska's outline is missing from the OSM US extract

KIND_RANK = {"city": 0, "town": 1, "village": 2, "hamlet": 3}

# OSM rarely tags the state on place nodes, so derive it from is_in tags or the GNIS/TIGER fields
STATE_KEYS = ("is_in:state_code", "addr:state", "is_in:state", "tiger:STATE", "gnis:ST_alpha")


def main(src, states_path, dst):
    tree, geoms, codes = load_states(states_path)
    out = []
    with open(src, encoding="utf-8") as f:
        for line in f:
            line = line.strip().lstrip("\x1e")
            if not line:
                continue
            feat = json.loads(line)
            p = feat.get("properties", {})
            name = p.get("name:en") or p.get("name")
            kind = p.get("place")
            if not name or kind not in KIND_RANK:
                continue
            lon, lat = feat["geometry"]["coordinates"]
            state = next((p[k] for k in STATE_KEYS if p.get(k)), "")
            if len(state) > 2:
                state = STATE_ABBR.get(state.strip().lower(), "")
            state = state_of(Point(lon, lat), tree, geoms, codes) or state
            try:
                pop = int(str(p.get("population", "0")).replace(",", "").split(".")[0] or 0)
            except ValueError:
                pop = 0
            out.append([name, state.upper(), kind, round(lon, 5), round(lat, 5), pop])
    out.sort(key=lambda r: (KIND_RANK[r[2]], -r[5], r[0]))
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(out, f, separators=(",", ":"), ensure_ascii=False)
    print(f"{len(out)} places -> {dst}")


STATE_ABBR = {n.lower(): a for a, n in [
    ("AL", "Alabama"), ("AK", "Alaska"), ("AZ", "Arizona"), ("AR", "Arkansas"), ("CA", "California"),
    ("CO", "Colorado"), ("CT", "Connecticut"), ("DE", "Delaware"), ("DC", "District of Columbia"),
    ("FL", "Florida"), ("GA", "Georgia"), ("HI", "Hawaii"), ("ID", "Idaho"), ("IL", "Illinois"),
    ("IN", "Indiana"), ("IA", "Iowa"), ("KS", "Kansas"), ("KY", "Kentucky"), ("LA", "Louisiana"),
    ("ME", "Maine"), ("MD", "Maryland"), ("MA", "Massachusetts"), ("MI", "Michigan"), ("MN", "Minnesota"),
    ("MS", "Mississippi"), ("MO", "Missouri"), ("MT", "Montana"), ("NE", "Nebraska"), ("NV", "Nevada"),
    ("NH", "New Hampshire"), ("NJ", "New Jersey"), ("NM", "New Mexico"), ("NY", "New York"),
    ("NC", "North Carolina"), ("ND", "North Dakota"), ("OH", "Ohio"), ("OK", "Oklahoma"), ("OR", "Oregon"),
    ("PA", "Pennsylvania"), ("RI", "Rhode Island"), ("SC", "South Carolina"), ("SD", "South Dakota"),
    ("TN", "Tennessee"), ("TX", "Texas"), ("UT", "Utah"), ("VT", "Vermont"), ("VA", "Virginia"),
    ("WA", "Washington"), ("WV", "West Virginia"), ("WI", "Wisconsin"), ("WY", "Wyoming"),
    ("PR", "Puerto Rico")]}

if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], sys.argv[3])
