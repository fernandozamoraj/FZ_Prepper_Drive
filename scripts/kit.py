#!/usr/bin/env python3
"""kit.py (offline prepper kit v1.17.0): download and rebuild everything in the kit, on macOS or Windows.

Run it through the wrappers, which also fetch a portable Python the first time if needed:
    macOS:   ./kit.sh <command> [options]
    Windows: kit.bat <command> [options]

Quick start:
    install all    everything: libraries, Bible, PDF guides, US map + directions (~160 GB)
    install wiki   the offline library (Wikipedia and the other libraries) + Bible (~140 GB);
                   just Wikipedia: install wiki --only wikipedia_en_all
    install maps   whole-US map, directions and town search (~20 GB kept, ~35 GB while building);
                   quick try with one state: install maps --state arkansas
    start          start the kit and open the Home page in the browser

Optional modules (not part of install all; pick what you want, see README "Books, audiobooks, software"):
    books          menu to choose books by category or keyword; or directly:
                   books list [words]   /   books get math nursing dracula [--audio] [--format pdf]
    software       menu to choose programs; or: software get vlc calibre [--os windows,mac,linux]
                   software update   newest versions of what you have   /   software check   what's out of date
    movies         menu to choose free films; or: movies get comedy nosferatu   /   movies add <archive.org link>
    install books | install software | install movies    all of that module (books: add --audio for audiobooks)

Single steps (each is safe to re-run; finished work is skipped and downloads resume):
    setup         programs the kit carries: portable Python/Java/kiwix-serve for Windows and Mac (runtime/),
                   Planetiler and GraphHopper jars, MapLibre, map fonts and icons
    download       content: Kiwix libraries (kiwix/*.zim) and PDF guides (guides/)
    build-map      whole-US map tiles maps/us.pmtiles (downloads build/us.osm.pbf, ~12 GB, first)
    build-routing  offline directions graph routing/graph-us/ from build/us.osm.pbf
    build-places   town search list map-viewer/places.json from build/us.osm.pbf
    build-bible    KJV Bible library kiwix/bible_en_kjv_<yyyy-mm>.zim and home/kjv.json
    build-all      build-map, build-routing, build-places, build-bible
    all            same as install all
    make-drive     copy the finished kit to a USB drive (exFAT) with the double-click launchers
    version        print the kit version
Use `<command> --help` for options.
"""
import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.parse
import zipfile

VERSION = "1.17.0"
HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(KIT, "bin"))  # kitplatform (python -I leaves script dirs out of sys.path)
import kitplatform  # noqa: E402
import catalog  # noqa: E402  (books, audiobooks, software: bin/catalog.py)

WINDOWS = sys.platform == "win32"
LOG = os.path.join(KIT, "download.log")  # serve.sh reads "OK  <file>" lines from here

# ---- Pinned versions of the programs the kit carries -------------------------------------------------
PY_RELEASE, PY_VERSION = "20261026", "3.12.16"
PY_BASE = f"https://github.com/astral-sh/python-build-standalone/releases/download/{PY_RELEASE}"
KIWIX_BASE = "https://download.kiwix.org/release/kiwix-tools"
PLATFORMS = {  # runtime/<name>: python-build-standalone triple, Adoptium os/arch, kiwix-tools build
    "win-x64": ("x86_64-pc-windows-msvc", "windows", "x64", "kiwix-tools_win-x86_64-3.8.1.zip"),
    "mac-arm64": ("aarch64-apple-darwin", "mac", "aarch64", "kiwix-tools_macos-arm64-3.8.2.tar.gz"),
    "mac-x64": ("x86_64-apple-darwin", "mac", "x64", "kiwix-tools_macos-x86_64-3.8.2.tar.gz"),
}
PLANETILER = ("https://github.com/onthegomap/planetiler/releases/download/v0.10.2/planetiler.jar", "bin/planetiler.jar")
GRAPHHOPPER = ("https://repo1.maven.org/maven2/com/graphhopper/graphhopper-web/11.1/graphhopper-web-11.1.jar",
               "routing/graphhopper-web-11.1.jar")
WEB_LIBS = [
    ("https://cdn.jsdelivr.net/npm/maplibre-gl@4.7.1/dist/maplibre-gl.js", "map-viewer/lib/maplibre-gl.js"),
    ("https://cdn.jsdelivr.net/npm/maplibre-gl@4.7.1/dist/maplibre-gl.css", "map-viewer/lib/maplibre-gl.css"),
    ("https://cdn.jsdelivr.net/npm/pmtiles@3.2.1/dist/pmtiles.js", "map-viewer/lib/pmtiles.js"),
] + [(f"https://openmaptiles.github.io/osm-bright-gl-style/{f}", f"map-viewer/style/{f}")
     for f in ("sprite.json", "sprite.png", "sprite@2x.json", "sprite@2x.png")]
FONTS_ZIP = "https://github.com/openmaptiles/fonts/releases/download/v2.0/noto-sans.zip"
FONTS = ("Noto Sans Regular", "Noto Sans Bold", "Noto Sans Italic")  # the ones style.json uses

# ---- Content ---------------------------------------------------------------------------------------
US_PBF = "https://download.geofabrik.de/north-america/us-latest.osm.pbf"
KIWIX_ZIM = "https://download.kiwix.org/zim"
# (folder, file-name prefix): the newest <prefix><yyyy-mm>.zim on download.kiwix.org is used
ZIM_SETS = {
    "core": [  # small and most important first, Wikipedia (~120 GB) last
        ("other", "zimgit-water_en_"), ("other", "zimgit-medicine_en_"), ("other", "zimgit-knots_en_"),
        ("other", "zimgit-food-preparation_en_"), ("other", "zimgit-post-disaster_en_"),
        ("other", "trueprepper.com_en_all_"), ("wikipedia", "wikipedia_en_medicine_maxi_"),
        ("ifixit", "ifixit_en_all_"), ("wikivoyage", "wikivoyage_en_all_maxi_"),
    ] + [("stack_exchange", f"{s}.stackexchange.com_en_all_") for s in (
        "outdoors", "cooking", "gardening", "diy", "electronics", "engineering", "sustainability", "ham",
        "homebrew", "medicalsciences")] + [("wikipedia", "wikipedia_en_all_maxi_")],
    "programming": [("devdocs", f"devdocs_en_{d}_") for d in (
        "python", "javascript", "html", "css", "node", "bash", "git", "sqlite", "postgresql", "lua")]
    + [("freecodecamp", "freecodecamp_en_all_"), ("wikibooks", "wikibooks_en_all_maxi_")],
}
STATES = ["texas", "new-mexico", "oklahoma", "arkansas", "louisiana", "california", "oregon", "nevada",
          "arizona", "alabama", "mississippi", "illinois", "indiana", "ohio"]
UA = "Mozilla/5.0"
KIT_UA = f"offline-prepper-kit/{VERSION} (+https://github.com/fernandozamoraj/FZ_Prepper_Drive)"  # books, software:
# an honest name (some hosts refuse the fake browser one, Gutenberg asks scripts to say who they are)
PDFS = [  # (url, topic folder, file name)
    ("https://www.sjsu.edu/people/michelle.hager/docs/fm_21-76_us_army_survival_manual_2006.pdf", "survival",
     "FM-21-76-Army-Survival-Manual.pdf"),
    ("https://rmp.nc.gov/LCF/Publications/AL_Resources/Survival/Multi%20Service%20Survival%20Manual.pdf",
     "survival", "Multi-Service-Survival-Manual.pdf"),
    ("https://archive.org/download/MManuals/UsMarineCorps-Survival-Mcrp3-02f.pdf", "survival",
     "USMC-Survival-MCRP-3-02F.pdf"),
    ("https://www.ready.gov/sites/default/files/2021-11/are-you-ready-guide.pdf", "preparedness",
     "FEMA-Are-You-Ready.pdf"),
    ("https://19january2021snapshot.epa.gov/sites/static/files/2017-09/documents/"
     "emergency_disinfection_of_drinking_water_sept2017.pdf", "water",
     "EPA-Emergency-Disinfection-of-Drinking-Water.pdf"),
    ("https://nchfp.uga.edu/papers/guide/INTRO_HomeCanrev0715.pdf", "canning", "00-Intro.pdf"),
] + [(f"https://nchfp.uga.edu/papers/guide/GUIDE0{i}_HomeCan_rev0715.pdf", "canning", f"0{i}-{name}.pdf")
     for i, name in enumerate(["Principles-of-Home-Canning", "Fruit-and-Fruit-Products", "Tomatoes", "Vegetables",
                               "Poultry-Red-Meats-Seafood", "Fermented-and-Pickled", "Jams-and-Jellies"], 1)]
HESPERIAN = "https://languages.hesperian.org/pages/en/pdf.html"
HESPERIAN_BOOKS = [("en_wtnd", "Where-There-Is-No-Doctor"), ("en_dent", "Where-There-Is-No-Dentist"),
                   ("en_midw", "Book-for-Midwives"), ("en_cgeh", "Community-Guide-to-Environmental-Health")]
BIBLE_ZIP = "https://ebible.org/Scriptures/eng-kjv2006_vpl.zip"


