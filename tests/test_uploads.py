#!/usr/bin/env python3
"""tests/test_uploads.py (offline prepper kit v1.19.0): documents added on the Books page (bin/intranet.py /uploads).

    python3 tests/test_uploads.py        (uses a temporary folder, not uploads/)

Adds a PDF and an EPUB, lists them with title / who / category, serves them back (with byte ranges and nosniff),
keeps both copies when two people upload the same name, refuses: no X-Kit-Upload header, other web sites, unknown
category, web pages and programs (.html, .exe), a renamed file that isn't really a PDF, empty and too-big files,
path tricks in the name; phones can add but not remove; removing moves the file to .trash; hidden files never served.
Videos on the Movies page (kind=movies): MP4/MKV in, fakes and wrong kinds out, listing, streaming, removal.
Also /share.json, the Wi-Fi address the Home page shows for sharing the kit.
"""
import http.client
import json
import os
import shutil
import sys
import tempfile
import threading
import urllib.parse

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FAILS = []
PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n" + b"x" * 5000
EPUB = b"PK\x03\x04" + b"\x00" * 3000
MP4 = b"\x00\x00\x00\x20ftypisom\x00\x00\x02\x00" + b"\x00" * 4000
MKV = b"\x1a\x45\xdf\xa3" + b"\x00" * 4000


def check(cond, what):
    print(("ok   " if cond else "FAIL ") + what)
    if not cond:
        FAILS.append(what)


