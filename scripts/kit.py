#!/usr/bin/env python3
"""kit.py (offline prepper kit v1.12.0): download and rebuild everything in the kit, on macOS or Windows.

Run it through the wrappers, which also fetch a portable Python the first time if needed:
    macOS:   ./kit.sh <command> [options]
    Windows: kit.bat <command> [options]

Commands (each is safe to re-run; finished work is skipped and downloads resume):
    setup          programs the kit carries: portable Python/Java/kiwix-serve for Windows and Mac (runtime/),
                   Planetiler and GraphHopper jars, MapLibre, map fonts and icons
    download       content: Kiwix libraries (kiwix/*.zim) and PDF guides (guides/)
    build-map      whole-US map tiles maps/us.pmtiles (downloads build/us.osm.pbf, ~12 GB, first)
    build-routing  offline directions graph routing/graph-us/ from build/us.osm.pbf
    build-places   town search list map-viewer/places.json from build/us.osm.pbf
    build-bible    KJV Bible library kiwix/bible_en_kjv_<yyyy-mm>.zim and home/kjv.json
    build-all      build-map, build-routing, build-places, build-bible
    all            setup, download, build-all (everything; ~190 GB and many hours)
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
import zipfile

VERSION = "1.12.0"
HERE = os.path.dirname(os.path.abspath(__file__))
KIT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(KIT, "bin"))  # kitplatform (python -I leaves script dirs out of sys.path)
import kitplatform  # noqa: E402

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
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def kit_path(*parts):
    return os.path.join(KIT, *parts)


def curl():
    exe = shutil.which("curl.exe" if WINDOWS else "curl")
    if not exe:
        die("curl not found (it comes with macOS and Windows 10 or later)")
    return exe


def fetch_text(url):
    r = subprocess.run([curl(), "-sfL", "-A", UA, url], capture_output=True)
    return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else None


def remote_size(url):
    r = subprocess.run([curl(), "-sIL", "-A", UA, url], capture_output=True)
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


def get(url, dest, tries=5, quiet=False):
    """Resumable download to dest (via dest.part). Skips a file that's already complete. Returns True if OK."""
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    name = os.path.basename(dest)
    remote = remote_size(url)
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
        rc = subprocess.call([curl(), "-fL", "-A", UA, "--retry", "5", "--retry-delay", "10", "-C", "-",
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


def run(cmd, cwd=None, log=None):
    print("$ " + " ".join(f'"{c}"' if " " in c else c for c in cmd), flush=True)
    if log:
        with open(log, "w", encoding="utf-8") as f:
            rc = subprocess.call(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT)
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
    if fails:
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
    if not a.graph and port_open(8989):
        die("the directions router is running (port 8989); stop the map server before rebuilding its graph")
    shutil.rmtree(graph, ignore_errors=True)
    os.makedirs(os.path.join(routing, "logs"), exist_ok=True)
    say(f"=== build-routing: {os.path.basename(pbf)} -> {graph} (GraphHopper, -Xmx{a.xmx}) ===")
    run([find_java_or_die(), f"-Xmx{a.xmx}", f"-Ddw.graphhopper.datareader.file={pbf}",
         f"-Ddw.graphhopper.graph.location={graph}", "-jar", jar, "import", "config.yml"],
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
    a.platform, a.force, a.set, a.only, a.update = "all", False, "all", None, False
    cmd_setup(a)
    cmd_download(a)
    cmd_build_all(a)


# ==== make-drive =======================================================================================
DRIVE_SKIP_DIRS = {".git", ".venv", "build", "__pycache__", "drive-root", "logs"}
DRIVE_SKIP = re.compile(r"(\.bak-[^/\\]*|\.DS_Store|^\._.*|^download.*\.log|\.log|\.part|\.tmp|\.new\.pmtiles)$")


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
    s.set_defaults(fn=cmd_download)

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
    s = sub.add_parser("version", help="print the kit version")
    s.set_defaults(fn=lambda a: print(f"offline prepper kit {VERSION}"))

    a = p.parse_args()
    a.fn(a)


if __name__ == "__main__":
    main()
