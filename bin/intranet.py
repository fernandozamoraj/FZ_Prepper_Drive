#!/usr/bin/env python3
"""intranet: one home page for the whole offline prepper kit, plus the servers it links to (v1.20.1).

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
import shutil
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

VERSION = "1.20.1"  # sent in /ports.json: nav.js tells people to restart when the running hub is older than the files
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
FILE_ROOTS = {"books", "audiobooks", "movies", "software", "extra", "uploads"}
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


# ---- Family page (home/family.html): one encrypted file, locked and unlocked in the browser -------------------------
FAMILY_DIR = os.path.join(KIT, "family")
FAMILY_FILE = os.path.join(FAMILY_DIR, "family.enc.json")
FAMILY_KEEP = 5  # earlier saves kept as family.enc.json.1 (newest) ... .5, all still encrypted
FAMILY_LOCK = threading.Lock()
B64 = re.compile(r"^[A-Za-z0-9+/]*={0,2}$")


def family_load():
    try:
        with open(FAMILY_FILE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) and isinstance(d.get("file"), dict) else None
    except (OSError, ValueError):
        return None


def family_json(local):
    d = family_load()
    out = {"local": local, "exists": bool(d), "file_path": FAMILY_FILE}
    if d:
        out |= {"file": {k: v for k, v in d["file"].items() if k != "verifier"}, "rev": d.get("rev", 0),
                "saved": d.get("saved")}
    return out


def family_file_ok(f):
    """The shape of a locked file sent by family.html (the server can't read it, only check it looks right)."""
    try:
        return (f["format"] == "fz-family-1" and isinstance(f["iter"], int) and 100000 <= f["iter"] <= 10_000_000
                and all(isinstance(f[k], str) and B64.match(f[k]) for k in ("salt", "nonce", "ct", "tag"))
                and len(f["salt"]) == 24 and len(f["nonce"]) == 24 and len(f["tag"]) == 44 and len(f["ct"]) <= 8 << 20
                and re.fullmatch(r"[0-9a-f]{64}", f["verifier"]) is not None
                and set(f) == {"format", "iter", "salt", "nonce", "ct", "tag", "verifier"})
    except (KeyError, TypeError):
        return False


def family_proof_ok(d, proof):
    import hashlib
    import hmac
    if not isinstance(proof, str) or not re.fullmatch(r"[0-9a-f]{64}", proof):
        return False
    return hmac.compare_digest(hashlib.sha256(bytes.fromhex(proof)).hexdigest(), d["file"]["verifier"])


def family_write(d):
    """Save atomically, keeping the earlier saves (still encrypted) as .1 ... .5."""
    os.makedirs(FAMILY_DIR, exist_ok=True)
    if os.path.exists(FAMILY_FILE):
        for n in range(FAMILY_KEEP, 1, -1):
            if os.path.exists(f"{FAMILY_FILE}.{n - 1}"):
                os.replace(f"{FAMILY_FILE}.{n - 1}", f"{FAMILY_FILE}.{n}")
        os.replace(FAMILY_FILE, FAMILY_FILE + ".1")
    tmp = FAMILY_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f)
    os.replace(tmp, FAMILY_FILE)


# ---- Supplies page (home/supplies.html): household checkmarks, shared by every device -------------------------------
SUPPLIES_FILE = os.path.join(FAMILY_DIR, "supplies.json")  # next to the Family page: personal, copied to the drive, not git
SUPPLY_ID = re.compile(r"^[a-z0-9-]{1,40}$")