# ==== helpers ==========================================================================================
def say(msg, log=LOG):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(log, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def die(msg):
    say(f"ERROR: {msg}")  # also in download.log, so a stop shows there too
    sys.exit(1)


def kit_path(*parts):
    return os.path.join(KIT, *parts)


def curl():
    exe = shutil.which("curl.exe" if WINDOWS else "curl")
    if not exe:
        die("curl not found (it comes with macOS and Windows 10 or later)")
    return exe


def fetch_text(url, ua=UA):
    r = subprocess.run([curl(), "-sfL", "--connect-timeout", "30", "-m", "180", "-A", ua, url], capture_output=True)
    return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else None


def remote_size(url, ua=UA):
    # a server that never answers HEAD (a hung mirror) must not stall the download: give up after 60 s
    r = subprocess.run([curl(), "-sIL", "--connect-timeout", "30", "-m", "60", "-A", ua, url], capture_output=True)
    if r.returncode != 0:
        return None
    sizes = re.findall(rb"(?im)^content-length:\s*(\d+)", r.stdout)
    status = re.findall(rb"(?m)^HTTP/\S+\s+(\d+)", r.stdout)
    if not status or status[-1] != b"200":
        return None
    return int(sizes[-1]) if sizes else 0


def size_of(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return -1


def get(url, dest, tries=5, quiet=False, ua=UA):
    """Resumable download to dest (via dest.part). Skips a file that's already complete. Returns True if OK."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    name = os.path.basename(dest)
    remote = remote_size(url, ua)
    if os.path.exists(dest) and (remote in (None, 0) or size_of(dest) == remote):
        if not quiet:
            say(f"OK  {name} (complete)")
        return True
    part = dest + ".part"
    if remote and size_of(part) > remote:
        os.remove(part)
    for n in range(1, tries + 1):
        if remote and size_of(part) == remote:
            break
        say(f"GET {name} (try {n}, have {max(size_of(part), 0)} of {remote or '?'} bytes)")
        progress = ["--progress-bar"] if sys.stdout.isatty() else ["-sS"]
        # --speed-limit/--speed-time: a stalled connection (a hung mirror) is dropped after 60 s and resumed
        rc = subprocess.call([curl(), "-fL", "-A", ua, "--retry", "5", "--retry-delay", "10", "-C", "-",
                              "--connect-timeout", "30", "--speed-limit", "1000", "--speed-time", "60",
                              *progress, "-o", part, url])
        if rc == 0 and not remote:
            break
        if rc != 0:
            time.sleep(5)
    if os.path.exists(part) and (not remote or size_of(part) == remote):
        os.replace(part, dest)
        say(f"OK  {name} (complete, {size_of(dest) / 1e6:,.1f} MB)")
        return True
    say(f"FAIL {name} <- {url}")
    return False


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def check_sum(path, expected, algo="sha256"):
    h = hashlib.new(algo)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    if h.hexdigest().lower() != expected.lower():
        os.remove(path)
        die(f"checksum mismatch for {os.path.basename(path)} (deleted; run again)")


def extract(archive, dest):
    """Extract a .zip or .tar.gz. Symlinks become real copies (exFAT drives can't store links)."""
    os.makedirs(dest, exist_ok=True)
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as z:
            z.extractall(dest)
        return
    links = []
    with tarfile.open(archive) as t:
        members = []
        for m in t.getmembers():
            (links if m.issym() or m.islnk() else members).append(m)
        kw = {"filter": "tar"} if hasattr(tarfile, "data_filter") else {}
        t.extractall(dest, members=members, **kw)
    for m in sorted(links, key=lambda m: m.name.count("/")):
        link = os.path.join(dest, m.name)
        base = dest if m.islnk() else os.path.dirname(link)
        target = os.path.normpath(os.path.join(base, m.linkname))
        if not target.startswith(os.path.abspath(dest)) or not os.path.exists(target):
            continue
        if os.path.isdir(target):
            shutil.copytree(target, link, dirs_exist_ok=True)
        else:
            shutil.copy2(target, link)


def tidy_runtime(folder):
    """Make a runtime folder drive-ready: symlinks become real copies (exFAT can't store links), and
    debug symbols (*.pdb, ~60 MB on Windows) and __pycache__ folders are dropped."""
    for root, dirs, files in os.walk(folder, topdown=False):
        for f in files:
            p = os.path.join(root, f)
            if os.path.islink(p):
                target = os.path.realpath(p)
                os.remove(p)
                if os.path.isfile(target):
                    shutil.copy2(target, p)
            elif f.endswith(".pdb"):
                os.remove(p)
        for d in dirs:
            p = os.path.join(root, d)
            if os.path.islink(p):
                target = os.path.realpath(p)
                os.remove(p)
                if os.path.isdir(target):
                    shutil.copytree(target, p)
            elif d == "__pycache__":
                shutil.rmtree(p, ignore_errors=True)


def tmpdir():
    d = kit_path("build", "tmp-setup")
    os.makedirs(d, exist_ok=True)
    return tempfile.mkdtemp(dir=d)


def find_java_or_die():
    java = kitplatform.find_java()
    if not java:
        die("Java 21 not found. Run `setup` first (it puts a portable Java in runtime/).")
    return java


def current_platform():
    if WINDOWS:
        return "win-x64"
    if sys.platform == "darwin":
        return "mac-arm64" if platform.machine() == "arm64" else "mac-x64"
    return None


def router_running():
    """GraphHopper answering on 8989 or a fallback port (serve-maps.py moves it if another program has 8989)."""
    import urllib.request
    for port in range(8989, 9000):
        if not port_open(port):
            continue
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/info", timeout=3) as r:
                if b'"bbox"' in r.read(20000):
                    return True
        except (OSError, ValueError):
            pass
    return False


def port_open(port):
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def build_venv():
    """scripts/.venv with the Python packages the builders need (needs internet the first time)."""
    venv = kit_path("scripts", ".venv")
    py = os.path.join(venv, "Scripts", "python.exe") if WINDOWS else os.path.join(venv, "bin", "python")
    marker = os.path.join(venv, "kit-packages.txt")
    pkgs = ["shapely", "libzim", "osmium"]
    if not os.path.exists(marker):
        say(f"Creating {venv} ({', '.join(pkgs)})")
        subprocess.check_call([sys.executable, "-m", "venv", "--clear", venv])
        subprocess.check_call([py, "-m", "pip", "-q", "install", "--upgrade", "pip"])
        subprocess.check_call([py, "-m", "pip", "-q", "install", *pkgs])
        with open(marker, "w") as f:
            f.write("\n".join(pkgs) + "\n")
    return py


ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


def run(cmd, cwd=None, log=None):
    print("$ " + " ".join(f'"{c}"' if " " in c else c for c in cmd), flush=True)
    if log:  # show the program's progress in the window and keep a copy in the log
        print(f"    (this can take a long time; output is also saved to {log})", flush=True)
        with open(log, "w", encoding="utf-8", errors="replace") as f:
            p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            try:
                for raw in p.stdout:
                    line = ANSI.sub("", raw.decode("utf-8", "replace"))  # colour codes show as junk in cmd.exe
                    f.write(line)
                    f.flush()
                    sys.stdout.write("    " + line)
                    sys.stdout.flush()
            finally:
                rc = p.wait()
    else:
        rc = subprocess.call(cmd, cwd=cwd)
    if rc != 0:
        die(f"command failed (exit {rc})" + (f"; see {log}" if log else ""))


# ==== setup ============================================================================================
def setup_platform(name, force):
    triple, jos, jarch, kiwix_file = PLATFORMS[name]
    rt = kit_path("runtime", name)
    exe = ".exe" if name.startswith("win") else ""

    # Python
    py = os.path.join(rt, "python", "python.exe" if exe else "bin/python3")
    running = os.path.exists(py) and os.path.samefile(os.path.dirname(sys.executable), os.path.dirname(py))
    if os.path.exists(py) and (not force or running):
        say(f"OK  runtime/{name}/python (present)")
    else:
        tar = f"cpython-{PY_VERSION}+{PY_RELEASE}-{triple}-install_only.tar.gz"
        d = tmpdir()
        get(f"{PY_BASE}/{tar}", os.path.join(d, tar)) or die("Python download failed")
        sums = fetch_text(f"{PY_BASE}/SHA256SUMS") or ""
        m = re.search(r"(?m)^([0-9a-f]{64})\s+" + re.escape(tar) + "$", sums)
        if m:
            check_sum(os.path.join(d, tar), m.group(1))
        shutil.rmtree(os.path.join(rt, "python"), ignore_errors=True)
        extract(os.path.join(d, tar), rt)  # archive holds python/
        shutil.rmtree(d, ignore_errors=True)
        say(f"OK  runtime/{name}/python (Python {PY_VERSION})")

    # Java (Temurin JRE 21, newest build)
    java = os.path.join(rt, "java", "bin", "java" + exe)
    if os.path.exists(java) and not force:
        say(f"OK  runtime/{name}/java (present)")
    else:
        info = json.loads(fetch_text("https://api.adoptium.net/v3/assets/latest/21/hotspot?image_type=jre"
                                     f"&os={jos}&architecture={jarch}&vendor=eclipse") or "[]")
        pkg = next((a["binary"]["package"] for a in info if a["binary"].get("image_type") == "jre"), None)
        pkg or die(f"no Temurin JRE 21 found for {jos}/{jarch}")
        d = tmpdir()
        arc = os.path.join(d, pkg["name"])
        get(pkg["link"], arc) or die("Java download failed")
        check_sum(arc, pkg["checksum"])
        extract(arc, os.path.join(d, "x"))
        home = next((root for root, _, files in os.walk(os.path.join(d, "x"))
                     if os.path.basename(root) == "bin" and ("java" + exe) in files), None)
        home or die("java not found in the Temurin archive")
        shutil.rmtree(os.path.join(rt, "java"), ignore_errors=True)
        shutil.move(os.path.dirname(home), os.path.join(rt, "java"))
        shutil.rmtree(d, ignore_errors=True)
        say(f"OK  runtime/{name}/java ({pkg['name']})")

    # kiwix-serve
    serve = os.path.join(rt, "kiwix", "kiwix-serve" + exe)
    if os.path.exists(serve) and not force:
        say(f"OK  runtime/{name}/kiwix (present)")
    else:
        d = tmpdir()
        arc = os.path.join(d, kiwix_file)
        get(f"{KIWIX_BASE}/{kiwix_file}", arc) or die("kiwix-tools download failed")
        md5 = fetch_text(f"{KIWIX_BASE}/{kiwix_file}.md5")
        if md5:
            check_sum(arc, md5.split()[0], "md5")
        extract(arc, os.path.join(d, "x"))
        out = os.path.join(rt, "kiwix")
        shutil.rmtree(out, ignore_errors=True)
        os.makedirs(out)
        for root, _, files in os.walk(os.path.join(d, "x")):
            for f in files:  # Windows: kiwix-serve.exe + its DLLs. Mac: kiwix-serve only.
                if f == "kiwix-serve" + exe or (exe and f.lower().endswith(".dll")):
                    shutil.copy2(os.path.join(root, f), out)
                if not exe and name == current_platform() and f in ("kiwix-serve", "kiwix-manage", "kiwix-search"):
                    shutil.copy2(os.path.join(root, f), kit_path("bin", f))  # serve.sh uses bin/kiwix-serve
        shutil.rmtree(d, ignore_errors=True)
        say(f"OK  runtime/{name}/kiwix ({kiwix_file})")
    tidy_runtime(rt)


def cmd_setup(a):
    names = list(PLATFORMS) if a.platform == "all" else (
        [current_platform()] if a.platform == "current" else a.platform.split(","))
    for n in names:
        n in PLATFORMS or die(f"unknown platform {n!r} (use {', '.join(PLATFORMS)}, current or all)")
    say(f"=== setup v{VERSION}: programs for {', '.join(names)} ===")
    for n in names:
        setup_platform(n, a.force)
    for url, rel in [PLANETILER, GRAPHHOPPER] + WEB_LIBS:
        if a.force and os.path.exists(kit_path(rel)):
            os.remove(kit_path(rel))
        get(url, kit_path(*rel.split("/"))) or die(f"download failed: {url}")
    sha1 = fetch_text(GRAPHHOPPER[0] + ".sha1")
    if sha1:
        check_sum(kit_path(*GRAPHHOPPER[1].split("/")), sha1.split()[0], "sha1")
    fonts = kit_path("map-viewer", "fonts")
    if all(os.path.isdir(os.path.join(fonts, f)) for f in FONTS) and not a.force:
        say("OK  map-viewer/fonts (present)")
    else:
        d = tmpdir()
        get(FONTS_ZIP, os.path.join(d, "noto-sans.zip")) or die("font download failed")
        with zipfile.ZipFile(os.path.join(d, "noto-sans.zip")) as z:
            for m in z.namelist():
                parts = m.split("/")
                for i, p in enumerate(parts[:-1]):
                    if p in FONTS and parts[-1].endswith(".pbf"):
                        target = os.path.join(fonts, p, parts[-1])
                        os.makedirs(os.path.dirname(target), exist_ok=True)
                        with z.open(m) as src, open(target, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        break
        shutil.rmtree(d, ignore_errors=True)
        missing = [f for f in FONTS if not os.path.isdir(os.path.join(fonts, f))]
        missing and die(f"fonts missing from {FONTS_ZIP}: {missing}")
        say("OK  map-viewer/fonts (Noto Sans)")
    shutil.rmtree(kit_path("build", "tmp-setup"), ignore_errors=True)
    say("=== setup done ===")


# ==== download =========================================================================================
def newest_zim(folder, prefix):
    listing = fetch_text(f"{KIWIX_ZIM}/{folder}/") or ""
    names = set(re.findall(r'href="(' + re.escape(prefix) + r'\d{4}-\d{2}\.zim)"', listing))
    return max(names) if names else None


def local_zims(prefix):
    pat = re.compile(re.escape(prefix) + r"\d{4}-\d{2}\.zim$")
    return sorted(f for f in kitplatform.visible_files(kit_path("kiwix"), ".zim") if pat.match(f))


def download_zim(folder, prefix, update):
    have = local_zims(prefix)
    if have and not update:  # keep the edition you have; --update fetches a newer one next to it
        name = have[-1]
        if remote_size(f"{KIWIX_ZIM}/{folder}/{name}") is None:
            say(f"OK  {name} (kept; no longer on the server)")
            return True
        return get(f"{KIWIX_ZIM}/{folder}/{name}", kit_path("kiwix", name))
    name = newest_zim(folder, prefix)
    if not name:
        say(f"FAIL no {prefix}<date>.zim in {KIWIX_ZIM}/{folder}/")
        return False
    return get(f"{KIWIX_ZIM}/{folder}/{name}", kit_path("kiwix", name))


def download_pdf(url, topic, name):
    dest = kit_path("guides", *topic.split("/"), name)
    if size_of(dest) > 0:
        with open(dest, "rb") as f:
            if f.read(5).startswith(b"%PDF"):
                return True
    if get(url, dest, tries=2, quiet=True):
        with open(dest, "rb") as f:
            if f.read(5).startswith(b"%PDF"):
                return True
        os.remove(dest)
        say(f"FAIL {topic}/{name} (not a PDF) <- {url}")
    return False


def cmd_download(a):
    sets = ["core", "programming", "pdfs"] if a.set == "all" else a.set.split(",")
    say(f"=== download v{VERSION}: {', '.join(sets)} ===")
    fails = 0
    for s in sets:
        if s in ZIM_SETS:
            for folder, prefix in ZIM_SETS[s]:
                if a.only and a.only not in prefix:
                    continue
                fails += not download_zim(folder, prefix, a.update)
        elif s == "pdfs":
            for url, topic, name in PDFS:
                if not a.only or a.only in name:
                    fails += not download_pdf(url, topic, name)
            page = fetch_text(HESPERIAN) or ""
            links = re.findall(r'href="([^"]+\.pdf)"', page)
            for key, book in HESPERIAN_BOOKS:
                urls = [u for u in links if f"/pdf/{key}_" in u]
                if not urls:
                    say(f"FAIL no chapters found for {key} on {HESPERIAN}")
                    fails += 1
                for n, u in enumerate(urls, 1):
                    name = f"{n:02d}-{os.path.basename(u)}"
                    if not a.only or a.only in name:
                        fails += not download_pdf(u, f"medical/{book}", name)
        elif s == "states":  # optional state extracts (only for quick tests and regional maps)
            for st in STATES:
                if not a.only or a.only in st:
                    fails += not get(f"https://download.geofabrik.de/north-america/us/{st}-latest.osm.pbf",
                                     kit_path("maps", f"{st}-latest.osm.pbf"))
        else:
            die(f"unknown set {s!r} (core, programming, pdfs, states, all)")
    say(f"=== download done, {fails} failed ===")
    return fails


def cmd_download_cli(a):
    if cmd_download(a):
        say("Some downloads failed (see FAIL lines above). Run the same command again to retry them.")
        sys.exit(2)


# ==== builds ===========================================================================================
def us_pbf(a):
    if getattr(a, "pbf", None):
        os.path.exists(a.pbf) or die(f"not found: {a.pbf}")
        return os.path.abspath(a.pbf)
    pbf = kit_path("build", "us.osm.pbf")
    if os.path.exists(pbf) and not getattr(a, "refresh_osm", False):
        return pbf  # never resume onto an older extract: --refresh-osm starts a fresh download
    if os.path.exists(pbf):
        os.remove(pbf)
    get(US_PBF, pbf) or die("could not download the OpenStreetMap US extract")
    return pbf


def cmd_build_map(a):
    pbf = us_pbf(a)
    out = os.path.abspath(a.output) if a.output else kit_path("maps", "us.pmtiles")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    new = out[:-len(".pmtiles")] + ".new.pmtiles" if out.endswith(".pmtiles") else out + ".new.pmtiles"
    say(f"=== build-map: {os.path.basename(pbf)} -> {out} (Planetiler, -Xmx{a.xmx}) ===")
    os.path.exists(kit_path("bin", "planetiler.jar")) or die("bin/planetiler.jar missing: run setup")
    build = kit_path("build")
    run([find_java_or_die(), f"-Xmx{a.xmx}", "-jar", kit_path("bin", "planetiler.jar"), f"--osm-path={pbf}",
         "--storage=mmap", "--nodemap-type=array", "--download", f"--download_dir={os.path.join(build, 'sources')}",
         f"--tmpdir={os.path.join(build, 'data', 'tmp')}", f"--output={new}", "--force"],
        cwd=build, log=os.path.join(build, "planetiler.log"))
    os.replace(new, out)
    say(f"built {out} ({size_of(out) / 1e9:.1f} GB)")


def cmd_build_routing(a):
    pbf = us_pbf(a)
    routing = kit_path("routing")
    graph = os.path.abspath(a.graph) if a.graph else os.path.join(routing, "graph-us")
    jar = os.path.join(routing, "graphhopper-web-11.1.jar")
    os.path.exists(jar) or die("routing/graphhopper-web-11.1.jar missing: run setup")
    if not a.graph and router_running():
        die("the directions router is running. Stop the kit first (Ctrl+C or close its window), "
            "then run this again")
    shutil.rmtree(graph, ignore_errors=True)
    os.makedirs(os.path.join(routing, "logs"), exist_ok=True)
    say(f"=== build-routing: {os.path.basename(pbf)} -> {graph} (GraphHopper, -Xmx{a.xmx}) ===")
    run([find_java_or_die(), f"-Xmx{a.xmx}", f"-Ddw.graphhopper.datareader.file={pbf}",
         f"-Ddw.graphhopper.graph.location={graph}",
         "-Ddw.logging.appenders[0].threshold=INFO",  # show import progress in the window (config.yml: WARN)
         "-jar", jar, "import", "config.yml"],
        cwd=routing, log=os.path.join(routing, "build.log"))
    os.path.exists(os.path.join(graph, "properties")) or die("graph not built; see routing/build.log")
    say(f"built {graph}")


def cmd_build_places(a):
    pbf = us_pbf(a)
    out = os.path.abspath(a.output) if a.output else kit_path("map-viewer", "places.json")
    states = kit_path("routing", "states.geojson")
    py = build_venv()
    tmp = tempfile.mkdtemp()
    places = os.path.join(tmp, "places.geojsonseq")
    say(f"=== build-places: {os.path.basename(pbf)} -> {out} ===")
    osmium_cli = shutil.which("osmium")
    if osmium_cli and a.engine != "pyosmium":  # osmium-tool (brew install osmium-tool): fastest
        f1, f2 = os.path.join(tmp, "places.osm.pbf"), os.path.join(tmp, "states.osm.pbf")
        run([osmium_cli, "tags-filter", pbf, "n/place=city,town,village,hamlet", "-o", f1, "--overwrite"])
        run([osmium_cli, "export", f1, "-f", "geojsonseq", "-o", places, "--overwrite", "--geometry-types=point"])
        run([osmium_cli, "tags-filter", pbf, "r/admin_level=4", "-o", f2, "--overwrite"])
        run([osmium_cli, "export", f2, "-f", "geojson", "-o", states, "--overwrite", "--geometry-types=polygon"])
    else:  # pyosmium (Windows, or Macs without osmium-tool)
        run([py, os.path.join(HERE, "places_extract.py"), pbf, places, states])
    run([py, kit_path("routing", "make_places.py"), places, states, out])
    shutil.rmtree(tmp, ignore_errors=True)


def cmd_build_bible(a):
    src = kit_path("bible", "src")
    txt = os.path.join(src, "kjv2006", "eng-kjv2006_vpl.txt")
    if not os.path.exists(txt):
        z = os.path.join(src, "eng-kjv2006_vpl.zip")
        get(BIBLE_ZIP, z) or die("Bible text download failed")
        extract(z, os.path.join(src, "kjv2006"))
    py = build_venv()
    say("=== build-bible ===")
    run([py, kit_path("bible", "build-bible.py")])


def cmd_build_all(a):
    base = {"pbf": getattr(a, "pbf", None), "refresh_osm": getattr(a, "refresh_osm", False)}
    cmd_build_map(argparse.Namespace(**base, output=None, xmx="14g"))
    base["refresh_osm"] = False  # downloaded once, used by all three
    cmd_build_routing(argparse.Namespace(**base, graph=None, xmx="18g"))
    cmd_build_places(argparse.Namespace(**base, output=None, engine="auto"))
    cmd_build_bible(argparse.Namespace())


def cmd_all(a):
    cmd_install(argparse.Namespace(what="all", platform="all", only=None, state=None, words=None))


def cmd_install(a):
    """Quick-start bundles: all, wiki (library + Bible) or maps (map + directions + town search).
    Each step is named in the window and the log; if one stops, it says which and how to carry on.
    books, software and movies are the optional modules (never part of all)."""
    if a.what in ("books", "software", "movies"):
        words = getattr(a, "words", None) or ["all"]
        if a.what == "books":
            fails = books_get(catalog.pick(catalog.BOOKS, words, catalog.BOOK_FIELDS)[0], audio=a.audio)
        elif a.what == "software":
            fails = software_get(catalog.pick(catalog.SOFTWARE, words, catalog.SOFTWARE_FIELDS)[0], os_list(a.os))
        else:
            fails = movies_get(catalog.pick(catalog.all_movies(), words, catalog.MOVIE_FIELDS)[0])
        say(f"=== install {a.what} done. It shows on the Home page ({kit_cmd()} start) ===")
        if fails:
            say(f"NOTE: {fails} download(s) failed; run the same command again to retry them.")
            sys.exit(2)
        return
    plat = a.platform or ("all" if a.what == "all" else "current")
    again = f"{'kit.bat' if WINDOWS else './kit.sh'} install {a.what}" + \
        (f" --only {a.only}" if a.only else "") + (f" --state {a.state}" if a.state else "")
    steps = [("programs (setup)", lambda: cmd_setup(argparse.Namespace(platform=plat, force=False)))]
    failed_downloads = []
    if a.what in ("all", "wiki"):
        sets = "all" if a.what == "all" else "core,programming"
        steps += [("library and PDF downloads",
                   lambda: failed_downloads.append(cmd_download(argparse.Namespace(set=sets, only=a.only, update=False)))),
                  ("Bible", lambda: cmd_build_bible(argparse.Namespace()))]
    if a.what in ("all", "maps"):
        pbf = None
        if a.state:  # quick try: one state's extract instead of the 12 GB US one
            pbf = kit_path("maps", f"{a.state}-latest.osm.pbf")
            steps.append((f"{a.state} map data", lambda: get(
                f"https://download.geofabrik.de/north-america/us/{a.state}-latest.osm.pbf", pbf) or
                die(f"no OpenStreetMap extract for {a.state!r} (use names like texas, new-mexico, arkansas)")))
        base = {"pbf": pbf, "refresh_osm": False}
        steps += [("map (build-map)", lambda: cmd_build_map(argparse.Namespace(**base, output=None, xmx="14g"))),
                  ("directions (build-routing)",
                   lambda: cmd_build_routing(argparse.Namespace(**base, graph=None, xmx="18g"))),
                  ("town search (build-places)",
                   lambda: cmd_build_places(argparse.Namespace(**base, output=None, engine="auto")))]
    for n, (name, fn) in enumerate(steps, 1):
        say(f"##### install {a.what}: step {n} of {len(steps)}: {name} #####")
        try:
            fn()
        except KeyboardInterrupt:
            say(f"STOPPED (Ctrl+C) during step {n}: {name}. To carry on later, run: {again}")
            sys.exit(130)
        except SystemExit as e:
            if e.code in (0, None):
                raise
            say(f"STOPPED: step {n} ({name}) failed; the error is just above. Finished parts are kept. "
                f"Fix the problem (or just retry if the computer slept or lost internet), then run: {again}")
            raise
        except Exception:
            import traceback
            traceback.print_exc()
            say(f"STOPPED: step {n} ({name}) failed with the error above. Finished parts are kept. "
                f"Run again with: {again}")
            sys.exit(1)
    say(f"=== install {a.what} done. Start the kit with: {'kit.bat' if WINDOWS else './kit.sh'} start ===")
    if sum(failed_downloads):
        say(f"NOTE: {sum(failed_downloads)} download(s) failed (FAIL lines in download.log). "
            f"Everything else is installed; run {again} again to retry them.")


def cmd_start(a):
    """Start the hub (which starts the library and maps it finds) and open the browser."""
    cmd = [sys.executable, "-I", kit_path("bin", "intranet.py"), "--open"]
    if a.port:
        cmd.insert(3, str(a.port))
    try:
        sys.exit(subprocess.call(cmd))
    except KeyboardInterrupt:
        pass


# ==== books, audiobooks, software (optional modules) =====================================================
GUTENBERG_MIRRORS = ["https://gutenberg.pglaf.org", "https://aleph.gutenberg.org", "https://www.gutenberg.org"]
OPENSTAX_API = ("https://openstax.org/apps/cms/api/v2/pages/?type=books.Book&limit=250"
                "&fields=title,book_state,high_resolution_pdf_url,license_name,license_version")
_cache = {}


def kit_cmd():
    return "kit.bat" if WINDOWS else "./kit.sh"


def looks_like(path, fmt):
    """A real EPUB (zip) / PDF / MP3, not an error page saved under that name."""
    magic = {"epub": (b"PK",), "pdf": (b"%PDF",), "mp3": (b"ID3", b"\xff\xfb", b"\xff\xf3", b"\xff\xf2")}.get(fmt)
    if not magic:
        return True
    try:
        with open(path, "rb") as f:
            head = f.read(4)
    except OSError:
        return False
    return any(head.startswith(m) for m in magic)


def fetch_checked(url, dest, fmt, quiet=False):
    """get() plus a format check; a wrong file is deleted so the next run tries again."""
    if os.path.isfile(dest) and looks_like(dest, fmt):
        if not quiet:
            say(f"OK  {os.path.basename(dest)} (have it)")
        return True
    if not get(url, dest, tries=3, quiet=quiet, ua=KIT_UA):
        return False
    if looks_like(dest, fmt):
        return True
    os.remove(dest)
    say(f"FAIL {os.path.basename(dest)}: the server sent something that isn't a {fmt.upper()} <- {url}")
    return False


def openstax_book(slug):
    """(pdf url, title with edition, license) of the newest live edition: slug, slug-2e, slug-3e..."""
    if "openstax" not in _cache:
        _cache["openstax"] = json.loads(fetch_text(OPENSTAX_API, KIT_UA) or '{"items": []}')["items"]
    pat = re.compile("^" + re.escape(slug) + r"(?:-(\d+)e)?$")
    hits = []
    for b in _cache["openstax"]:
        m = pat.match(b["meta"]["slug"])
        if m and b.get("high_resolution_pdf_url") and b.get("book_state") in ("live", "deprecated", "retired"):
            hits.append(((b["book_state"] == "live", int(m.group(1) or 1)), b))
    if not hits:
        return None, None, None
    b = max(hits, key=lambda h: h[0])[1]
    return b["high_resolution_pdf_url"], b["title"], f"{b.get('license_name')} {b.get('license_version') or ''}".strip()


def get_book_text(b, fmt):
    dest = catalog.book_file(b, fmt)
    if b.get("openstax"):
        url, title, lic = openstax_book(b["openstax"])
        if not url:
            say(f"FAIL {b['id']}: OpenStax has no PDF for {b['openstax']!r} (check {OPENSTAX_API.split('?')[0]})")
            return False
        say(f"    {b['id']}: {title} (OpenStax, {lic})")
        return fetch_checked(url, dest, "pdf")
    if b.get("gutenberg"):
        n = b["gutenberg"]
        # Gutenberg asks scripts to use mirrors (its main site answers them with 503). Illustrated EPUB 3 first
        # (Treasure Island 49 MB, Monte Cristo 85 MB), the plain text-only EPUB if that fails.
        for mirror in GUTENBERG_MIRRORS:
            for name in (f"pg{n}-images-3.epub", f"pg{n}.epub"):
                if fetch_checked(f"{mirror}/cache/epub/{n}/{name}", dest, "epub"):
                    return True
            time.sleep(2)
        return False
    if b.get("pdf_index"):  # one PDF per chapter: books/<cat>/<Title - Author>/<chapter>.pdf
        page, pat = b["pdf_index"]
        if os.path.isfile(os.path.join(dest, catalog.DONE)):
            say(f"OK  {os.path.basename(dest)}/ (have it)")
            return True
        html = fetch_text(page, KIT_UA)
        chapters = {}  # file -> "04 Processes.pdf" (numbered chapters sort in book order)
        for num, fname, title in re.findall(pat, html or ""):
            title = catalog.safe(re.sub(r"\s+", " ", title)) or fname[:-4]
            chapters.setdefault(fname, f"{int(num):02d} {title}.pdf" if num else fname)  # titles of extras repeat
        if not chapters:
            say(f"FAIL {b['id']}: no chapter PDFs found on {page}")
            return False
        say(f"    {b['id']}: {len(chapters)} chapter PDFs from {page}")
        fails = 0
        for fname, local in chapters.items():
            print(f"    {local}", flush=True)
            fails += not fetch_checked(urllib.parse.urljoin(page, fname), os.path.join(dest, local), "pdf", quiet=True)
        names = chapters
        if fails:
            say(f"FAIL {b['id']}: {fails} of {len(names)} chapters (run again to retry)")
            return False
        with open(os.path.join(dest, catalog.DONE), "w") as f:
            f.write(f"{len(names)} chapters from {page}\n")
        say(f"OK  {os.path.basename(dest)}/ ({len(names)} chapters)")
        return True
    return fetch_checked(b["files"][fmt], dest, fmt)


def get_audiobook(b):
    """LibriVox recording: every 64 kbps MP3 of the archive.org item, into audiobooks/<cat>/<Title - Author>/."""
    ident, folder = b["librivox"], catalog.audio_dir(b)
    if os.path.isfile(os.path.join(folder, catalog.DONE)):
        say(f"OK  audiobook {b['title']} (have it)")
        return True
    meta = json.loads(fetch_text(f"https://archive.org/metadata/{ident}", KIT_UA) or "{}")
    tracks = sorted((f for f in meta.get("files", []) if f.get("format") == "64Kbps MP3"), key=lambda f: f["name"])
    if not tracks:
        say(f"FAIL audiobook {b['title']}: no MP3s in archive.org item {ident}")
        return False
    mb = sum(int(t.get("size", 0)) for t in tracks) / 1e6
    say(f"GET audiobook {b['title']}: {len(tracks)} parts, {mb:,.0f} MB (LibriVox, public domain)")
    fails = 0
    for n, t in enumerate(tracks, 1):
        dest = os.path.join(folder, t["name"])
        if not (size_of(dest) == int(t.get("size", -2)) and looks_like(dest, "mp3")):
            print(f"    part {n} of {len(tracks)}: {t['name']}", flush=True)
            fails += not fetch_checked(f"https://archive.org/download/{ident}/{urllib.parse.quote(t['name'])}",
                                       dest, "mp3", quiet=True)
    if fails:
        say(f"FAIL audiobook {b['title']}: {fails} of {len(tracks)} parts (run again to retry)")
        return False
    with open(os.path.join(folder, catalog.TRACKS), "w", encoding="utf-8") as f:  # chapter titles for the player
        json.dump({t["name"]: t.get("title") or "" for t in tracks}, f, indent=0, ensure_ascii=False)
    with open(os.path.join(folder, catalog.DONE), "w", encoding="utf-8") as f:
        f.write(f"{b['title']} by {b['author']}, read by LibriVox volunteers (public domain).\n"
                f"https://archive.org/details/{ident}\n")
    say(f"OK  audiobook {b['title']} ({len(tracks)} parts, {mb:,.0f} MB)")
    return True


def write_book_notes():
    """books/ABOUT THESE BOOKS.txt: where each book came from and its license (most licenses ask for this)."""
    lines = ["Books and audiobooks in this kit: source and license of each.",
             "Fetched with the kit's `books` command (bin/catalog.py lists them all).", ""]
    for b in catalog.BOOKS:
        have = catalog.book_status(b)
        if have:
            src = ("OpenStax (openstax.org)" if b.get("openstax") else f"Project Gutenberg #{b['gutenberg']}"
                   if b.get("gutenberg") else "Kiwix library" if b.get("zim") else
                   (b.get("files") or {}).get("epub") or (b.get("files") or {}).get("pdf") or b["pdf_index"][0])
            lines.append(f"- {b['title']} by {b['author']} [{', '.join(have)}]\n    source: {src}\n"
                         f"    license: {b['license']}" +
                         (f"\n    audiobook: LibriVox, public domain, https://archive.org/details/{b['librivox']}"
                          if "audio" in have else ""))
    os.makedirs(catalog.BOOKS_DIR, exist_ok=True)
    with open(os.path.join(catalog.BOOKS_DIR, "ABOUT THESE BOOKS.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def books_get(books, fmt="epub", audio=False, audio_only=False, dry_run=False):
    pref = {"epub": ["epub", "pdf"], "pdf": ["pdf", "epub"]}
    say(f"=== books v{VERSION}: {len(books)} book(s), format {fmt}"
        f"{', with audiobooks' if audio else ', audiobooks only' if audio_only else ''} ===")
    fails = 0
    for n, b in enumerate(books, 1):
        avail = catalog.formats_of(b)
        want = avail if fmt == "both" else [f for f in pref[fmt] if f in avail][:1] or avail[:1]
        print(f"--- {n}/{len(books)} {b['title']} ({b['author']}): "
              f"{'' if audio_only else '/'.join(want)}{' + audiobook' if (audio or audio_only) and b.get('librivox') else ''}",
              flush=True)
        if dry_run:
            continue
        if not audio_only:
            for f in want:
                if f == "library":
                    fails += not download_zim(*b["zim"], update=False)
                else:
                    fails += not get_book_text(b, f)
        if (audio or audio_only) and b.get("librivox"):
            fails += not get_audiobook(b)
        elif audio_only:
            print("    (no audiobook for this one)")
    if not dry_run:
        write_book_notes()
    say(f"=== books done, {fails} failed ===" if not dry_run else "=== dry run: nothing downloaded ===")
    if not dry_run and any(b.get("zim") for b in books) and not audio_only:
        print("Note: a book that is a Library (the Rust book) shows up after the kit is restarted.")
    return fails


def print_books(books):
    cat = None
    for b in books:
        if b["cat"] != cat:
            cat = b["cat"]
            print(f"\n{catalog.CATEGORIES[cat][0]}  (category: {cat})")
        have = catalog.book_status(b)
        fm = "/".join(f.upper() if f != "library" else "Library" for f in catalog.formats_of(b))
        mark = "✓" if any(k != "audio" for k in have) else " "
        audio = ("  🎧 have audiobook" if "audio" in have else "  🎧 audiobook available") if b.get("librivox") else ""
        print(f"  {mark} {b['id']:<26} {b['title']} - {b['author']}  [{fm}]{audio}")
    print("\n✓ = downloaded.  Get some with e.g.:  " + kit_cmd() + " books get calculus-1 nursing dracula")


def menu(prompt):
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def menu_words(ans, numbers, items, fields):
    """Words typed at a menu: numbers pick menu lines; other words are grouped into the longest phrases that
    match something ("nursing think python" = nursing + think python). Commas always separate."""
    words = []
    for piece in ans.split(","):
        phrase = []
        for tok in piece.split() + [","]:
            if tok.isdigit() or tok == ",":
                i = 0
                while i < len(phrase):  # longest run of words that some item matches, left to right
                    j = next((j for j in range(len(phrase), i, -1)
                              if catalog.pick(items, [" ".join(phrase[i:j])], fields)[0]), i + 1)
                    words.append(" ".join(phrase[i:j]))
                    i = j
                phrase = []
                if tok != ",":
                    words.append(numbers.get(int(tok), tok))
            else:
                phrase.append(tok)
    return words


def books_menu():
    cats = list(catalog.CATEGORIES)
    print("\nBooks and audiobooks (optional: not part of install all)\n")
    for n, c in enumerate(cats, 1):
        items = [b for b in catalog.BOOKS if b["cat"] == c]
        got = sum(bool(catalog.book_status(b)) for b in items)
        print(f"  {n:>2}  {catalog.CATEGORIES[c][0]:<38} {len(items):>2} books" + (f", {got} downloaded" if got else ""))
    extra = {str(len(cats) + 1): "textbooks", str(len(cats) + 2): "fiction", str(len(cats) + 3): "all"}
    print(f"  {len(cats) + 1:>2}  All textbooks (about 3.4 GB)\n  {len(cats) + 2:>2}  All fiction (small; their audiobooks"
          f" are about 8 GB)\n  {len(cats) + 3:>2}  Everything")
    print("\nType numbers, category names, book ids or keywords,")
    print("e.g.  1 3 dracula   or   nursing think python   ('list' shows every book; Enter alone cancels)")
    while True:
        ans = menu("> ")
        if not ans:
            print("Nothing chosen.")
            return
        if ans.lower() == "list":
            print_books(catalog.BOOKS)
            continue
        numbers = {n: c for n, c in enumerate(cats, 1)} | {int(k): v for k, v in extra.items()}
        words = menu_words(ans, numbers, catalog.BOOKS, catalog.BOOK_FIELDS)
        books, unknown = catalog.pick(catalog.BOOKS, words, catalog.BOOK_FIELDS)
        if unknown:
            print(f"Nothing matches: {', '.join(unknown)}")
        if books:
            break
    print_books(books)
    with_audio = any(b.get("librivox") for b in books) and \
        menu("\nAlso get the audiobooks for these (MP3, about 100 MB to 1.4 GB each)? [y/N] ").lower().startswith("y")
    if not menu(f"Download {len(books)} book(s) now? [Y/n] ").lower().startswith("n"):
        sys.exit(2 if books_get(books, audio=with_audio) else 0)


def cmd_books(a):
    if a.action is None:
        if not sys.stdin.isatty():
            die(f"say what to get, e.g. {kit_cmd()} books get math   (or {kit_cmd()} books list)")
        return books_menu()
    books, unknown = catalog.pick(catalog.BOOKS, a.words or ["all"], catalog.BOOK_FIELDS)
    if unknown:
        print(f"Nothing matches: {', '.join(unknown)}. Categories: {', '.join(catalog.CATEGORIES)}; "
              f"groups: {', '.join(catalog.GROUPS)}, all. `{kit_cmd()} books list` shows every book.")
    if a.action == "list":
        return print_books(books)
    if not a.words:
        die(f"say which books, e.g. {kit_cmd()} books get math dracula   (or: books get all)")
    if not books:
        sys.exit(1)
    if books_get(books, a.format, a.audio, a.audio_only, a.dry_run):
        say("Some downloads failed (FAIL lines above). Run the same command again to retry them.")
        sys.exit(2)


# ---- software ----
def github_release(repo):
    key = "gh:" + repo
    if key not in _cache:
        hdr = ["-H", f"Authorization: Bearer {os.environ['GITHUB_TOKEN']}"] if os.environ.get("GITHUB_TOKEN") else []
        r = subprocess.run([curl(), "-sfL", "-A", KIT_UA, *hdr, f"https://api.github.com/repos/{repo}/releases/latest"],
                           capture_output=True)
        _cache[key] = json.loads(r.stdout or b"{}") if r.returncode == 0 else {}
    return _cache[key]


def publisher_sha256(url, name):
    """(sha256, where it came from) from the publisher's own checksum file, for hosts that post one; else (None, None).
    Fetched from the publisher's main server, not the mirror the file itself may come from."""
    if url.startswith("https://get.videolan.org/vlc/"):  # VideoLAN: <file>.sha256 next to each file
        sums = fetch_text(url.replace("https://get.videolan.org/vlc/", "https://download.videolan.org/pub/videolan/vlc/")
                          + ".sha256", KIT_UA) or ""
        m = re.match(r"([0-9a-f]{64})\s", sums)
        return (m.group(1), "videolan.org .sha256") if m else (None, "videolan.org .sha256 (missing)")
    m = re.match(r"https://download-installer\.cdn\.mozilla\.net/pub/firefox/releases/([^/]+)/(.+)$", url)
    if m:  # Mozilla: one SHA256SUMS per release on archive.mozilla.org
        sums = fetch_text(f"https://archive.mozilla.org/pub/firefox/releases/{m.group(1)}/SHA256SUMS", KIT_UA) or ""
        rel = urllib.parse.unquote(m.group(2))
        hit = re.search(r"(?m)^([0-9a-f]{64})\s+" + re.escape(rel) + "$", sums)
        return (hit.group(1), "mozilla.org SHA256SUMS") if hit else (None, "mozilla.org SHA256SUMS (missing)")
    return None, None


def resolve(how):
    """(url, file name, sha256 or None, where the checksum came from) of the newest download,
    or (None, reason, None, None)."""
    kind = how[0]
    if kind == "github":
        rel = github_release(how[1])
        if not rel:
            return None, f"GitHub didn't answer for {how[1]} (rate limit? set GITHUB_TOKEN, or wait an hour)", None, None
        for asset in rel.get("assets", []):
            if re.fullmatch(how[2], asset["name"]):
                d = asset.get("digest") or ""
                return (asset["browser_download_url"], asset["name"], d[7:] if d.startswith("sha256:") else None,
                        "GitHub release checksum" if d.startswith("sha256:") else None)
        return None, f"no file like {how[2]} in {how[1]} {rel.get('tag_name')}", None, None
    if kind == "github-tag":
        rel = github_release(how[1])
        if not rel.get("tag_name"):
            return None, f"GitHub didn't answer for {how[1]}", None, None
        url = how[2].format(v=rel["tag_name"].lstrip("v"))
        name = os.path.basename(url)
    elif kind == "page":
        m = re.search(how[2], fetch_text(how[1], KIT_UA) or "")
        if not m:
            return None, f"no link like {how[2]} on {how[1]}", None, None
        url = urllib.parse.urljoin(how[1], m.group(0))
        name = os.path.basename(url)
    elif kind == "redirect":
        r = subprocess.run([curl(), "-sIL", "--connect-timeout", "30", "-m", "60", "-A", KIT_UA, "-o", os.devnull,
                            "-w", "%{url_effective}", how[1]], capture_output=True)
        url = r.stdout.decode().strip()
        if r.returncode != 0 or not url or url == how[1]:
            return None, f"{how[1]} didn't forward to a file", None, None
        name = urllib.parse.unquote(os.path.basename(urllib.parse.urlparse(url).path))
    else:
        return None, f"unknown source type {kind}", None, None
    digest, where = publisher_sha256(url, name)
    if where and not digest:
        return None, f"the publisher's checksum for {name} wasn't found ({where}); not downloading it unchecked", None, None
    return url, name, digest, where


def trusted(url):
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    return urllib.parse.urlparse(url).scheme == "https" and \
        any(host == h or host.endswith("." + h) for h in catalog.TRUSTED_SOFTWARE_HOSTS)


def software_get(apps, oses, dry_run=False, only_present=False):
    """Official releases only: the link must be on the program's own host (catalog.TRUSTED_SOFTWARE_HOSTS), and the
    file must match the publisher's checksum when the publisher posts one (GitHub, VideoLAN, Mozilla).
    only_present: just the programs/systems already downloaded (`software update`)."""
    say(f"=== software v{VERSION}: {', '.join(a['name'] for a in apps)} for {', '.join(oses)} ===")
    fails = 0
    today = time.strftime("%Y-%m-%d")
    for app in apps:
        for o in oses:
            entry = app["os"].get(o)
            if only_present and not catalog.software_files(app, o):
                continue
            if isinstance(entry, str) or not entry:
                print(f"--- {app['name']} for {catalog.OS_NAMES[o]}: no download. {entry or ''}")
                continue
            folder = os.path.join(catalog.SOFTWARE_DIR, o, app["id"])
            keep, record = [], {}
            old = {}
            try:
                with open(os.path.join(folder, catalog.CHECKSUMS), encoding="utf-8") as f:
                    old = json.load(f)
            except (OSError, ValueError):
                pass
            for label, how in entry:
                url, name, digest, where = resolve(how)
                print(f"--- {app['name']} for {catalog.OS_NAMES[o]} ({label}): {name}", flush=True)
                if not url:
                    say(f"FAIL {app['id']} {o}: {name}")
                    fails += 1
                    continue
                if not dry_run and os.path.exists(os.path.join(folder, name)):
                    print("    (you have this version)")
                if not trusted(url):
                    say(f"FAIL {app['id']} {o}: {url} is not the program's official download site; skipped")
                    fails += 1
                    continue
                print(f"    {url}\n    checksum: {'sha256 from ' + where if digest else 'none published (official site, HTTPS)'}")
                if dry_run:
                    continue
                dest = os.path.join(folder, name)
                if not get(url, dest, tries=3, ua=KIT_UA):
                    fails += 1
                    continue
                if digest and sha256(dest) != digest:
                    os.remove(dest)
                    say(f"FAIL {name}: doesn't match the publisher's checksum ({where}); deleted")
                    fails += 1
                    continue
                if digest:
                    say(f"    checksum OK ({where})")
                keep.append(name)
                record[name] = {"url": url, "sha256": digest or sha256(dest), "verified_by": where,
                                # downloaded: when this version arrived; checked: last time it was the newest release
                                "downloaded": old.get(name, {}).get("downloaded") or today, "checked": today}
            if keep and len(keep) == len(entry):  # everything new is here: remove older versions
                for old_file in catalog.visible(folder):
                    if old_file not in keep and not old_file.endswith((".part", ".json")):
                        say(f"    removing older {old_file}")
                        os.remove(os.path.join(folder, old_file))
            if record:
                with open(os.path.join(folder, catalog.CHECKSUMS), "w", encoding="utf-8") as f:
                    json.dump({k: v for k, v in (old | record).items() if os.path.exists(os.path.join(folder, k))},
                              f, indent=1)
    say(f"=== software done, {fails} failed ===" if not dry_run else "=== dry run: nothing downloaded ===")
    return fails


def software_age_days(app, o):
    """Days since this program was last confirmed up to date (checksums.json 'checked', else the file's date)."""
    folder = os.path.join(catalog.SOFTWARE_DIR, o, app["id"])
    files = catalog.software_files(app, o)
    if not files:
        return None
    try:
        with open(os.path.join(folder, catalog.CHECKSUMS), encoding="utf-8") as f:
            sums = json.load(f)
        dates = [sums[os.path.basename(p)]["checked"] for p in files]
        return min((time.time() - time.mktime(time.strptime(d, "%Y-%m-%d"))) // 86400 for d in dates)
    except (OSError, ValueError, KeyError):
        return min((time.time() - os.path.getmtime(p)) // 86400 for p in files)


def software_check(apps, oses):
    """Which downloaded programs have a newer release (asks each publisher; downloads nothing)."""
    print(f"Checking for newer versions of what you have (programs older than {catalog.STALE_DAYS} days "
          f"since their last check are marked):")
    behind = 0
    for app in apps:
        for o in oses:
            files = [os.path.basename(p) for p in catalog.software_files(app, o)]
            entry = app["os"].get(o)
            if not files or isinstance(entry, str):
                continue
            newest = [resolve(how)[1] for _, how in entry]
            age = software_age_days(app, o)
            new = [n for n in newest if n not in files]
            behind += bool(new)
            print(f"  {'NEWER ' if new else 'ok    '}{app['name']} for {catalog.OS_NAMES[o]}: have {', '.join(files)}"
                  + (f"; newest {', '.join(new)}" if new else "")
                  + (f"  (last checked {int(age)} days ago)" if age is not None and age > catalog.STALE_DAYS else ""))
    print(f"\n{behind} out of date." + (f" Update them with:  {kit_cmd()} software update" if behind else ""))
    return behind


def os_list(value):
    if value in (None, "all"):
        return list(catalog.OS_NAMES)
    if value == "current":
        return ["windows" if WINDOWS else "mac" if sys.platform == "darwin" else "linux"]
    out = [{"win": "windows", "macos": "mac", "osx": "mac"}.get(o.strip().lower(), o.strip().lower())
           for o in value.split(",")]
    for o in out:
        o in catalog.OS_NAMES or die(f"unknown OS {o!r} (use windows, mac, linux, current or all)")
    return out


def print_software(apps, oses):
    for app in apps:
        print(f"\n  {app['id']:<11} {app['name']}: {app['about']}")
        for o in oses:
            entry = app["os"].get(o)
            files = catalog.software_files(app, o)
            if isinstance(entry, str):
                print(f"      {catalog.OS_NAMES[o]:<8} - {entry}")
            else:
                got = ", ".join(os.path.basename(f) for f in files)
                print(f"      {catalog.OS_NAMES[o]:<8} {'✓ ' + got if files else '  ' + ', '.join(l for l, _ in entry)}")
    print(f"\n✓ = downloaded.  Get some with e.g.:  {kit_cmd()} software get vlc calibre --os windows,mac")


def software_menu(oses):
    apps = catalog.SOFTWARE
    print("\nSoftware for the kit's download center (optional: not part of install all)\n")
    for n, app in enumerate(apps, 1):
        got = [catalog.OS_NAMES[o] for o in catalog.OS_NAMES if catalog.software_files(app, o)]
        print(f"  {n:>2}  {app['name']:<18} {app['about'][:70]}" + (f"  [have: {', '.join(got)}]" if got else ""))
    print(f"  {len(apps) + 1:>2}  All of them")
    ans = menu("\nType numbers or names (e.g. 1 4 6, or vlc calibre); Enter alone cancels\n> ")
    if not ans:
        print("Nothing chosen.")
        return
    numbers = {n: app["id"] for n, app in enumerate(apps, 1)} | {len(apps) + 1: "all"}
    words = menu_words(ans, numbers, apps, catalog.SOFTWARE_FIELDS)
    chosen, unknown = catalog.pick(apps, words, catalog.SOFTWARE_FIELDS)
    if unknown:
        print(f"Nothing matches: {', '.join(unknown)}")
    if not chosen:
        return
    o = menu("For which computers? 1 Windows  2 Mac  3 Linux  4 all three  (Enter = all three) > ")
    oses = [list(catalog.OS_NAMES)[int(x) - 1] for x in re.findall(r"[1-3]", o)] or list(catalog.OS_NAMES)
    sys.exit(2 if software_get(chosen, oses) else 0)


def cmd_software(a):
    oses = os_list(a.os)
    if a.action in ("update", "check"):
        apps = catalog.pick(catalog.SOFTWARE, a.words or ["all"], catalog.SOFTWARE_FIELDS)[0]
        if not any(catalog.software_files(x, o) for x in apps for o in oses):
            die(f"no software downloaded yet; get some first, e.g. {kit_cmd()} software get vlc")
        if a.action == "check":
            return software_check(apps, oses)
        if software_get(apps, oses, a.dry_run, only_present=True):
            say("Some updates failed (FAIL lines above). Run the same command again to retry them.")
            sys.exit(2)
        return
    if a.action is None:
        if not sys.stdin.isatty():
            die(f"say what to get, e.g. {kit_cmd()} software get vlc   (or {kit_cmd()} software list)")
        return software_menu(oses)
    apps, unknown = catalog.pick(catalog.SOFTWARE, a.words or ["all"], catalog.SOFTWARE_FIELDS)
    if unknown:
        print(f"Nothing matches: {', '.join(unknown)}. Programs: {', '.join(x['id'] for x in catalog.SOFTWARE)}, all")
    if a.action == "list":
        return print_software(apps, oses)
    if not a.words:
        die(f"say which programs, e.g. {kit_cmd()} software get vlc calibre   (or: software get all)")
    if not apps:
        sys.exit(1)
    if software_get(apps, oses, a.dry_run):
        say("Some downloads failed (FAIL lines above). Run the same command again to retry them.")
        sys.exit(2)


# ---- movies ----
IA_VIDEO_PREF = ["h.264", "h.264 IA", "512Kb MPEG4", "MPEG4", "h.264 MPEG4"]  # H.264 first: plays in every browser


def ia_metadata(ident):
    key = "ia:" + ident
    if key not in _cache:
        _cache[key] = json.loads(fetch_text(f"https://archive.org/metadata/{ident}", KIT_UA) or "{}")
    return _cache[key]


def ia_best_video(meta, wanted=None):
    """(file name, size) of the pinned file if the item still has it, else its best browser-playable MP4."""
    files = [f for f in meta.get("files", []) if f["name"].lower().endswith((".mp4", ".m4v"))]
    for f in files:
        if f["name"] == wanted:
            return f["name"], int(f.get("size", 0))
    ok = [f for f in files if f.get("format") in IA_VIDEO_PREF and int(f.get("size", 0)) > 20_000_000]
    if not ok:
        return None, 0
    # preferred format, then the biggest file of it (several cuts or a trailer can sit in one item)
    f = min(ok, key=lambda f: (IA_VIDEO_PREF.index(f["format"]), -int(f.get("size", 0))))
    return f["name"], int(f.get("size", 0))


def looks_like_video(path):
    try:
        with open(path, "rb") as f:
            head = f.read(16)
    except OSError:
        return False
    return b"ftyp" in head[:12] or head.startswith(b"\x1a\x45\xdf\xa3") or head.startswith(b"RIFF")  # mp4 / mkv,webm / avi


def get_movie(m, dry_run=False):
    dest = catalog.movie_file(m)
    if os.path.isfile(dest) and looks_like_video(dest):
        say(f"OK  {os.path.basename(dest)} (have it)")
        return True
    if m.get("url"):  # added by hand from a direct link
        url, size = m["url"], None
    else:
        meta = ia_metadata(m["ia"])
        name, size = ia_best_video(meta, m.get("file"))
        if not name:
            say(f"FAIL {m['title']}: no playable MP4 in archive.org item {m['ia']}")
            return False
        if name != m.get("file"):
            say(f"    {m['title']}: {m.get('file')} is gone from archive.org, using {name}")
        url = f"https://archive.org/download/{m['ia']}/{urllib.parse.quote(name)}"
    print(f"    {m['title']} ({m.get('year') or '?'}): {size / 1e6:,.0f} MB" if size else f"    {m['title']}", flush=True)
    if dry_run:
        print(f"    {url}")
        return True
    if not get(url, dest, tries=3, ua=KIT_UA):
        return False
    if looks_like_video(dest):
        return True
    os.remove(dest)
    say(f"FAIL {m['title']}: the download isn't a video file <- {url}")
    return False


def movies_get(movies, dry_run=False):
    say(f"=== movies v{VERSION}: {len(movies)} film(s) ===")
    fails = 0
    for n, m in enumerate(movies, 1):
        print(f"--- {n}/{len(movies)} {m['title']}", flush=True)
        fails += not get_movie(m, dry_run)
    say(f"=== movies done, {fails} failed ===" if not dry_run else "=== dry run: nothing downloaded ===")
    return fails


def print_movies(movies):
    cat = None
    for m in movies:
        if m["cat"] != cat:
            cat = m["cat"]
            print(f"\n{catalog.MOVIE_CATEGORIES.get(cat, cat)}  (category: {cat})")
        mark = "✓" if os.path.isfile(catalog.movie_file(m)) else " "
        print(f"  {mark} {m['id']:<24} {m['title']} ({m.get('year') or '?'}), {m.get('minutes') or '?'} min")
    print(f"\n✓ = downloaded.  Get some with e.g.:  {kit_cmd()} movies get comedy nosferatu\n"
          f"Add any other free film:  {kit_cmd()} movies add https://archive.org/details/<item>")


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:40] or "movie"


def cmd_movies_add(a):
    """Add a film to movies/my-movies.json and download it. Takes an archive.org item (link or id)
    or a direct link to a video file. Only add films you are allowed to download (public domain or open license)."""
    src = a.words[0] if a.words else die(f"say what to add, e.g. {kit_cmd()} movies add https://archive.org/details/<item>")
    m = re.match(r"(?:https?://(?:www\.)?archive\.org/(?:details|download)/)?([A-Za-z0-9._-]+)/?(?:[?#].*)?$", src)
    if src.startswith("http") and not re.match(r"https?://(?:www\.)?archive\.org/(details|download)/", src):
        name = urllib.parse.unquote(os.path.basename(urllib.parse.urlparse(src).path))
        name.lower().endswith(catalog.VIDEO_EXT) or die("a direct link must end in a video file name (.mp4, .webm, ...)")
        entry = dict(title=a.title or os.path.splitext(name)[0].replace("_", " "), year=a.year, url=src, file=name,
                     license="added by you (from " + urllib.parse.urlparse(src).netloc + ")")
    elif m:
        ident = m.group(1)
        meta = ia_metadata(ident)
        meta.get("metadata") or die(f"archive.org has no item {ident!r}")
        md = meta["metadata"]
        name, size = ia_best_video(meta)
        name or die(f"archive.org item {ident} has no MP4 video the kit can play")
        lic = md.get("licenseurl") or md.get("rights") or "see archive.org"
        if not re.search(r"publicdomain|creativecommons", str(lic)):
            print(f"Note: archive.org lists no public-domain or Creative Commons license for this item ({lic}).\n"
                  "Only keep it if you know it's free to download.")
        title = a.title or (md.get("title") if isinstance(md.get("title"), str) else ident)
        year = a.year or (re.search(r"\d{4}", str(md.get("year") or md.get("date") or "")) or [None])[0]
        entry = dict(title=title, year=year, ia=ident, file=name, license=str(lic))
    else:
        die("give an archive.org link or item id, or a direct link to a video file")
    entry.update(id=slug(entry["title"]), cat=a.category or "my-movies", minutes=None, kw="mine added")
    mine = [x for x in catalog.my_movies() if x["id"] != entry["id"]] + [entry]
    os.makedirs(catalog.MOVIES_DIR, exist_ok=True)
    with open(catalog.MY_MOVIES, "w", encoding="utf-8") as f:
        json.dump(mine, f, indent=1)
    say(f"Added {entry['title']} ({entry.get('year') or '?'}) as {entry['id']!r} in {catalog.MY_MOVIES}")
    if not a.dry_run and not get_movie(entry):
        say(f"Download failed; run `{kit_cmd()} movies get {entry['id']}` to retry.")
        sys.exit(2)


def movies_menu():
    cats = list(catalog.MOVIE_CATEGORIES)
    movies = catalog.all_movies()
    print("\nMovies (optional: not part of install all). Public domain and Creative Commons films.\n")
    shown = []
    for c in cats:
        items = [m for m in movies if m["cat"] == c]
        if items:
            shown.append(c)
            got = sum(os.path.isfile(catalog.movie_file(m)) for m in items)
            print(f"  {len(shown):>2}  {catalog.MOVIE_CATEGORIES[c]:<42} {len(items):>2} films" +
                  (f", {got} downloaded" if got else ""))
    print(f"  {len(shown) + 1:>2}  Everything (about 17 GB)")
    print("\nType numbers, categories, movie ids or keywords (e.g. 1 5 nosferatu, or 'sherlock holmes');")
    print("'list' shows every film; Enter alone cancels.")
    while True:
        ans = menu("> ")
        if not ans:
            print("Nothing chosen.")
            return
        if ans.lower() == "list":
            print_movies(movies)
            continue
        numbers = {n: c for n, c in enumerate(shown, 1)} | {len(shown) + 1: "all"}
        words = menu_words(ans, numbers, movies, catalog.MOVIE_FIELDS)
        chosen, unknown = catalog.pick(movies, words, catalog.MOVIE_FIELDS)
        if unknown:
            print(f"Nothing matches: {', '.join(unknown)}")
        if chosen:
            break
    print_movies(chosen)
    if not menu(f"Download {len(chosen)} film(s) now? [Y/n] ").lower().startswith("n"):
        sys.exit(2 if movies_get(chosen) else 0)


def cmd_movies(a):
    if a.action == "add":
        return cmd_movies_add(a)
    if a.action is None:
        if not sys.stdin.isatty():
            die(f"say what to get, e.g. {kit_cmd()} movies get comedy   (or {kit_cmd()} movies list)")
        return movies_menu()
    movies, unknown = catalog.pick(catalog.all_movies(), a.words or ["all"], catalog.MOVIE_FIELDS)
    if unknown:
        print(f"Nothing matches: {', '.join(unknown)}. Categories: {', '.join(catalog.MOVIE_CATEGORIES)}, all. "
              f"`{kit_cmd()} movies list` shows every film.")
    if a.action == "list":
        return print_movies(movies)
    if not a.words:
        die(f"say which films, e.g. {kit_cmd()} movies get comedy nosferatu   (or: movies get all)")
    if not movies:
        sys.exit(1)
    if movies_get(movies, a.dry_run):
        say("Some downloads failed (FAIL lines above). Run the same command again to retry them.")
        sys.exit(2)


# ==== make-drive =======================================================================================
DRIVE_SKIP_DIRS = {".git", ".venv", "build", "__pycache__", "drive-root", "logs"}
DRIVE_SKIP = re.compile(r"(^kit-settings\.json|\.bak-[^/\\]*|\.DS_Store|^\._.*|^download.*\.log|\.log|\.part|\.tmp|\.new\.pmtiles)$")


def copy_changed(src, dst, skip_zims):
    n = 0
    for root, dirs, files in os.walk(src):
        rel = os.path.relpath(root, src)
        dirs[:] = [d for d in dirs if d not in DRIVE_SKIP_DIRS and not (rel == "bible" and d == "src")]
        for f in files:
            if DRIVE_SKIP.search(f) or (skip_zims and f.endswith(".zim")):
                continue
            s, d = os.path.join(root, f), os.path.join(dst, rel, f)
            st = os.stat(s)
            if os.path.exists(d) and size_of(d) == st.st_size and abs(os.path.getmtime(d) - st.st_mtime) < 3:
                continue
            if rel.split(os.sep)[0] == "family" and os.path.exists(d) and os.path.getmtime(d) > st.st_mtime + 3:
                # The Family page was saved on the drive after this copy: never replace the newer one
                print(f"  KEPT {os.path.join(rel, f)}: the drive's copy is newer (saved on the drive). To keep it on this"
                      f" computer too, copy it back: {d} -> {s}", flush=True)
                continue
            os.makedirs(os.path.dirname(d), exist_ok=True)
            print(f"  {os.path.join(rel, f)}", flush=True)
            shutil.copy2(s, d)  # keeps the time stamp (for the next re-run) and the Mac launcher's run permission
            n += 1
    return n


def cmd_make_drive(a):
    drive = os.path.abspath(a.drive)
    os.path.isdir(drive) or die(f"drive not found: {drive} (is it plugged in?)")
    dest = os.path.join(drive, "offline-prepper-kit")
    need = sum(size_of(os.path.join(r, f)) for r, d, fs in os.walk(KIT)
               if not set(os.path.relpath(r, KIT).split(os.sep)) & DRIVE_SKIP_DIRS for f in fs)
    have = sum(size_of(os.path.join(r, f)) for r, _, fs in os.walk(dest) for f in fs) if os.path.isdir(dest) else 0
    free = shutil.disk_usage(drive).free
    print(f"Kit needs about {need / 1e9:.0f} GB; drive has {free / 1e9:.0f} GB free (+{have / 1e9:.0f} GB already copied).")
    if free + have < need:
        die("not enough space on the drive (it must be exFAT: FAT32 can't hold files over 4 GB)")
    print("== 1/3 Programs, maps, directions, Bible, guides")
    n = copy_changed(KIT, dest, skip_zims=True)
    print("== 2/3 Launchers and instructions at the top of the drive")
    for f in os.listdir(kit_path("drive-root")):
        if not f.startswith("."):
            shutil.copy2(kit_path("drive-root", f), os.path.join(drive, f))
    if a.no_libraries:
        print("== 3/3 Libraries skipped (--no-libraries)")
    else:
        print("== 3/3 Libraries (Wikipedia is the big one: this part takes a while)")
        n += copy_changed(kit_path("kiwix"), os.path.join(dest, "kiwix"), skip_zims=False)
    print(f"Done: {n} files copied to {dest}")


# ==== main =============================================================================================
def main():
    p = argparse.ArgumentParser(prog="kit", description=__doc__.split("\n\n")[0],
                                formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("install", help="quick start: all, wiki or maps; optional modules: books, software, movies")
    s.add_argument("what", choices=["all", "wiki", "maps", "books", "software", "movies"])
    s.add_argument("words", nargs="*", help="books/software/movies: only these (categories, ids or keywords)")
    s.add_argument("--audio", action="store_true", help="books: also the audiobooks (MP3, large)")
    s.add_argument("--os", help="software: windows, mac, linux (comma list), current or all (default)")
    s.add_argument("--platform", help="programs for: current (default for wiki/maps), all (default for all; "
                   "needed for a drive that runs on both Windows and Mac)")
    s.add_argument("--only", help="wiki/all: only libraries whose name contains this, e.g. wikipedia_en_all")
    s.add_argument("--state", help="maps/all: build from one state (e.g. arkansas) instead of the whole US")
    s.set_defaults(fn=cmd_install)
    s = sub.add_parser("start", help="start the kit and open the Home page")
    s.add_argument("--port", type=int, help="Home page port (default 8000)")
    s.set_defaults(fn=cmd_start)

    s = sub.add_parser("setup", help="programs: runtimes, jars, map libraries and fonts")
    s.add_argument("--platform", default="all", help="all (default; the drive runs anywhere), current, "
                   "or a list such as win-x64,mac-arm64,mac-x64")
    s.add_argument("--force", action="store_true", help="download again even if present")
    s.set_defaults(fn=cmd_setup)

    s = sub.add_parser("download", help="Kiwix libraries and PDF guides")
    s.add_argument("--set", default="all", help="all (= core,programming,pdfs) or a list of core, programming, "
                   "pdfs, states (states = optional per-state OSM extracts for tests)")
    s.add_argument("--only", help="only items whose name contains this text, e.g. --only knots")
    s.add_argument("--update", action="store_true", help="fetch newer library editions even if you have one")
    s.set_defaults(fn=cmd_download_cli)

    def osm_args(s, out_help=None, xmx=None):
        s.add_argument("--pbf", help="use this .osm.pbf instead of build/us.osm.pbf (e.g. a state, for a quick test)")
        s.add_argument("--refresh-osm", action="store_true", help="download a fresh build/us.osm.pbf first")
        if out_help:
            s.add_argument("--output", help=out_help)
        if xmx:
            s.add_argument("--xmx", default=xmx, help=f"Java heap (default {xmx})")

    s = sub.add_parser("build-map", help="maps/us.pmtiles")
    osm_args(s, "output .pmtiles (default maps/us.pmtiles)", "14g")
    s.set_defaults(fn=cmd_build_map)
    s = sub.add_parser("build-routing", help="routing/graph-us/")
    osm_args(s, xmx="18g")
    s.add_argument("--graph", help="output folder (default routing/graph-us)")
    s.set_defaults(fn=cmd_build_routing)
    s = sub.add_parser("build-places", help="map-viewer/places.json")
    osm_args(s, "output .json (default map-viewer/places.json)")
    s.add_argument("--engine", choices=["auto", "pyosmium"], default="auto",
                   help="auto uses osmium-tool when installed, else pyosmium")
    s.set_defaults(fn=cmd_build_places)
    s = sub.add_parser("build-bible", help="kiwix/bible_en_kjv_*.zim and home/kjv.json")
    s.set_defaults(fn=cmd_build_bible)
    s = sub.add_parser("build-all", help="build-map, build-routing, build-places, build-bible")
    osm_args(s)
    s.set_defaults(fn=cmd_build_all)
    s = sub.add_parser("all", help="setup + download + build-all (everything)")
    s.set_defaults(fn=cmd_all)
    s = sub.add_parser("make-drive", help="copy the kit to a USB drive")
    s.add_argument("drive", help="the drive, e.g. E:\\ on Windows or /Volumes/NAME on a Mac")
    s.add_argument("--no-libraries", action="store_true", help="skip kiwix/*.zim (quick)")
    s.set_defaults(fn=cmd_make_drive)
    s = sub.add_parser("books", help="optional: textbooks, novels and audiobooks (menu, list, get)")
    s.add_argument("action", nargs="?", choices=["list", "get"])
    s.add_argument("words", nargs="*", help="categories (math, nursing, ... fiction, textbooks, all), "
                   "book ids or keywords; quote a phrase: \"think python\"")
    s.add_argument("--format", choices=["epub", "pdf", "both"], default="epub",
                   help="epub (default): EPUB when there is one, else PDF; pdf: the other way round; both")
    s.add_argument("--audio", action="store_true", help="also get the audiobook (LibriVox MP3) where there is one")
    s.add_argument("--audio-only", action="store_true", help="only the audiobooks")
    s.add_argument("--dry-run", action="store_true", help="show what would be downloaded")
    s.set_defaults(fn=cmd_books)
    s = sub.add_parser("software", help="optional: programs for the download center, by OS (menu, list, get)")
    s.add_argument("action", nargs="?", choices=["list", "get", "update", "check"],
                   help="update: newest version of everything you already have (old versions are removed); "
                        "check: just report what's out of date")
    s.add_argument("words", nargs="*", help="program ids (vlc, mplayer, mpv, calibre, sumatrapdf, thorium, 7zip, "
                   "firefox, retroarch, notepadpp), keywords (video, ebook...) or all")
    s.add_argument("--os", help="windows, mac, linux (comma list), current, or all (default)")
    s.add_argument("--dry-run", action="store_true", help="find the newest versions, download nothing")
    s.set_defaults(fn=cmd_software)
    s = sub.add_parser("movies", help="optional: free films to stream or download (menu, list, get, add)")
    s.add_argument("action", nargs="?", choices=["list", "get", "add"])
    s.add_argument("words", nargs="*", help="get: categories (comedy, drama, mystery, adventure, horror, open-movies, "
                   "all), movie ids or keywords. add: an archive.org link or item id, or a direct video link")
    s.add_argument("--title", help="add: the film's title (default: from archive.org or the file name)")
    s.add_argument("--year", help="add: the year")
    s.add_argument("--category", help="add: which section it shows in (default my-movies)")
    s.add_argument("--dry-run", action="store_true", help="show what would be downloaded")
    s.set_defaults(fn=cmd_movies)
    s = sub.add_parser("version", help="print the kit version")
    s.set_defaults(fn=lambda a: print(f"offline prepper kit {VERSION}"))

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
