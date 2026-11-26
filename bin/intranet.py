#!/usr/bin/env python3
"""intranet: one home page for the whole offline prepper kit, plus the servers it links to (v1.15.0).

Usage: intranet.py [port] [--open]   (default 8000). Ctrl+C (or closing the window) stops everything it started.
Runs on macOS and Windows; the launchers on the drive ("Start Prepper Kit (Mac).command" / "(Windows).bat")
start it with the kit's own portable Python and pass --open to open the browser when everything is ready.

Serves home/hub.html at /, the PDF guides at /guides/, a guide list at /guides.json and
service status at /status.json. /bible is the Bible search page (home/bible.html + /kjv.json,
built by bible/build-bible.sh); /bible-info.json names the library's Bible file for "open in library" links.
Starts the library (kiwix-serve, port 8080) and the maps (serve-maps.py, port 8090, which starts
the directions router) unless they are already running. If another program uses one of those ports, the
service moves to the next free one (8081..., 8091...); /ports.json tells the pages (nav.js) where everything is.
Optional modules (bin/catalog.py): /books, /movies (+ /movies/add, how to add your own), /software pages with
/books.json, /movies.json, /software.json; their files are served from /files/<books|audiobooks|movies|software>/
with byte ranges, so videos and audiobooks stream and seek (iPhones need that).
Your own folders: /settings (home/settings.html) lists extra movie and book folders saved in kit-settings.json. They are
scanned when the hub starts (and on Save / Rescan) and show up on the Books and Movies pages; their files are served
from /files/extra/<movies|books>/<n>/... Only this computer can change the folders (or browse its disks).
"""
import html
import http.server
import json
import os
import posixpath
import re
import signal
import socket
import sys
import threading
import time
import urllib.parse
import urllib.request
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # kitplatform (python -I leaves the script dir out)
import kitplatform  # noqa: E402
import catalog  # noqa: E402  (books, audiobooks, movies, software)
import mimetypes  # noqa: E402

VERSION = "1.15.0"  # sent in /ports.json: nav.js tells people to restart when the running hub is older than the files
KIT = kitplatform.KIT
GUIDES = os.path.join(KIT, "guides")
PORTS = {"library": 8080, "maps": 8090}
# Testing only: PREPPER_KIT_TEST_PORTS="9000,9080,9090" runs hub, library and maps on other ports.
_TEST = os.environ.get("PREPPER_KIT_TEST_PORTS", "").split(",")
if len(_TEST) == 3:
    PORTS = {"library": int(_TEST[1]), "maps": int(_TEST[2])}
DEFAULT_PORTS = dict(PORTS)
children = []


def port_up(port):
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


# How to tell that a port is really the kit's server and not some other program using it
CHECK = {"library": "/catalog/v2/root.xml", "maps": "/style/style.json"}


def is_ours(name, port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}{CHECK[name]}", timeout=3) as r:
            return r.status == 200
    except OSError:
        return False


def library_has_home_page():
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORTS['library']}/", timeout=3) as r:
            return b"Offline Library" in r.read(4000)
    except OSError:
        return True  # can't tell; don't warn


def guide_list():
    out = {}
    for root, _, files in os.walk(GUIDES):
        pdfs = sorted(f for f in files if f.lower().endswith(".pdf") and not f.startswith("._"))
        if pdfs:
            folder = os.path.relpath(root, GUIDES).replace(os.sep, "/")
            out[folder] = [{"name": f[:-4].replace("-", " "),
                            "url": "/guides/" + urllib.parse.quote(posixpath.normpath(posixpath.join(folder, f))),
                            "mb": round(os.path.getsize(os.path.join(root, f)) / 1e6, 1)} for f in pdfs]
    return dict(sorted(out.items()))


