#!/usr/bin/env python3
"""intranet: one home page for the whole offline prepper kit, plus the servers it links to (v1.13.0).

Usage: intranet.py [port] [--open]   (default 8000). Ctrl+C (or closing the window) stops everything it started.
Runs on macOS and Windows; the launchers on the drive ("Start Prepper Kit (Mac).command" / "(Windows).bat")
start it with the kit's own portable Python and pass --open to open the browser when everything is ready.

Serves home/hub.html at /, the PDF guides at /guides/, a guide list at /guides.json and
service status at /status.json. /bible is the Bible search page (home/bible.html + /kjv.json,
built by bible/build-bible.sh); /bible-info.json names the library's Bible file for "open in library" links.
Starts the library (kiwix-serve, port 8080) and the maps (serve-maps.py, port 8090, which starts
the directions router) unless something is already listening on those ports.
"""
import http.server
import json
import os
import posixpath
import signal
import socket
import sys
import time
import urllib.parse
import urllib.request
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # kitplatform (python -I leaves the script dir out)
import kitplatform  # noqa: E402

KIT = kitplatform.KIT
GUIDES = os.path.join(KIT, "guides")
PORTS = {"library": 8080, "maps": 8090}
# Testing only: PREPPER_KIT_TEST_PORTS="9000,9080,9090" runs hub, library and maps on other ports
# (the header links still point at 8000/8080/8090).
_TEST = os.environ.get("PREPPER_KIT_TEST_PORTS", "").split(",")
if len(_TEST) == 3:
    PORTS = {"library": int(_TEST[1]), "maps": int(_TEST[2])}
children = []


def port_up(port):
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def library_has_home_page():
    try:
        with urllib.request.urlopen("http://127.0.0.1:8080/", timeout=3) as r:
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


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=KIT, **kw)

    def do_GET(self):
        path = urllib.parse.unquote(self.path.split("?", 1)[0])
        if path == "/status.json":
            return self.send_json({n: port_up(p) for n, p in PORTS.items()})
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
        if path == "/bible-info.json":
            zims = [f[:-4] for f in kitplatform.visible_files(os.path.join(KIT, "kiwix"), ".zim") if f.startswith("bible_")]
            return self.send_json({"zim": zims[-1] if zims else None})
        if path in ("/", "/index.html"):
            self.path = "/home/hub.html"
        elif not path.startswith("/guides/") or ".." in path:
            return self.send_error(404)
        return super().do_GET()

    def send_json(self, obj):
        body = json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
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


def start_services():
    for name, svc_port in PORTS.items():
        if port_up(svc_port):
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