def main():
    sys.path.insert(0, os.path.join(KIT, "bin"))
    import http.server
    import intranet
    kit = tempfile.mkdtemp(prefix="uploads-test-")  # /files/uploads/ is read from KIT/uploads
    tmp = os.path.join(kit, "uploads")
    os.makedirs(tmp)
    intranet.KIT = kit
    intranet.UPLOADS = tmp
    intranet.UPLOAD_INDEX = os.path.join(tmp, ".index.json")
    movies = os.path.join(kit, "movies")
    os.makedirs(movies)
    intranet.catalog.MOVIES_DIR = movies
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), intranet.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    port = srv.server_address[1]
    remote = {"on": False}
    real_is_local = intranet.Handler.is_local
    intranet.Handler.is_local = lambda self: False if remote["on"] else real_is_local(self)

    def req(method, path, body=b"", headers=None):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=20)
        c.request(method, path, body=body, headers=headers or {})
        r = c.getresponse()
        data = r.read()
        c.close()
        try:
            return r.status, json.loads(data), dict(r.getheaders())
        except ValueError:
            return r.status, data, dict(r.getheaders())

    def up(name, data, cat="survival", title="", by="", hdr=True, origin=None, kind="docs"):
        q = urllib.parse.urlencode({"kind": kind, "cat": cat, "name": name, "title": title, "by": by})
        h = {"Content-Type": "application/octet-stream", "Content-Length": str(len(data))}
        if hdr:
            h["X-Kit-Upload"] = "1"
        if origin:
            h["Origin"] = origin
        return req("POST", "/uploads?" + q, data, h)

    try:
        st, d, _ = req("GET", "/share.json")
        check(st == 200 and d["port"] == port and (d["url"] is None or d["url"] == f"http://{d['ip']}:{port}/"),
              f"Home page share address: {d.get('url')}")
        st, d, _ = req("GET", "/uploads.json")
        check(st == 200 and d["local"] and all(not c["items"] for c in d["cats"]), "empty list, this computer is local")
        st, d, _ = up("Water Purification.pdf", PDF, title="EPA water guide", by="Maria")
        check(st == 200 and d["key"] == "survival/Water Purification.pdf", f"PDF added: {st} {d.get('key') or d}")
        it = next(c for c in d["cats"] if c["id"] == "survival")["items"][0]
        check(it["title"] == "EPA water guide" and it["by"] == "Maria" and it["ext"] == "pdf", "listed with title, name and type")
        st, d, _ = up("Water Purification.pdf", PDF, by="Jose")
        check(st == 200 and d["key"] == "survival/Water Purification (2).pdf", "same name again: both kept, '(2)'")
        remote["on"] = True
        st, d, _ = up("Field Manual.epub", EPUB, cat="medical")
        check(st == 200 and d["local"] is False, "a phone can add (EPUB, Medical)")
        st, d, _ = req("POST", "/uploads/delete", json.dumps({"key": "medical/Field Manual.epub"}).encode(),
                       {"Content-Type": "application/json", "X-Kit-Upload": "1"})
        check(st == 403, "a phone can't remove")
        remote["on"] = False

        # serving
        st, body, h = req("GET", "/files/uploads/" + urllib.parse.quote("survival/Water Purification.pdf"),
                          headers={"Range": "bytes=0-4"})
        check(st == 206 and body == b"%PDF-", "served back with byte ranges")
        check(h.get("X-Content-Type-Options") == "nosniff" and h.get("Content-Type") == "application/pdf", "PDF type + nosniff")
        check(req("GET", "/files/uploads/.index.json")[0] == 404, "the hidden index is never served")
        check(req("GET", "/files/uploads/survival/../../etc/passwd")[0] == 404, "path tricks not served")

        # refusals
        check(up("a.pdf", PDF, hdr=False)[0] == 403, "no X-Kit-Upload header: refused")
        check(up("a.pdf", PDF, origin="http://evil.example")[0] == 403, "other web site: refused")
        check(up("a.pdf", PDF, cat="secret")[0] == 400, "unknown category: refused")
        check(up("page.html", b"<script>alert(1)</script>")[0] == 415, ".html refused")
        check(up("setup.exe", b"MZ" + b"\x00" * 100)[0] == 415, ".exe refused")
        check(up("fake.pdf", b"<html>not a pdf</html>")[0] == 415, "renamed file that isn't a PDF: refused")
        check(up("empty.pdf", b"")[0] == 411, "empty file refused")
        saved_max = intranet.UPLOAD_MAX
        intranet.UPLOAD_MAX = 1000
        check(up("big.pdf", PDF)[0] == 413, "over the size limit: refused")
        intranet.UPLOAD_MAX = saved_max
        st, d, _ = up("../../evil/.hidden.pdf", PDF)
        check(st == 200 and d["key"] == "survival/hidden.pdf", f"path and hidden-file tricks in the name cleaned: {d.get('key')}")
        st, d, _ = up('wi:n*do?ws<>|.PDF', PDF, cat="manuals")
        check(st == 200 and d["key"] == "manuals/wi_n_do_ws___.pdf", f"characters Windows refuses replaced: {d.get('key')}")
        check(not [f for f in os.listdir(tmp) if f.startswith(".incoming")], "no half-written files left behind")

        # remove (this computer)
        st, d, _ = req("POST", "/uploads/delete", json.dumps({"key": "survival/Water Purification (2).pdf"}).encode(),
                       {"Content-Type": "application/json", "X-Kit-Upload": "1"})
        keys = [i["key"] for c in d["cats"] for i in c["items"]]
        check(st == 200 and "survival/Water Purification (2).pdf" not in keys, "this computer can remove")
        check(any(f.endswith("Water Purification (2).pdf") for f in os.listdir(os.path.join(tmp, ".trash"))),
              "removed file is in .trash, not erased")
        check(req("POST", "/uploads/delete", json.dumps({"key": "survival/../../x.pdf"}).encode(),
                  {"Content-Type": "application/json", "X-Kit-Upload": "1"})[0] == 400, "remove with a path trick refused")
        os.makedirs(os.path.join(tmp, "radio"), exist_ok=True)
        shutil.copy(os.path.join(tmp, "survival", "Water Purification.pdf"), os.path.join(tmp, "radio", "By hand.pdf"))
        st, d, _ = req("GET", "/uploads.json")
        radio = next(c for c in d["cats"] if c["id"] == "radio")["items"]
        check([i["title"] for i in radio] == ["By hand"], "a file copied into uploads/<category>/ by hand shows up")

        # ---- videos (Movies page) ----
        st, d, _ = up("Grandma 80th birthday.mp4", MP4, kind="movies", cat="my-movies", title="Grandma's 80th", by="Ana")
        check(st == 200 and d["key"] == "my-movies/Grandma 80th birthday.mp4", f"MP4 added to movies/my-movies: {st} {d.get('key') or d}")
        mine = [m for c in d["categories"] if c["id"] == "my-movies" for m in c["movies"]]
        check([(m["title"], m["license"].split(" · ")[0], m["key"]) for m in mine] ==
              [("Grandma's 80th", "added by Ana", "my-movies/Grandma 80th birthday.mp4")], "listed on Movies with title, name, key")
        check(d["local"] is True and "my-movies" in d["upload"]["cats"] and "open-movies" not in d["upload"]["cats"],
              "Movies page gets upload categories (not the Creative Commons one)")
        st, d, _ = up("Camping.mkv", MKV, kind="movies", cat="adventure")
        check(st == 200 and os.path.isfile(os.path.join(movies, "adventure", "Camping.mkv")), "MKV added to Adventure")
        check(up("fake.mp4", b"<html>" + b"x" * 100, kind="movies", cat="my-movies")[0] == 415, "renamed file that isn't an MP4: refused")
        check(up("book.pdf", PDF, kind="movies", cat="my-movies")[0] == 415, "a PDF on the Movies page: refused")
        check(up("film.mp4", MP4, kind="docs")[0] == 415, "a video on the Books page: refused")
        check(up("a.mp4", MP4, kind="movies", cat="open-movies")[0] == 400, "Creative Commons category can't be uploaded to")
        check(up("a.mp4", MP4, kind="games", cat="my-movies")[0] == 400, "unknown kind refused")
        st, body, h = req("GET", "/files/movies/" + urllib.parse.quote("my-movies/Grandma 80th birthday.mp4"), headers={"Range": "bytes=4-7"})
        check(st == 206 and body == b"ftyp" and h.get("Content-Type") == "video/mp4", "video streams back with byte ranges")
        check(req("GET", "/files/movies/.uploads.json")[0] == 404, "the movies index is never served")
        remote["on"] = True
        check(req("POST", "/uploads/delete", json.dumps({"kind": "movies", "key": "my-movies/Grandma 80th birthday.mp4"}).encode(),
                  {"Content-Type": "application/json", "X-Kit-Upload": "1"})[0] == 403, "a phone can't remove a video")
        remote["on"] = False
        st, d, _ = req("POST", "/uploads/delete", json.dumps({"kind": "movies", "key": "my-movies/Grandma 80th birthday.mp4"}).encode(),
                       {"Content-Type": "application/json", "X-Kit-Upload": "1"})
        check(st == 200 and not [m for c in d["categories"] for m in c["movies"] if m.get("key") == "my-movies/Grandma 80th birthday.mp4"]
              and any(f.endswith("Grandma 80th birthday.mp4") for f in os.listdir(os.path.join(movies, ".trash"))),
              "this computer removes a video into movies/.trash")
    finally:
        srv.shutdown()
        shutil.rmtree(kit, ignore_errors=True)


if __name__ == "__main__":
    main()
    print(f"\n{'ALL PASSED' if not FAILS else str(len(FAILS)) + ' FAILED'}")
    sys.exit(1 if FAILS else 0)