def supplies_load():
    try:
        with open(SUPPLIES_FILE, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        d = {}
    items = d.get("items") if isinstance(d.get("items"), dict) else {}
    return {"people": d.get("people") if isinstance(d.get("people"), int) else 4,
            "budget": d.get("budget") if isinstance(d.get("budget"), int) else 100,
            "items": {k: v for k, v in items.items() if SUPPLY_ID.match(str(k)) and v in ("have", "skip")},
            "saved": d.get("saved")}


def supplies_update(body):
    """Merge one change (a checkmark, people or budget) so two phones ticking different items never undo each other."""
    d = supplies_load()
    if "people" in body:
        if isinstance(body["people"], bool) or not isinstance(body["people"], int) or not 1 <= body["people"] <= 30:
            raise ValueError("People must be 1 to 30.")
        d["people"] = body["people"]
    if "budget" in body:
        if isinstance(body["budget"], bool) or not isinstance(body["budget"], int) or not 1 <= body["budget"] <= 100000:
            raise ValueError("Budget must be $1 to $100,000.")
        d["budget"] = body["budget"]
    items = body.get("items", {})
    if not isinstance(items, dict) or len(items) > 500:
        raise ValueError("Bad request.")
    for k, v in items.items():
        if not SUPPLY_ID.match(str(k)) or v not in ("have", "skip", ""):
            raise ValueError("Bad request.")
        if v:
            d["items"][k] = v
        else:
            d["items"].pop(k, None)
    d["saved"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    os.makedirs(FAMILY_DIR, exist_ok=True)
    tmp = SUPPLIES_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1)
    os.replace(tmp, SUPPLIES_FILE)
    return d


# ---- Uploaded documents (Books page, "Add a document"): anyone on the Wi-Fi may add, only this computer may delete --
UPLOADS = os.path.join(KIT, "uploads")              # uploads/<category>/<file>; files copied there by hand show up too
UPLOAD_INDEX = os.path.join(UPLOADS, ".index.json")  # titles, who added it and when (hidden: never served)
UPLOAD_CATS = {"survival": "Survival and preparedness", "medical": "Medical and first aid",
               "food": "Food, water and gardening", "repair": "Repair, tools and building",
               "radio": "Radio and communication", "manuals": "Manuals for our gear", "faith": "Faith",
               "kids": "Kids and school", "other": "Other"}
UPLOAD_EXT = (".pdf", ".epub", ".mobi", ".azw3", ".fb2", ".djvu", ".cbz", ".cbr", ".txt", ".rtf", ".docx", ".m4b", ".mp3")
UPLOAD_MAX = 1 << 30           # 1 GB a file
UPLOAD_KEEP_FREE = 2 << 30     # never fill the disk: keep 2 GB free
UPLOAD_LOCK = threading.Lock()
# The file has to start like what its name says (a renamed web page or program is refused)
UPLOAD_MAGIC = {".pdf": [b"%PDF-"], ".epub": [b"PK\x03\x04"], ".docx": [b"PK\x03\x04"], ".cbz": [b"PK\x03\x04"],
                ".djvu": [b"AT&TFORM"], ".cbr": [b"Rar!"], ".rtf": [b"{\\rtf"], ".mobi": None, ".azw3": None,
                ".fb2": None, ".txt": None, ".m4b": None, ".mp3": None}
MOVIE_UPLOAD_MAX = 8 << 30     # 8 GB a video (a long HD film); the kit's drive is exFAT, which has no 4 GB limit
MP4_BOXES = (b"ftyp", b"moov", b"mdat", b"wide", b"free", b"skip", b"pnot")


def looks_like(ext, first):
    """Does the start of the file match its extension? (Unknown or text-like types aren't checked.)"""
    if ext in (".mp4", ".m4v", ".mov"):
        return first[4:8] in MP4_BOXES
    if ext in (".webm", ".mkv"):
        return first.startswith(b"\x1a\x45\xdf\xa3")
    if ext == ".avi":
        return first[:4] == b"RIFF" and first[8:12] == b"AVI "
    if ext == ".ogv":
        return first.startswith(b"OggS")
    magic = UPLOAD_MAGIC.get(ext)
    return not magic or any(first.startswith(m) for m in magic)


def upload_kind(kind):
    """Where each kind of upload goes. Worked out on each call (tests point the folders elsewhere)."""
    if kind == "movies":  # into movies/<category>/, where the Movies page already lists videos added by hand
        return {"root": catalog.MOVIES_DIR, "index": os.path.join(catalog.MOVIES_DIR, ".uploads.json"),
                "cats": {k: v for k, v in catalog.MOVIE_CATEGORIES.items() if k != "open-movies"},
                "ext": catalog.VIDEO_EXT, "max": MOVIE_UPLOAD_MAX, "what": "Videos", "noun": "video"}
    return {"root": UPLOADS, "index": UPLOAD_INDEX, "cats": UPLOAD_CATS, "ext": UPLOAD_EXT, "max": UPLOAD_MAX,
            "what": "Books and documents", "noun": "document"}


def upload_index(path=None):
    try:
        with open(path or UPLOAD_INDEX, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def upload_index_save(d, path=None):
    path = path or UPLOAD_INDEX
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1, ensure_ascii=False)
    os.replace(path + ".tmp", path)


def clean_name(name):
    """A safe file name from whatever a phone sends: no folders, no hidden files, no characters Windows refuses."""
    name = os.path.basename(str(name).replace("\\", "/"))
    name = re.sub(r'[\x00-\x1f<>:"/\\|?*]', "_", name).strip().strip(".")
    stem, ext = os.path.splitext(name)
    stem = stem[:120].strip() or "document"
    return stem + ext.lower()


def clean_text(s, n):
    return re.sub(r"[\x00-\x1f]", " ", str(s or "")).strip()[:n]


def uploads_json(local):
    idx, cats = upload_index(), []
    for cid, cname in UPLOAD_CATS.items():
        d = os.path.join(UPLOADS, cid)
        files = sorted((f for f in kitplatform.visible_files(d, "") if f.lower().endswith(UPLOAD_EXT)
                        and os.path.isfile(os.path.join(d, f))), key=natural)
        items = []
        for f in files:
            p, key = os.path.join(d, f), f"{cid}/{f}"
            info = idx.get(key, {})
            items.append({"key": key, "title": info.get("title") or os.path.splitext(f)[0].replace("_", " "),
                          "by": info.get("by", ""), "added": info.get("added") or
                          time.strftime("%Y-%m-%d", time.localtime(os.path.getmtime(p))),
                          "ext": os.path.splitext(f)[1][1:].lower(), "mb": round(os.path.getsize(p) / 1e6, 1),
                          "url": "/files/uploads/" + urllib.parse.quote(key)})
        cats.append({"id": cid, "name": cname, "items": items})
    return {"local": local, "cats": cats, "ext": UPLOAD_EXT, "max_mb": UPLOAD_MAX >> 20, "folder": UPLOADS,
            "kit_name": os.path.basename(KIT)}


DROP_NOTE = """HOW TO ADD FILES (offline prepper kit)

Copy {what} into the folder that fits, here in "{here}":
{folders}

They show up on the {page} page the next time it is opened or reloaded: no restart needed.
Files must be inside one of these folders (not loose here), and one of these kinds:
{ext}

You can also add them one at a time from any phone or computer on the Wi-Fi with "{button}" on the {page} page.
"""


def make_drop_folders():
    """Category folders for the Books and Movies pages, plus a how-to note in each place, so people copying files
    straight onto the drive (Finder, File Explorer) see where they go. Never fails the start (a read-only drive)."""
    for kind, page, button, what in (("docs", "Books", "Add a document", "PDFs and e-books"),
                                     ("movies", "Movies", "Add a video", "videos")):
        K = upload_kind(kind)
        try:
            for cat in K["cats"]:
                os.makedirs(os.path.join(K["root"], cat), exist_ok=True)
            note = os.path.join(K["root"], "HOW TO ADD FILES.txt")
            if not os.path.exists(note):
                with open(note, "w", encoding="utf-8", newline="\r\n") as f:  # Windows line ends: Notepad reads it too
                    f.write(DROP_NOTE.format(what=what, here=os.path.basename(K["root"]), page=page, button=button,
                                             folders="\n".join(f"  {c:<12} {n}" for c, n in K["cats"].items()),
                                             ext=", ".join(e[1:].upper() for e in K["ext"])))
        except OSError:
            pass


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


def movies_json(local=False):
    movies, known = catalog.all_movies(), set()
    up = upload_kind("movies")
    idx = upload_index(up["index"])
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
            rel = os.path.relpath(p, catalog.MOVIES_DIR).replace(os.sep, "/")
            cat = rel.split("/")[0] if "/" in rel else ""
            cat = cat if cat in catalog.MOVIE_CATEGORIES else "my-movies"
            info = idx.get(rel, {})
            who = f"added by {info['by']}" if info.get("by") else "added by you"
            removable = rel.count("/") == 1 and rel.split("/")[0] in up["cats"]  # uploaded or copied into movies/<cat>/
            out.setdefault(cat, []).append({"id": None, "title": info.get("title") or os.path.splitext(f)[0].replace("_", " "),
                                            "year": None, "minutes": None,
                                            "license": who + (f" · {info['added']}" if info.get("added") else ""),
                                            "url": file_url(p), "mb": round(os.path.getsize(p) / 1e6),
                                            "key": rel if removable else None})
    cats = [{"id": c, "name": catalog.MOVIE_CATEGORIES.get(c, c), "movies": out[c]} for c in out if out[c]]
    for n, f in enumerate(FOLDERS["movies"]):  # your own folders (Settings page)
        cats.append({"id": f"folder-{n}", "name": os.path.basename(f["path"].rstrip("\\/")) or f["path"], "folder": f["path"],
                     "found": f["ok"], "extra": True,
                     "movies": [{"id": None, "title": m["title"], "year": None, "minutes": None,
                                 "license": m["where"] or "", "url": extra_url("movies", n, m["rel"]),
                                 "mb": round(m["mb"])} for m in f["items"]]})
    return {"cmd": KIT_CMD, "folder": catalog.MOVIES_DIR, "kit_name": os.path.basename(KIT), "categories": cats, "local": local,
            "upload": {"cats": up["cats"], "ext": up["ext"], "max_mb": up["max"] >> 20}}


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


# Sent with the reader page. Books are shown in same-origin frames that foliate-js must let run scripts (a WebKit bug),
# and frames made from blob: URLs inherit this policy, so a script inside an e-book (an upload, say) never runs.
READER_CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' blob:; img-src 'self' blob: data:; "
              "font-src 'self' blob: data:; media-src 'self' blob:; frame-src 'self' blob:; connect-src 'self'; "
              "object-src 'none'; base-uri 'none'; form-action 'none'")


