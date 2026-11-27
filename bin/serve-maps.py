#!/usr/bin/env python3
"""serve-maps: serve the offline map viewer + .pmtiles over the local network (v1.17.1).

Usage: serve-maps.py [port]   (default 8090)
Serves ../map-viewer/ at /, and ../maps/*.pmtiles at /tiles/. Supports HTTP Range requests,
which the PMTiles format needs (Python's built-in http.server does not).
Also forwards /route and /info to the offline directions server (GraphHopper on 127.0.0.1:8989, or the next
free port up to 8999 if another program has 8989),
so phones only need this one port. If routing/graph-us exists, the router is started automatically
(routing/start-router.sh) and stopped on Ctrl+C. `serve-maps.py 8090 --no-router` skips it.
"""
import atexit
import http.server
import os
import re
import signal
import socket
import subprocess
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # kitplatform (python -I leaves the script dir out)
import kitplatform  # noqa: E402

KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VIEWER = os.path.join(KIT, "map-viewer")
TILES = os.path.join(KIT, "maps")
ROUTER_PORTS = range(8989, 9000)  # GraphHopper's own port (config.yml) and fallbacks
ROUTER = "http://127.0.0.1:8989"
ROUTING = os.path.join(KIT, "routing")
router_proc = None


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **kw):
        super().__init__(*a, directory=VIEWER, **kw)

    def do_GET(self):
        clean = self.path.split("?", 1)[0]
        if clean in ("/route", "/info"):
            return self.proxy_router()
        return super().do_GET()

    def proxy_router(self):
        # 180 s: from a slow USB stick the first long route reads a lot of the 8.5 GB graph (measured 18-36 s
        # idle, over 60 s while the drive was busy). Later routes over the same roads are instant (cached).
        try:
            with urllib.request.urlopen(ROUTER + self.path, timeout=180) as r:
                status, body = r.status, r.read()
        except urllib.error.HTTPError as e:  # GraphHopper's own errors (e.g. point not near a road)
            status, body = e.code, e.read()
        except OSError as e:
            status = 503
            timed_out = isinstance(e, TimeoutError) or isinstance(getattr(e, "reason", None), TimeoutError)
            if timed_out:
                body = b'{"message":"This route took too long (the drive may be slow or busy). Try again: it is faster the second time."}'
            elif router_proc and router_proc.poll() is None:
                body = b'{"message":"Directions are still loading (up to a few minutes after start from a USB drive). Try again shortly."}'
            else:
                body = b'{"message":"Directions are not running. Close the Prepper Kit window and start it again."}'
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def translate_path(self, path):
        clean = path.split("?", 1)[0].split("#", 1)[0]
        if clean == "/nav.js":  # the kit's header bar (home/nav.js), shared with the hub and library
            return os.path.join(KIT, "home", "nav.js")
        if clean.startswith("/tiles/"):
            name = os.path.basename(clean)
            return os.path.join(TILES, name)
        return super().translate_path(path)

    def guess_type(self, path):
        if path.endswith(".pbf"):
            return "application/x-protobuf"
        if path.endswith(".pmtiles"):
            return "application/octet-stream"
        return super().guess_type(path)

    def send_head(self):
        rng = self.headers.get("Range")
        path = self.translate_path(self.path)
        if not rng or not os.path.isfile(path):
            return super().send_head()
        m = re.match(r"bytes=(\d*)-(\d*)$", rng.strip())
        size = os.path.getsize(path)
        if not m:
            self.send_error(416)
            return None
        start, end = m.group(1), m.group(2)
        if start == "":  # suffix range: last N bytes
            start, end = max(0, size - int(end)), size - 1
        else:
            start, end = int(start), (int(end) if end else size - 1)
        end = min(end, size - 1)
        if start > end:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{size}")
            self.end_headers()
            return None
        f = open(path, "rb")
        f.seek(start)
        self.send_response(206)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(end - start + 1))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()
        self._remaining = end - start + 1
        return f

    def copyfile(self, source, outputfile):
        remaining = getattr(self, "_remaining", None)
        if remaining is None:
            return super().copyfile(source, outputfile)
        while remaining > 0:
            chunk = source.read(min(65536, remaining))
            if not chunk:
                break
            outputfile.write(chunk)
            remaining -= len(chunk)
        self._remaining = None

    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def log_message(self, *a):
        pass  # quiet