KIT_CMD = "kit.bat" if sys.platform == "win32" else "./kit.sh"  # the command on the computer running the kit
FILE_ROOTS = {"books", "audiobooks", "movies", "software", "extra"}
mimetypes.add_type("application/epub+zip", ".epub")
mimetypes.add_type("video/mp4", ".m4v")
for _ext, _type in ((".epub", "application/epub+zip"), (".m4b", "audio/mp4"), (".m4a", "audio/mp4"), (".mkv", "video/x-matroska"),
                    (".opus", "audio/ogg"), (".mobi", "application/x-mobipocket-ebook"), (".azw3", "application/vnd.amazon.ebook")):
    mimetypes.add_type(_type, _ext)

# ---- Your own folders (kit-settings.json, the Settings page) -------------------------------------------------------
FOLDERS = {k: [] for k in catalog.FOLDER_KINDS}  # kind -> [{"stored", "path", "ok", "items", "truncated"}], set by scan
SCANNED = {"at": None, "running": False}
SCAN_LOCK = threading.Lock()
MAX_FILES = 20000  # per folder: someone may point it at a whole disk


def natural(s):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", s)]


def scan_one(kind, root):
    """Movies: every video file. Books: book files (an EPUB and a PDF with the same name are one book) and audiobooks
    (a folder of audio files is one audiobook; a single audio file at the top is one too)."""
    items, n, exts = [], 0, catalog.VIDEO_EXT if kind == "movies" else catalog.BOOK_EXT + catalog.AUDIO_EXT
    books, audio, real_root = {}, {}, os.path.realpath(root)
    for d, dirs, files in os.walk(root):
        dirs[:] = sorted((x for x in dirs if not x.startswith(".") and x not in ("$RECYCLE.BIN", "System Volume Information")),
                         key=natural)
        rel_d = os.path.relpath(d, root)
        rel_d = "" if rel_d == "." else rel_d
        for f in sorted(files, key=natural):
            ext = os.path.splitext(f)[1].lower()
            if f.startswith(".") or ext not in exts:
                continue
            if os.path.islink(os.path.join(d, f)) and \
                    os.path.commonpath([real_root, os.path.realpath(os.path.join(d, f))]) != real_root:
                continue  # a shortcut to somewhere outside the folder: not served, so not listed
            n += 1
            if n > MAX_FILES:
                return items + list(books.values()) + list(audio.values()), True
            rel = os.path.join(rel_d, f)
            try:
                mb = round(os.path.getsize(os.path.join(d, f)) / 1e6, 1)
            except OSError:
                continue
            stem = os.path.splitext(f)[0].replace("_", " ")
            if kind == "movies":
                items.append({"title": stem, "rel": rel, "mb": mb, "where": rel_d})
            elif ext in catalog.AUDIO_EXT:
                key = rel_d or rel  # loose audio files at the top are one audiobook each
                a = audio.setdefault(key, {"title": os.path.basename(rel_d) if rel_d else stem, "where": os.path.dirname(rel_d),
                                           "tracks": []})
                a["tracks"].append({"name": stem, "rel": rel})
            else:
                b = books.setdefault((rel_d, stem.lower()), {"title": stem, "where": rel_d, "files": {}})
                b["files"][ext[1:]] = {"rel": rel, "mb": mb}
    return items + list(books.values()) + list(audio.values()), False


def scan_folders():
    """(Re)read kit-settings.json and look through every folder in it."""
    with SCAN_LOCK:
        SCANNED["running"] = True
        try:
            out = {}
            for kind, stored_list in catalog.load_settings()["folders"].items():
                out[kind] = []
                for stored in stored_list:
                    root = catalog.resolve_folder(stored)
                    ok = os.path.isdir(root)
                    items, cut = scan_one(kind, root) if ok else ([], False)
                    out[kind].append({"stored": stored, "path": root, "ok": ok, "items": items, "truncated": cut})
            FOLDERS.update(out)
            SCANNED["at"] = time.time()
        finally:
            SCANNED["running"] = False


def extra_url(kind, n, rel):
    return f"/files/extra/{kind}/{n}/" + urllib.parse.quote(rel.replace(os.sep, "/"))


