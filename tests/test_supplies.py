#!/usr/bin/env python3
"""tests/test_supplies.py (offline prepper kit v1.19.0): the Supplies page's item list and its server side.

    python3 tests/test_supplies.py        (needs node; uses a temporary folder, not family/)

1. home/supplies-data.js loads; every item has a unique id the server accepts, a known phase, the text fields,
   a sensible price and only links to the kit's own pages.
2. /supplies, /supplies-data.js, /supplies.json; checkmarks merge one at a time (two phones never undo each other);
   bad ids, statuses, people and budget are refused; other web sites can't change it; it survives a restart.
"""
import http.server
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILS = []


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        FAILS.append(what)


def data_tests():
    js = ("globalThis.window = globalThis; require(process.argv[1]);"
          "console.log(JSON.stringify({phases: window.SUPPLY_PHASES, groups: window.SUPPLY_GROUPS}))")
    d = json.loads(subprocess.run(["node", "-e", js, os.path.join(KIT, "home", "supplies-data.js")],
                                  capture_output=True, text=True, timeout=30).stdout)
    items = [it for g in d["groups"] for it in g["items"]]
    ids = [it["id"] for it in items]
    check(len(items) >= 60, f"{len(items)} items in {len(d['groups'])} groups")
    check(len(ids) == len(set(ids)), "item ids are unique")
    check(all(re.fullmatch(r"[a-z0-9-]{1,40}", i) for i in ids), "item ids fit the server's pattern")
    check(all(str(it["phase"]) in d["phases"] for it in items), "every item has a known phase")
    check(all(it.get(k) for it in items for k in ("name", "why", "look")), "every item has name, why and look-for text")
    check(all(it["price"] is None or (len(it["price"]) == 2 and 0 <= it["price"][0] <= it["price"][1] <= 5000)
              for it in items), "prices are [low, high] with low <= high")
    check(all(it.get("per") in (None, "person") for it in items), "per is empty or 'person'")
    check(all(it.get("link", "/").startswith("/") for it in items), "links stay on the kit")
    check(all(g.get("intro") and g.get("icon") for g in d["groups"]), "every group has an icon and intro")
    check("travel-router" in ids, "portable travel router is on the list")
    for p in d["phases"]:
        check(any(str(it["phase"]) == p for it in items), f"phase {p} has items")


def server_tests():
    sys.path.insert(0, os.path.join(KIT, "bin"))
    import intranet
    tmp = tempfile.mkdtemp(prefix="supplies-test-")
    intranet.FAMILY_DIR = tmp
    intranet.SUPPLIES_FILE = os.path.join(tmp, "supplies.json")
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), intranet.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{srv.server_address[1]}"

    def req(path, body=None, origin=None):
        r = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(),
                                   headers={"Content-Type": "application/json", **({"Origin": origin} if origin else {})})
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read() or b"{}")

    try:
        for page, text in (("/supplies", b"Emergency supplies"), ("/supplies-data.js", b"SUPPLY_GROUPS")):
            with urllib.request.urlopen(base + page) as r:
                check(text in r.read(), f"{page} is served")
        st, d = req("/supplies.json")
        check(st == 200 and d["people"] == 4 and d["budget"] == 100 and d["items"] == {}, "defaults: 4 people, $100, nothing checked")
        req("/supplies.json", {"items": {"water-stored": "have"}})            # phone 1
        st, d = req("/supplies.json", {"items": {"headlamps": "have"}})      # phone 2, its own change only
        check(d["items"] == {"water-stored": "have", "headlamps": "have"}, "two devices' checkmarks merge")
        st, d = req("/supplies.json", {"items": {"water-stored": "", "pfd": "skip"}, "people": 3, "budget": 75})
        check(d["items"] == {"headlamps": "have", "pfd": "skip"} and d["people"] == 3 and d["budget"] == 75,
              "uncheck, not-needed, people and budget saved")
        for bad, what in (({"items": {"../x": "have"}}, "bad id"), ({"items": {"a": "maybe"}}, "bad status"),
                          ({"people": 0}, "0 people"), ({"people": True}, "people=true"), ({"budget": "lots"}, "text budget"),
                          ({"items": ["a"]}, "items not an object")):
            check(req("/supplies.json", bad)[0] == 400, f"refused: {what}")
        check(req("/supplies.json", {"items": {"cash": "have"}}, origin="http://evil.example")[0] == 403, "other web site refused")
        with open(intranet.SUPPLIES_FILE) as f:
            check(json.load(f)["items"] == {"headlamps": "have", "pfd": "skip"}, "saved to family/supplies.json (survives restart)")
    finally:
        srv.shutdown()
        shutil.rmtree(tmp)


if __name__ == "__main__":
    data_tests()
    server_tests()
    print(f"\n{'ALL PASSED' if not FAILS else str(len(FAILS)) + ' FAILED'}")
    sys.exit(1 if FAILS else 0)