def port_open(port):
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.5):
            return True
    except OSError:
        return False


def graphhopper_on(port):
    """True if GraphHopper (not some other program) answers on this port."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/info", timeout=3) as r:
            return b'"bbox"' in r.read(20000)
    except (OSError, ValueError):
        return False


def start_router():
    """Start GraphHopper in the background if there is a graph and it is not already running."""
    global router_proc
    if not os.path.isfile(os.path.join(ROUTING, "graph-us", "properties")):
        return "off (no routing graph yet: run routing/build-routing.sh)"
    global ROUTER
    if graphhopper_on(8989):
        return "already running"
    java = kitplatform.find_java()
    if not java:
        return "off (Java not found)"
    free = [p for p in ROUTER_PORTS if not port_open(p)]
    if len(free) < 2:
        return "off (ports 8989-8999 are all in use by other programs)"
    app, admin = free[0], free[1]  # GraphHopper also opens an admin port (config.yml: 8990)
    ROUTER = f"http://127.0.0.1:{app}"
    moved = "" if app == 8989 else f" on port {app} (another program has 8989)"
    # Same as routing/start-router.sh, without needing bash (Windows). MMAP: the 8.5 GB graph is read
    # from disk on demand, so the router needs little RAM.
    cmd = [java, "-Xmx3g", "-Ddw.graphhopper.graph.dataaccess.default_type=MMAP",
           f"-Ddw.server.application_connectors[0].port={app}", f"-Ddw.server.admin_connectors[0].port={admin}",
           "-jar", "graphhopper-web-11.1.jar", "server", "config.yml"]
    os.makedirs(os.path.join(ROUTING, "logs"), exist_ok=True)
    router_proc = kitplatform.start_quietly(cmd, cwd=ROUTING, log=os.path.join(ROUTING, "router.log"))
    atexit.register(stop_router)
    return f"starting{moved} (ready in a few seconds)"


def stop_router():
    if router_proc and router_proc.poll() is None:
        router_proc.terminate()
        try:
            router_proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            router_proc.kill()


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))  # no packets sent; picks the LAN interface
        return s.getsockname()[0]
    except OSError:
        return "<this-mac-ip>"


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    port = int(args[0]) if args else 8090
    tiles = kitplatform.visible_files(TILES, ".pmtiles")
    if not tiles:
        sys.exit(f"No .pmtiles map in {TILES} yet")
    # Planetiler creates a tiny placeholder file at the start of a build and fills it at the end
    if all(os.path.getsize(os.path.join(TILES, f)) < 1_000_000 for f in tiles):
        sys.exit("The map is still being built (or the build failed). Try again when it finishes.")
    try:
        server = http.server.ThreadingHTTPServer(("", port), Handler)
    except OSError:
        sys.exit(f"Port {port} is already in use (is startmaps already running?). Try: startmaps {port + 1}")
    print(f"Serving offline maps ({', '.join(tiles)})")
    # Closing the Terminal window (SIGHUP) or `kill` (SIGTERM) should also stop the router
    for sig in (signal.SIGTERM, getattr(signal, "SIGHUP", None), getattr(signal, "SIGBREAK", None)):
        if sig is None:
            continue
        signal.signal(sig, lambda *_: sys.exit(0))
    if "--no-router" not in sys.argv:
        print(f"  Directions: {start_router()}")
    print(f"  On this Mac:             http://localhost:{port}")
    print(f"  On phones/other devices: http://{lan_ip()}:{port}   (same Wi-Fi network)")
    print("Ctrl+C to stop.")
    try:
        server.serve_forever()
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        stop_router()