def settings_json(local):
    folders = {k: [{"stored": f["stored"], "path": f["path"], "ok": f["ok"], "truncated": f["truncated"],
                    "count": len(f["items"]),
                    "audiobooks": sum(1 for i in f["items"] if "tracks" in i)} for f in FOLDERS[k]]
               for k in catalog.FOLDER_KINDS}
    return {"local": local, "kinds": catalog.FOLDER_KINDS, "folders": folders, "file": catalog.SETTINGS_FILE,
            "scanned": SCANNED["at"], "scanning": SCANNED["running"], "max_files": MAX_FILES,
            "windows": sys.platform == "win32"}


def browse_json(path):
    """Folders on this computer, for the Settings page's folder picker (this computer only)."""
    roots = []
    if sys.platform == "win32":
        roots = [f"{c}:\\" for c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ" if os.path.exists(f"{c}:\\")]
    else:
        vols = sorted(v for v in os.listdir("/Volumes") if not v.startswith(".")) if os.path.isdir("/Volumes") else []
        roots = [os.path.expanduser("~")] + [os.path.join("/Volumes", v) for v in vols] + ["/"]
    path = os.path.abspath(os.path.expanduser(path)) if path else os.path.expanduser("~")
    try:
        dirs = sorted((e.name for e in os.scandir(path) if e.is_dir() and not e.name.startswith((".", "$"))), key=natural)
        err = None
    except OSError as e:
        dirs, err = [], e.strerror or str(e)
    parent = os.path.dirname(path)
    return {"path": path, "parent": parent if parent != path else None, "dirs": dirs, "roots": roots, "error": err,
            "sep": os.sep}


def file_url(path):
    return "/files/" + urllib.parse.quote(os.path.relpath(path, KIT).replace(os.sep, "/"))


def books_json():
    cats = []
    for cid, (name, group) in catalog.CATEGORIES.items():
        items = []
        for b in (b for b in catalog.BOOKS if b["cat"] == cid):
            have = catalog.book_status(b)
            got = {}
            for fmt, p in have.items():
                if fmt == "audio":
                    try:
                        with open(os.path.join(catalog.audio_dir(b), catalog.TRACKS), encoding="utf-8") as f:
                            titles = json.load(f)
                    except (OSError, ValueError):
                        titles = {}
                    got["audio"] = [{"name": titles.get(os.path.basename(t)) or
                                     os.path.splitext(os.path.basename(t))[0].replace("_", " "), "url": file_url(t)}
                                    for t in p]
                elif fmt == "library":
                    got["library"] = p
                elif os.path.isdir(p):  # one PDF per chapter
                    got[fmt] = [{"name": f[:-4], "url": file_url(os.path.join(p, f))} for f in catalog.visible(p)
                                if f.lower().endswith(".pdf")]
                else:
                    got[fmt] = {"url": file_url(p), "mb": round(os.path.getsize(p) / 1e6, 1)}
            items.append({k: b.get(k) for k in ("id", "title", "author", "license")} |
                         {"formats": catalog.formats_of(b), "audiobook": bool(b.get("librivox")), "have": got})
        cats.append({"id": cid, "name": name, "group": group, "books": items})
    for n, f in enumerate(FOLDERS["books"]):  # your own folders (Settings page)
        items = []
        for i, it in enumerate(f["items"]):
            have = {}
            if "tracks" in it:
                have["audio"] = [{"name": t["name"], "url": extra_url("books", n, t["rel"])} for t in it["tracks"]]
            for ext, fl in it.get("files", {}).items():
                entry = {"url": extra_url("books", n, fl["rel"]), "mb": fl["mb"], "ext": ext}
                if ext in ("epub", "pdf"):
                    have[ext] = entry
                else:
                    have.setdefault("other", []).append(entry)
            items.append({"id": f"x{n}-{i}", "title": it["title"], "author": "", "license": it["where"] or "",
                          "formats": [], "audiobook": "tracks" in it, "have": have, "extra": True})
        cats.append({"id": f"folder-{n}", "name": os.path.basename(f["path"].rstrip("\\/")) or f["path"], "group": "yours",
                     "books": items, "folder": f["path"], "found": f["ok"]})
    return {"cmd": KIT_CMD, "categories": cats}


def movies_json():
    movies, known = catalog.all_movies(), set()
    out = {c: [] for c in catalog.MOVIE_CATEGORIES}
    for m in movies:
        p = catalog.movie_file(m)
        known.add(os.path.normcase(os.path.abspath(p)))
        have = os.path.isfile(p)
        out.setdefault(m["cat"], []).append(
            {k: m.get(k) for k in ("id", "title", "year", "minutes", "license", "ia")} |
            {"url": file_url(p) if have else None, "mb": round(os.path.getsize(p) / 1e6) if have else None})
    for root, dirs, files in os.walk(catalog.MOVIES_DIR):  # videos dropped in by hand
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for f in sorted(files):
            p = os.path.join(root, f)
            if f.startswith(".") or not f.lower().endswith(catalog.VIDEO_EXT) or \
                    os.path.normcase(os.path.abspath(p)) in known:
                continue
            cat = os.path.relpath(root, catalog.MOVIES_DIR).split(os.sep)[0]
            cat = cat if cat in catalog.MOVIE_CATEGORIES else "my-movies"
            out.setdefault(cat, []).append({"id": None, "title": os.path.splitext(f)[0].replace("_", " "), "year": None,
                                            "minutes": None, "license": "added by you", "url": file_url(p),
                                            "mb": round(os.path.getsize(p) / 1e6)})
    cats = [{"id": c, "name": catalog.MOVIE_CATEGORIES.get(c, c), "movies": out[c]} for c in out if out[c]]
    for n, f in enumerate(FOLDERS["movies"]):  # your own folders (Settings page)
        cats.append({"id": f"folder-{n}", "name": os.path.basename(f["path"].rstrip("\\/")) or f["path"], "folder": f["path"],
                     "found": f["ok"], "extra": True,
                     "movies": [{"id": None, "title": m["title"], "year": None, "minutes": None,
                                 "license": m["where"] or "", "url": extra_url("movies", n, m["rel"]),
                                 "mb": round(m["mb"])} for m in f["items"]]})
    return {"cmd": KIT_CMD, "folder": catalog.MOVIES_DIR, "categories": cats}


def software_json():
    oses = {}
    for o, name in catalog.OS_NAMES.items():
        apps = []
        for app in catalog.SOFTWARE:
            entry = app["os"].get(o)
            try:
                with open(os.path.join(catalog.SOFTWARE_DIR, o, app["id"], catalog.CHECKSUMS), encoding="utf-8") as fh:
                    sums = json.load(fh)
            except (OSError, ValueError):
                sums = {}
            files = []
            for f in catalog.software_files(app, o):
                info = sums.get(os.path.basename(f), {})
                file_day = time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(f)))
                checked = info.get("checked") or file_day  # last time it was confirmed the newest release
                age = int((time.time() - time.mktime(time.strptime(checked, "%Y-%m-%d"))) // 86400)
                files.append({"name": os.path.basename(f), "url": file_url(f), "mb": round(os.path.getsize(f) / 1e6, 1),
                              "sha256": info.get("sha256"), "verified": info.get("verified_by"),
                              "downloaded": info.get("downloaded") or file_day, "checked": checked, "age_days": age,
                              "stale": age > catalog.STALE_DAYS})
            apps.append({k: app[k] for k in ("id", "name", "about", "license")} |
                        {"files": files, "note": entry if isinstance(entry, str) else None,
                         "variants": [] if isinstance(entry, str) else [label for label, _ in entry]})
        oses[o] = {"name": name, "apps": apps}
    return {"cmd": KIT_CMD, "os": oses, "stale_days": catalog.STALE_DAYS}


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=KIT, **kw)

    def do_GET(self):
        path = urllib.parse.unquote(self.path.split("?", 1)[0])
        if path == "/ports.json":  # read by nav.js on every page (library and map are other origins)
            return self.send_json({"hub": self.server.server_address[1], **PORTS, "version": VERSION}, cors=True)
        if path == "/status.json":
            return self.send_json({n: port_up(p) and is_ours(n, p) for n, p in PORTS.items()})
        if path == "/guides.json":
            return self.send_json(guide_list())
        if path in ("/bible", "/bible/"):
            self.path = "/home/bible.html"
            return super().do_GET()
        if path == "/nav.js":  # header bar shared by every page of the kit
            self.path = "/home/nav.js"
            return super().do_GET()
        if path == "/kjv.json":
            self.path = "/home/kjv.json"
            return super().do_GET()
        if path == "/settings.json":
            return self.send_json(settings_json(self.is_local()))
        if path == "/settings/browse.json":
            if not self.is_local():
                return self.send_error_json(403, "Folders can only be chosen on the computer that runs the kit.")
            q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
            return self.send_json(browse_json(q.get("path", [""])[0]))
        pages = {"/books": "books.html", "/movies": "movies.html", "/movies/add": "movies-add.html",
                 "/software": "software.html", "/settings": "settings.html", "/media.css": "media.css", "/media.js": "media.js"}
        if path.rstrip("/") in pages:
            self.path = "/home/" + pages[path.rstrip("/")]
            return super().do_GET()
        if path in ("/books.json", "/movies.json", "/software.json"):
            return self.send_json({"/books.json": books_json, "/movies.json": movies_json,
                                   "/software.json": software_json}[path]())
        if path.startswith("/files/"):
            return self.send_file(path[len("/files/"):])
        if path == "/bible-info.json":
            zims = [f[:-4] for f in kitplatform.visible_files(os.path.join(KIT, "kiwix"), ".zim") if f.startswith("bible_")]
            return self.send_json({"zim": zims[-1] if zims else None})
        if path in ("/", "/index.html"):
            self.path = "/home/hub.html"
        elif not path.startswith("/guides/") or ".." in path:
            return self.not_found()
        return super().do_GET()

    def not_found(self):
        """A readable page instead of Python's bare "Error response 404"."""
        body = (f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Page Not Found</title>
<link rel="stylesheet" href="/media.css"></head><body><script src="/nav.js"></script><div class="wrap">
<h1>Page not found</h1><p class="sub">There is nothing at <code>{html.escape(urllib.parse.unquote(self.path))}</code> on this kit.</p>
<p><a class="btn primary" href="/">⌂ Go to the Home page</a></p>
<p class="tips">If you just updated the kit, close its window (or press Ctrl+C) and start it again: the kit that is
running may be an older version that doesn't have this page yet.</p>
<footer>Offline prepper kit v{VERSION}</footer></div></body></html>""").encode()
        self.send_response(404)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def send_file(self, rel):
        """A file from books/, audiobooks/, movies/ or software/, with Range support (video seeking, iOS)."""
        parts = rel.split("/")
        if parts[0] not in FILE_ROOTS or any(p in ("", ".", "..") or p.startswith(".") for p in parts):
            return self.not_found()
        if parts[0] == "extra":  # /files/extra/<kind>/<n>/<path inside that folder>
            try:
                root = FOLDERS[parts[1]][int(parts[2])]["path"]
            except (KeyError, IndexError, ValueError):
                return self.not_found()
            path = os.path.join(root, *parts[3:])
            real_root, real = os.path.realpath(root), os.path.realpath(path)
            exts = catalog.VIDEO_EXT if parts[1] == "movies" else catalog.BOOK_EXT + catalog.AUDIO_EXT
            if len(parts) < 4 or os.path.commonpath([real_root, real]) != real_root or \
                    not parts[-1].lower().endswith(exts):  # only the files the pages list, nothing else in there
                return self.not_found()
        else:
            path = os.path.join(KIT, *parts)
        if not os.path.isfile(path):
            return self.not_found()
        size = os.path.getsize(path)
        start, end = 0, size - 1
        rng = self.headers.get("Range", "")
        m = re.match(r"bytes=(\d*)-(\d*)$", rng.strip())
        if m and (m.group(1) or m.group(2)):
            if m.group(1):
                start = int(m.group(1))
                end = min(int(m.group(2)), size - 1) if m.group(2) else size - 1
            else:  # last N bytes
                start = max(size - int(m.group(2)), 0)
            if start > end or start >= size:
                self.send_response(416)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
                return
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        else:
            self.send_response(200)
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if parts[0] == "software" or "download" in self.path.partition("?")[2]:  # ?download: save, don't play
            name = urllib.parse.quote(parts[-1])
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{name}")
        self.end_headers()
        if self.command == "HEAD":
            return
        try:
            with open(path, "rb") as f:
                f.seek(start)
                left = end - start + 1
                while left > 0:
                    chunk = f.read(min(1 << 20, left))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    left -= len(chunk)
        except (ConnectionResetError, BrokenPipeError):
            pass  # the player jumped elsewhere or the page closed

    def do_HEAD(self):
        path = urllib.parse.unquote(self.path.split("?", 1)[0])
        if path.startswith("/files/"):
            return self.send_file(path[len("/files/"):])
        return super().do_HEAD()

    def is_local(self):
        """True for the computer running the kit (where the folders live), never for phones on the Wi-Fi."""
        ip = self.client_address[0]
        if ip.startswith("::ffff:"):
            ip = ip[7:]
        return ip.startswith("127.") or ip == "::1" or ip == lan_ip()

    def do_POST(self):
        path = urllib.parse.unquote(self.path.split("?", 1)[0])
        if path not in ("/settings.json", "/settings/rescan"):
            return self.not_found()
        origin = urllib.parse.urlsplit(self.headers.get("Origin") or "")
        if origin.netloc and ((origin.port or 80) != self.server.server_address[1] or
                              origin.hostname not in ("localhost", "127.0.0.1", "::1", lan_ip())):
            return self.send_error_json(403, "Changes must come from the kit's own Settings page.")
        if path == "/settings/rescan":  # harmless: anyone may ask for a fresh look through the folders
            scan_folders()
            return self.send_json(settings_json(self.is_local()))
        if not self.is_local():
            return self.send_error_json(403, "Folders can only be changed on the computer that runs the kit.")
        if not (self.headers.get("Content-Type") or "").startswith("application/json"):
            return self.send_error_json(415, "Send JSON.")
        try:
            body = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length") or 0), 1 << 20)) or b"{}")
            wanted = body["folders"]
            assert isinstance(wanted, dict)
        except (ValueError, KeyError, AssertionError, TypeError):
            return self.send_error_json(400, "Bad request.")
        s = catalog.load_settings()
        new = {}
        for kind in catalog.FOLDER_KINDS:
            new[kind], seen = [], set()
            for p in wanted.get(kind, []):
                if not isinstance(p, str) or not p.strip():
                    continue
                p = p.strip().strip('"')
                if p in s["folders"][kind]:  # already saved: keep it even if its drive is unplugged now
                    stored = p
                else:
                    full = os.path.abspath(os.path.expanduser(p))
                    if not os.path.isdir(full):
                        return self.send_error_json(400, f"Folder not found: {p}")
                    stored = catalog.store_folder(full)
                key = os.path.normcase(catalog.resolve_folder(stored))
                if key not in seen:
                    seen.add(key)
                    new[kind].append(stored)
        s["folders"] = new
        try:
            catalog.save_settings(s)
        except OSError as e:
            return self.send_error_json(500, f"Could not save {catalog.SETTINGS_FILE}: {e.strerror or e}")
        scan_folders()
        return self.send_json(settings_json(True))

    def send_error_json(self, code, message):
        body = json.dumps({"error": message}).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, obj, cors=False):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        if cors:
            self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


def lan_ip():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("192.168.0.1", 9))  # no packet is sent; just picks the Wi-Fi interface
            return s.getsockname()[0]
        except OSError:
            return None


def pick_port(name, preferred):
    """(port, already_running): the kit's server if it is already up on preferred..preferred+9,
    else the first free port there. Other programs (e.g. Wondershare's helper on 8090) are stepped over."""
    free = None
    for port in range(preferred, preferred + 10):
        if port_up(port):
            if is_ours(name, port):
                return port, True
        elif free is None:
            free = port
    return free, False


def start_services():
    for name, preferred in list(PORTS.items()):
        svc_port, running = pick_port(name, preferred)
        if svc_port is None:
            print(f"  {name}: NOT started: ports {preferred}-{preferred + 9} are all used by other programs.")
            continue
        if svc_port != preferred:
            print(f"  {name}: port {preferred} is used by another program, using port {svc_port} instead")
        PORTS[name] = svc_port
        if running:
            print(f"  {name}: already running")
            if name == "library" and not library_has_home_page():
                print("  WARNING: that library server is an old one without the search home page.\n"
                      "  Stop it (Ctrl+C in its window) and start the kit again.")
            continue
        if name == "library":
            cmd, env = kitplatform.library_command(svc_port)
            if not cmd:
                print(f"  library: not started ({env})")
                continue
            children.append(kitplatform.start_quietly(cmd, env=env))
        else:
            if not kitplatform.visible_files(os.path.join(KIT, "maps"), ".pmtiles"):
                print(f"  {name}: not installed (no map in maps/; build it with: kit build-map)")
                continue
            children.append(kitplatform.start_quietly(
                [sys.executable, "-I", os.path.join(KIT, "bin", "serve-maps.py"), str(svc_port)]))
        print(f"  {name}: starting")


def stop_children(*_):
    for p in children:
        kitplatform.stop(p)


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    port = int(args[0]) if args else (int(_TEST[0]) if len(_TEST) == 3 else 8000)
    try:  # take our own port first, so a second copy doesn't start servers and then fail
        server = http.server.ThreadingHTTPServer(("", port), Handler)
    except OSError:
        print(f"The kit already seems to be running (port {port} is busy). Opening it in the browser.")
        if "--open" in sys.argv:
            webbrowser.open(f"http://localhost:{port}/")
        return
    print("Starting the offline prepper kit...")
    if any(catalog.load_settings()["folders"].values()):
        print(f"  Looking through your own folders ({os.path.basename(catalog.SETTINGS_FILE)})...")
    threading.Thread(target=scan_folders, daemon=True).start()
    start_services()
    # Stop everything on: kill (SIGTERM), closing the Mac Terminal window (SIGHUP),
    # Ctrl+Break / closing the Windows console window (SIGBREAK). Ctrl+C arrives as KeyboardInterrupt.
    signal.signal(signal.SIGINT, signal.default_int_handler)  # Ctrl+C even if started with SIGINT ignored
    for name in ("SIGTERM", "SIGHUP", "SIGBREAK"):
        if hasattr(signal, name):
            signal.signal(getattr(signal, name), lambda *_: sys.exit(0))
    ip = lan_ip()
    if PORTS != DEFAULT_PORTS:
        print(f"  (library on port {PORTS['library']}, maps on port {PORTS['maps']}; the Home page links follow)")
    print(f"\nReady. Home page:\n  On this computer:        http://localhost:{port}")
    if ip:
        print(f"  On phones/other devices: http://{ip}:{port}   (same Wi-Fi network)")
    print("\nKeep this window open while you use the kit. To stop it, close this window (or press Ctrl+C).")
    if "--open" in sys.argv:
        # Give the library a moment so the home page shows "running" right away
        for _ in range(20):
            if port_up(PORTS["library"]):
                break
            time.sleep(0.5)
        webbrowser.open(f"http://localhost:{port}/")
    try:
        server.serve_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        print("\nStopping...")
        stop_children()


if __name__ == "__main__":
    main()
