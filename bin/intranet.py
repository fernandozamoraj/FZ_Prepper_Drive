#!/usr/bin/env python3
"""intranet: one home page for the whole offline prepper kit, plus the servers it links to (v1.14.1).

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
import time
import urllib.parse
import urllib.request
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # kitplatform (python -I leaves the script dir out)
import kitplatform  # noqa: E402
import catalog  # noqa: E402  (books, audiobooks, movies, software)
import mimetypes  # noqa: E402

VERSION = "1.14.1"  # sent in /ports.json: nav.js tells people to restart when the running hub is older than the files
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
FILE_ROOTS = {"books", "audiobooks", "movies", "software"}
mimetypes.add_type("application/epub+zip", ".epub")
mimetypes.add_type("video/mp4", ".m4v")


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
    return {"cmd": KIT_CMD, "folder": catalog.MOVIES_DIR,
            "categories": [{"id": c, "name": catalog.MOVIE_CATEGORIES.get(c, c), "movies": out[c]} for c in out if out[c]]}


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
        pages = {"/books": "books.html", "/movies": "movies.html", "/movies/add": "movies-add.html",
                 "/software": "software.html", "/media.css": "media.css", "/media.js": "media.js"}
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