class Handler(http.server.SimpleHTTPRequestHandler):
    csp = None

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=KIT, **kw)

    def end_headers(self):
        if self.csp:
            self.send_header("Content-Security-Policy", self.csp)
            self.send_header("X-Content-Type-Options", "nosniff")
            self.csp = None
        super().end_headers()

    def do_GET(self):
        path = urllib.parse.unquote(self.path.split("?", 1)[0])
        if path == "/ports.json":  # read by nav.js on every page (library and map are other origins)
            return self.send_json({"hub": self.server.server_address[1], **PORTS, "version": VERSION}, cors=True)
        if path == "/share.json":  # the Home page's "Share this kit" box: the address phones on the Wi-Fi use
            ip, port = lan_ip(), self.server.server_address[1]
            return self.send_json({"ip": ip, "port": port, "url": f"http://{ip}:{port}/" if ip else None})
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
        if path == "/family.json":
            return self.send_json(family_json(self.is_local()))
        pages = {"/books": "books.html", "/movies": "movies.html", "/movies/add": "movies-add.html",
                 "/software": "software.html", "/settings": "settings.html", "/media.css": "media.css", "/media.js": "media.js",
                 "/family": "family.html", "/family-crypto.js": "family-crypto.js",
                 "/supplies": "supplies.html", "/supplies-data.js": "supplies-data.js"}
        if path == "/supplies.json":
            return self.send_json(supplies_load())
        if path in ("/reader", "/reader/"):  # e-book reader: only the kit's own scripts may run (books can carry scripts)
            self.csp = READER_CSP
            self.path = "/home/reader.html"
            return super().do_GET()
        if path in ("/reader.js", "/reader.css"):
            self.path = "/home" + path
            return super().do_GET()
        if path.startswith("/reader-lib/"):  # foliate-js, installed by `kit setup-reader` (not in git)
            if not re.fullmatch(r"/reader-lib/(vendor/)?[a-z0-9-]+\.js", path):
                return self.not_found()
            self.path = "/home" + path
            return super().do_GET()
        if path == "/uploads.json":
            return self.send_json(uploads_json(self.is_local()))
        if path.rstrip("/") in pages:
            self.path = "/home/" + pages[path.rstrip("/")]
            return super().do_GET()
        if path == "/movies.json":
            return self.send_json(movies_json(self.is_local()))
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
            if parts[0] == "uploads":
                if len(parts) != 3 or parts[1] not in UPLOAD_CATS or not parts[2].lower().endswith(UPLOAD_EXT):
                    return self.not_found()  # only the documents the Books page lists
                path = os.path.join(UPLOADS, parts[1], parts[2])
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
        self.send_header("X-Content-Type-Options", "nosniff")  # an uploaded .txt is shown as text, never run as a page
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
        if path not in ("/settings.json", "/settings/rescan", "/family.json", "/family/forget", "/supplies.json",
                        "/uploads", "/uploads/delete"):
            return self.not_found()
        origin = urllib.parse.urlsplit(self.headers.get("Origin") or "")
        if origin.netloc and ((origin.port or 80) != self.server.server_address[1] or
                              origin.hostname not in ("localhost", "127.0.0.1", "::1", lan_ip())):
            return self.send_error_json(403, "Changes must come from the kit's own pages.")
        if path.startswith("/family"):
            return self.post_family(path)
        if path.startswith("/uploads"):
            return self.post_upload(path)
        if path == "/supplies.json":  # anyone on the home Wi-Fi may tick items off (it's a household list)
            if not (self.headers.get("Content-Type") or "").startswith("application/json"):
                return self.send_error_json(415, "Send JSON.")
            try:
                body = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length") or 0), 1 << 16)) or b"{}")
                assert isinstance(body, dict)
                with FAMILY_LOCK:
                    return self.send_json(supplies_update(body))
            except (ValueError, AssertionError) as e:
                return self.send_error_json(400, str(e) if isinstance(e, ValueError) and "must" in str(e) else "Bad request.")
            except OSError as e:
                return self.send_error_json(500, f"Could not save {SUPPLIES_FILE}: {e.strerror or e}")
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

    def post_upload(self, path):
        """/uploads?kind=&cat=&name=&title=&by= with the file as the request body (any device on the Wi-Fi).
        kind "docs" (default, Books page: uploads/<cat>/) or "movies" (Movies page: movies/<cat>/).
        /uploads/delete {"kind", "key": "cat/file"}: this computer only; the file goes to <folder>/.trash, not deleted."""
        def refuse(code, msg):
            self.close_connection = True  # don't read a big body we are refusing
            return self.send_error_json(code, msg)
        if self.headers.get("X-Kit-Upload") != "1":  # a header other web sites can't send without asking first
            return refuse(403, "Uploads must come from the kit's own Books or Movies page.")
        q = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        arg = lambda k: q.get(k, [""])[0]  # noqa: E731
        if path == "/uploads/delete":
            try:
                body = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length") or 0), 4096)) or b"{}")
                K = upload_kind(body.get("kind"))
                key = body["key"]
                cat, name = key.split("/")
                assert cat in K["cats"] and name == clean_name(name) and name.lower().endswith(K["ext"])
            except (ValueError, KeyError, TypeError, AssertionError, AttributeError):
                return refuse(400, "Bad request.")
            if not self.is_local():
                return refuse(403, f"A {K['noun']} can only be removed on the computer that runs the kit.")
            src = os.path.join(K["root"], cat, name)
            with UPLOAD_LOCK:
                if not os.path.isfile(src):
                    return refuse(404, f"That {K['noun']} is not there any more.")
                os.makedirs(os.path.join(K["root"], ".trash"), exist_ok=True)
                os.replace(src, os.path.join(K["root"], ".trash", time.strftime("%Y%m%d-%H%M%S-") + name))
                idx = upload_index(K["index"])
                idx.pop(key, None)
                upload_index_save(idx, K["index"])
            return self.send_json(movies_json(True) if body.get("kind") == "movies" else uploads_json(True))
        kind = arg("kind") or "docs"
        if kind not in ("docs", "movies"):
            return refuse(400, "Bad request.")
        K = upload_kind(kind)
        cat, name = arg("cat"), clean_name(arg("name"))
        ext = os.path.splitext(name)[1]
        if cat not in K["cats"]:
            return refuse(400, "Pick a category.")
        if ext not in K["ext"]:
            return refuse(415, f"{ext or 'That kind of file'} can't be added here. {K['what']} only: "
                               + ", ".join(e[1:].upper() for e in K["ext"]) + ".")
        try:
            size = int(self.headers.get("Content-Length") or -1)
        except ValueError:
            size = -1
        if size <= 0:
            return refuse(411, "Empty file, or the browser didn't say how big it is.")
        if size > K["max"]:
            limit = K["max"] >> 20
            return refuse(413, f"Too big: the limit is {limit // 1024} GB a file." if limit >= 1024 else
                               f"Too big: the limit is {limit} MB a file.")
        os.makedirs(os.path.join(K["root"], cat), exist_ok=True)
        if shutil.disk_usage(K["root"]).free - size < UPLOAD_KEEP_FREE:
            return refuse(507, "Not enough free space on the kit's disk for this file.")
        tmp = os.path.join(K["root"], f".incoming-{threading.get_ident()}-{time.time_ns()}")
        try:
            left, first = size, b""
            with open(tmp, "wb") as f:
                while left > 0:
                    chunk = self.rfile.read(min(1 << 20, left))
                    if not chunk:
                        raise ConnectionError("the upload stopped part way")
                    if not first:
                        first = chunk[:16]
                    f.write(chunk)
                    left -= len(chunk)
            if not looks_like(ext, first):
                os.remove(tmp)
                return refuse(415, f"That file doesn't look like a real {ext[1:].upper()}.")
            with UPLOAD_LOCK:
                final, n = os.path.join(K["root"], cat, name), 2
                while os.path.exists(final):  # never replace someone else's file: "name (2).pdf"
                    final = os.path.join(K["root"], cat, f"{os.path.splitext(name)[0]} ({n}){ext}")
                    n += 1
                os.replace(tmp, final)
                key = f"{cat}/{os.path.basename(final)}"
                idx = upload_index(K["index"])
                idx[key] = {"title": clean_text(arg("title"), 200) or os.path.splitext(name)[0].replace("_", " "),
                            "by": clean_text(arg("by"), 60), "added": time.strftime("%Y-%m-%d")}
                upload_index_save(idx, K["index"])
        except (OSError, ConnectionError) as e:
            if os.path.exists(tmp):
                os.remove(tmp)
            return refuse(500, f"Could not save the file: {getattr(e, 'strerror', None) or e}")
        return self.send_json({"ok": True, "key": key, **(movies_json(self.is_local()) if kind == "movies"
                                                           else uploads_json(self.is_local()))})

    def post_family(self, path):
        """/family.json: save the locked file. The first one can only be made on the computer running the kit; after
        that any device may save (phones too) but must prove it knows the password (the write key, checked against the
        verifier in the saved file) and that it saw the newest save (rev). /family/forget: this computer only; the old
        file is renamed, never deleted, for "I forgot the password, start over"."""
        if not (self.headers.get("Content-Type") or "").startswith("application/json"):
            return self.send_error_json(415, "Send JSON.")
        try:
            body = json.loads(self.rfile.read(min(int(self.headers.get("Content-Length") or 0), 12 << 20)) or b"{}")
            assert isinstance(body, dict)
        except (ValueError, AssertionError):
            return self.send_error_json(400, "Bad request.")
        with FAMILY_LOCK:
            d = family_load()
            if path == "/family/forget":
                if not self.is_local():
                    return self.send_error_json(403, "Only the computer that runs the kit can start the Family page over.")
                if d:
                    os.replace(FAMILY_FILE, f"{FAMILY_FILE}.forgotten-{time.strftime('%Y%m%d-%H%M%S')}")
                return self.send_json(family_json(True))
            if not family_file_ok(body.get("file")):
                return self.send_error_json(400, "That doesn't look like a locked Family page.")
            if d is None:
                if not self.is_local():
                    return self.send_error_json(403, "Set up the Family page on the computer that runs the kit first.")
                rev = 1
            else:
                if not family_proof_ok(d, body.get("proof")):
                    return self.send_error_json(403, "The password doesn't match the saved Family page.")
                if body.get("rev") != d.get("rev", 0):
                    return self.send_error_json(409, "Someone saved the Family page on another device since you opened it. "
                                                     "Copy anything you typed, then reload the page.")
                rev = d.get("rev", 0) + 1
            saved = time.strftime("%Y-%m-%dT%H:%M:%S%z")
            try:
                family_write({"file": body["file"], "rev": rev, "saved": saved})
            except OSError as e:
                return self.send_error_json(500, f"Could not save {FAMILY_FILE}: {e.strerror or e}")
        return self.send_json({"ok": True, "rev": rev, "saved": saved})

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
    make_drop_folders()
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
