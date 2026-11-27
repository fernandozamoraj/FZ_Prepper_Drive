# FZ Prepper Drive (offline prepper kit v1.18.0)

An offline "internet in a box" that runs on **Windows and Mac** computers with nothing installed, from a folder
or a USB drive: an offline **library** (Wikipedia and more), the **Holy Bible (KJV)**, a **whole-US street map with
driving directions**, **PDF survival/medical guides**, and optional **books, audiobooks, movies and a software
center**, all on one Home page (http://localhost:8000) that phones
on the same Wi-Fi can open too.

**This repository holds only the code.** The content (libraries, maps, PDFs, routing data) and the programs it uses
are downloaded and built by the scripts below.

## Quick start

### 1. Get the code

```bash
git clone https://github.com/fernandozamoraj/FZ_Prepper_Drive.git offline-prepper-kit
```

No git? On the GitHub page click **Code → Download ZIP** and unzip it. Then open a terminal in that folder:
- **Mac:** Terminal, then `cd` into the folder. Commands start with `./kit.sh`.
- **Windows:** open the folder in File Explorer, type `cmd` in the address bar and press Enter. Commands start with `kit.bat`.

Nothing else needs to be installed first: the first command downloads a portable Python (~30 MB) by itself.
Every command can be stopped and run again; it skips what's finished and resumes downloads.

### 2. Install: pick one

| Option | What you get | Download / disk | Time | Mac | Windows |
|---|---|---|---|---|---|
| **A. Everything** | library + Bible + PDF guides + US map with directions | ~160 GB (+~20 GB build files) | a day or more | `./kit.sh install all` | `kit.bat install all` |
| **B. Wiki only** | offline library (Wikipedia, WikiMed, iFixit, Wikivoyage, Stack Exchange, survival, programming docs) + Bible | ~140 GB | most of a day | `./kit.sh install wiki` | `kit.bat install wiki` |
| **B2. Wikipedia only** | just English Wikipedia + Bible | ~120 GB | most of a day | `./kit.sh install wiki --only wikipedia_en_all` | `kit.bat install wiki --only wikipedia_en_all` |
| **C. Maps only** | whole-US map, driving directions, town search | ~20 GB (+~15 GB build files); **24 GB RAM** | 3–6 hours | `./kit.sh install maps` | `kit.bat install maps` |
| **C2. Maps, one state** (quick try) | the same for one state, e.g. Texas | small | minutes | `./kit.sh install maps --state texas` | `kit.bat install maps --state texas` |

You can add more later: e.g. after **C**, run `install wiki` to add the library. State names are Geofabrik's
(`texas`, `new-mexico`, `north-carolina`, ...). Wiki and maps installs fetch programs for **this** computer only;
`install all` fetches them for Windows **and** Mac so the folder or drive runs on both.
`regenerate-all.sh` / `regenerate-all.bat` do the same as `install all`.

The window names each step ("step 4 of 6: map") and the map builds print their progress as they go. If a step stops
(an error, Ctrl+C, the computer went to sleep), the last lines say which step and the exact command to carry on;
finished parts are kept. A download that fails doesn't stop the install: the end says how many to retry.
Turn off sleep while it runs (Windows: Settings → System → Power).

### 3. Run it

| Mac | Windows |
|---|---|
| `./kit.sh start` | `kit.bat start` |

Your browser opens the **Home page** (http://localhost:8000) with search, the library (port 8080), the Bible, the map (port 8090) and
your own **Family emergency page**; parts you didn't install show as not running. Keep the window open while you use it;
**Ctrl+C** or closing the window stops everything. Phones and tablets on the same Wi-Fi use the address it prints
(e.g. `http://192.168.1.20:8000`). If another program already uses port 8080 or 8090, the library or map moves to the next
free port (the window says which) and the Home page links follow; start from the Home page and you never need to know.

### 4. Optional: put it on a USB drive

Format a 256 GB+ drive as **exFAT** (see below), then `./make-drive.sh /Volumes/NAME` (Mac) or
`make-drive.bat E:\` (Windows). On the drive, anyone can double-click `Start Prepper Kit (Windows).bat` or
`Start Prepper Kit (Mac).command`; `HOW TO START.html` explains it in plain words.

## Books, audiobooks, movies, software (optional modules)

These are **not** part of `install all`: you pick what you want. Each has its own page on the Home page
(**Books**, **Movies**, **Software** in the header bar); a module you haven't installed shows how to add it.
Examples are for a Mac (`./kit.sh`); on Windows type `kit.bat` instead.

**Easiest: a menu.** Run the module's name alone, then type numbers, categories or keywords:

```bash
./kit.sh books
```
```bash
./kit.sh movies
```
```bash
./kit.sh software
```

**Or say exactly what you want** with `get`. Words can be a **category**, a **group**, an **id**, or any
**keyword** from the title or author (quote a phrase). `list` shows everything (✓ = downloaded); `--dry-run` shows
what `get` would fetch without downloading.

| You want | Command |
|---|---|
| see every book and its id | `./kit.sh books list` |
| all math books | `./kit.sh books get math` |
| nursing + Calculus 1 + Dracula | `./kit.sh books get nursing calculus-1 dracula` |
| a book by keyword or phrase | `./kit.sh books get "think python" austen` |
| all textbooks / all fiction / everything | `./kit.sh books get textbooks` · `books get fiction` · `books get all` |
| novels **with their audiobooks** (~8 GB of MP3) | `./kit.sh books get fiction --audio` |
| only the audiobook | `./kit.sh books get treasure-island --audio-only` |
| PDF first instead of EPUB, or both | `./kit.sh books get sicp --format pdf` · `--format both` |
| every book, text only (~3.5 GB; Biology alone is 400 MB) | `./kit.sh install books` |
| all comedies and the open movies | `./kit.sh movies get comedy open-movies` |
| films by keyword | `./kit.sh movies get "sherlock holmes" nosferatu` |
| all 40 films (~17 GB) | `./kit.sh install movies` |
| another free film from archive.org | `./kit.sh movies add https://archive.org/details/TheStranger_0 --category mystery` |
| a film from a direct video link | `./kit.sh movies add https://example.org/film.mp4 --title "My Film"` |
| VLC and Calibre for every system | `./kit.sh software get vlc calibre` |
| everything for Windows only | `./kit.sh software get all --os windows` |
| e-book readers for this computer | `./kit.sh software get ebook --os current` |
| all programs, all systems (~3.4 GB) | `./kit.sh install software` |
| **update** everything you have to the newest versions | `./kit.sh software update` |
| only see what's out of date (downloads nothing) | `./kit.sh software check` |

**Books** (63, saved in `books/<category>/`): EPUB first, PDF when a book has no EPUB (`--format` changes that).

| Category (word) | Books | Source, format |
|---|---|---|
| `math` | Prealgebra, Elementary/Intermediate/College Algebra, Precalculus, Calculus Vol 1–3, Introductory Statistics, Contemporary Mathematics | OpenStax, PDF |
| `nursing` | Fundamentals of Nursing, Pharmacology, Maternal-Newborn, Psychiatric-Mental Health, Nutrition for Nurses | OpenStax, PDF |
| `science` | Biology, Chemistry, College Physics, University Physics Vol 1–3 | OpenStax, PDF |
| `programming` | Intro to Python Programming (OpenStax), Think Python, Think Java, Open Data Structures (Python, Java), Operating Systems: Three Easy Pieces (chapter PDFs), SICP (EPUB), Pro Git (EPUB), The Rust Programming Language (Kiwix library: opens in the Library) | various |
| `business` | Principles of Economics, Management, Finance, Financial Accounting; Entrepreneurship; Business Ethics; Business Law I | OpenStax, PDF |
| `history` | U.S. History, World History Vol 1–2, Intro to Philosophy, American Government, Intro to Anthropology | OpenStax, PDF |
| `adventure` `romance` `mystery` `scifi` (group `fiction`) | Monte Cristo, Three Musketeers, Treasure Island, Robinson Crusoe, The Lost World, King Solomon's Mines · Pride and Prejudice, Sense and Sensibility, Jane Eyre, Persuasion, North and South · Adventures of Sherlock Holmes, Hound of the Baskervilles, The Moonstone, Mysterious Affair at Styles · Time Machine, War of the Worlds, Frankenstein, Dracula, Journey to the Centre of the Earth | Project Gutenberg EPUB; LibriVox MP3 audiobook for all but *Styles* (LibriVox has none) |

Novels are Gutenberg's illustrated EPUBs (about 165 MB for all 20) from the gutenberg.pglaf.org mirror, which can
be slow (about 100 KB/s): allow half an hour for all of them. OpenStax books are always the newest edition (looked up on openstax.org when you download). OpenStax has no EPUBs.
Audiobooks go to `audiobooks/<category>/` and play on the Books page (it remembers where you stopped on each device).

**Movies** (40, saved in `movies/<category>/`, ~17 GB in all, 35 MB to 770 MB each): categories `comedy`, `drama`,
`mystery`, `adventure`, `horror` (public domain classics from the Internet Archive) and `open-movies` (Blender Studio
and Sita Sings the Blues, Creative Commons). The Movies page streams them to any phone, tablet or computer on the Wi-Fi
(with seeking and resume) or downloads them. To add your own, see **How to add more movies** on that page:
`movies add` for archive.org or a direct link, or just copy video files into `movies/my-movies/`.

**Software** (saved in `software/<windows|mac|linux>/<program>/`, always the newest release): official releases
only, straight from each project (no SourceForge or download portals, so no bundled adware), checked against the
publisher's checksum where one exists (shown as **✓ verified** on the page). VLC, mpv (MPlayer's maintained successor;
MPlayer itself ships no official Windows or Mac programs), Calibre, SumatraPDF (Windows), Thorium Reader,
7-Zip, Firefox, RetroArch (with a cores pack for Windows and Linux) and Notepad++ (Windows). Where a program has no
download for a system (e.g. VLC on Linux), the page says how to get it. Ids: `vlc mplayer mpv calibre sumatrapdf thorium
7zip firefox retroarch notepadpp`; keywords like `video`, `ebook`, `editor` work too.

**Keeping software up to date:** run `./kit.sh software update` now and then while you have internet. It asks each
publisher for its newest release, downloads only what changed (checksum-checked like the first time) and removes the
old version. `software check` just lists what's behind. The Software page (and its Home page card) warns when a program
hasn't been checked for updates in more than **4 months**, and shows the command to run.

To add a book, film or program to the lists, add a line to `bin/catalog.py` (its top comment explains the fields).

### Your own movies, books and audiobooks (Settings page)
Open **⚙️ Settings** in the header bar (`http://localhost:8000/settings`) on the computer that runs the kit, and add a
folder for Movies or for Books (type the path or **Browse…**). The kit remembers them in `kit-settings.json` and looks
through them every time it starts; they show up on the Movies and Books pages for every device on the Wi-Fi.
Phones can see the list but can't change it. Press **Look again** after adding files.

### Your own documents (Add a document, Books page)
On the **📕 Books** page, **📤 Add a document** uploads PDFs, e-books (EPUB, MOBI, AZW3, DOCX…) and single-file
audiobooks from any phone or computer on the Wi-Fi, into a category, with an optional title and your name. They are
copied into `uploads/<category>/` in the kit (so they go to the thumb drive with `make-drive`) and listed at the top of
the Books page. Only the computer that runs the kit can remove one (it goes to `uploads/.trash`). You can also copy
files into `uploads/survival/`, `uploads/medical/`… by hand. Limit 1 GB a file. Test: `python3 tests/test_uploads.py`.

### Sharing the kit with phones
The Home page shows **📶 Share this kit** with the address other devices on the same Wi-Fi open (for example
`http://192.168.1.20:8000`) and a Copy button. No Wi-Fi (power out)? A small travel router run from a power bank makes
one: see the Supplies page.

### Emergency supplies (checklist, buying plan, water, storage)
Open **🧰 Supplies** in the header bar (`http://localhost:8000/supplies`): 85 things to have for outages, storms, floods
and evacuations, from water and flashlights to a power station, ham radio and a portable travel router for the kit,
each with why, what to look for, a rough price and how to store it. Set the number of people and a monthly budget;
check off what you have (✕ for what your home doesn't need) and the **Buying plan** tab spreads the rest over the
months, cheapest life-savers first. Also a **Water calculator** and **Storing it** tips. Checkmarks are shared by
every device and kept in `family/supplies.json`. To change the list, edit `home/supplies-data.js` (its top comment
explains the fields) and run `python3 tests/test_supplies.py`.

### Family emergency page (your own information, locked)
Open **👪 Family** in the header bar (`http://localhost:8000/family`). The first time, on the computer that runs the kit,
choose a password (three or four random words work well) and fill in what you can: emergency contacts (put an
out-of-area contact first), meeting places (with a map location, they open on the offline map with directions),
everyone's allergies, medicines and blood type, doctors and pharmacy, insurance numbers, where the shut-offs are, pets,
where the important documents are, and notes. **Print** gives a paper copy; keep one with the drive.

- **Locked in the browser.** The page encrypts everything before it leaves the browser; the kit stores only the locked
  file `family/family.enc.json` and never sees the password. Lose the drive, and nobody can read it without the
  password. Forget the password, and **nobody can recover it**, so write it down and keep it somewhere safe.
- **Phones too:** any device on the Wi-Fi can unlock, read and (with the password) edit it. It locks itself after 10
  minutes without use. Two devices editing at once: the second save is refused with a note to reload, not overwritten.
- **Earlier saves:** the last 5 are kept as `family/family.enc.json.1` … `.5` (still locked with the password they had).
- **Forgot the password?** On the computer that runs the kit: *Forgot the password? → Start over*. The old file is
  renamed (`family.enc.json.forgotten-DATE`), never deleted.
- **Never in git** (`.gitignore`), but **copied to the drive** by `make-drive`. If the page was changed on the drive
  later than on this computer, `make-drive` keeps the drive's copy and prints where to copy it back.
- Test: `python3 tests/test_family.py` (needs `node`).

## What you need (manual)

1. **Disk:** see the quick-start table (everything: about **160 GB** plus **~20 GB** of build files) (`build/`). Use an internal disk
   or a fast SSD; the map and routing builds do a lot of random reads and writes.
2. **Memory:** for the maps, **24 GB+ RAM** recommended (the library needs little). The map build uses a 14 GB Java heap and the routing build an 18 GB heap
   (lower them with `--xmx`, e.g. `kit.sh build-map --xmx 10g`; too low fails with OutOfMemoryError).
3. **Internet** for the downloads (Wikipedia alone is ~120 GB) and **time**: a day or more on a typical
   connection; the whole-US map takes ~1–3 h and the routing graph ~1–2 h on a recent machine.
4. **Intel Macs only:** `brew install osmium-tool` before `build-places` (the Python osmium package has no current
   Intel Mac build). Apple Silicon Macs and Windows need nothing extra.
5. **The USB drive** (256 GB or more) must be formatted **exFAT** so both Windows and Macs can read it and it can
   hold files over 4 GB. Formatting erases the drive:
   - Mac: Disk Utility → select the drive → Erase → Format **ExFAT**.
   - Windows: File Explorer → right-click the drive → Format… → File system **exFAT**.

## Commands

| Command | What it makes | Notes |
|---|---|---|
| `install all\|wiki\|maps` | the quick-start bundles above | `--only`, `--state`, `--platform current\|all` |
| `start` | runs the kit, opens the Home page | `--port` for another Home page port |
| `setup` | `runtime/` portable Python 3.12, Temurin Java 21 and kiwix-serve for **win-x64, mac-arm64 and mac-x64**; `bin/planetiler.jar`; `routing/graphhopper-web-11.1.jar`; `map-viewer/lib/` (MapLibre 4.7.1, pmtiles 3.2.1); `map-viewer/fonts/` (Noto Sans); map icons | ~1 GB. `--platform current` fetches only this computer's programs (a drive made that way runs only on this kind of computer). Checksums are verified. |
| `download` | `kiwix/*.zim` libraries, `guides/` PDFs | `--set core,programming,pdfs` (default: all three). `--only knots` for one item. Picks the newest edition on download.kiwix.org; keeps the one you have unless `--update`. Log: `download.log`. |
| `build-map` | `maps/us.pmtiles` (~11 GB, zoom 0–14) | Downloads `build/us.osm.pbf` (~12 GB, Geofabrik) first; Planetiler also downloads ~1.4 GB of water/boundary data into `build/sources`. `--refresh-osm` gets newer OSM data. |
| `build-routing` | `routing/graph-us/` (~8.5 GB) | GraphHopper car profile. Stop the kit's map server first (it uses the graph). |
| `build-places` | `map-viewer/places.json` (town search) | Every US city/town/village/hamlet with its state. |
| `build-bible` | `kiwix/bible_en_kjv_<yyyy-mm>.zim`, `home/kjv.json` | KJV text from eBible.org (public domain). |
| `build-all` | the four builds above | |
| `all` | same as `install all` | What `regenerate-all` runs. |
| `books [list\|get] [words]` | `books/`, `audiobooks/` | optional; menu when run alone. `--audio`, `--audio-only`, `--format epub\|pdf\|both`, `--dry-run` |
| `movies [list\|get\|add] [words]` | `movies/` | optional; `add <archive.org link or video URL>` with `--title`, `--year`, `--category` |
| `software [list\|get\|update\|check] [words]` | `software/<os>/` | optional; `--os windows,mac,linux\|current\|all` (default all); `update` = newest versions of what you have |
| `install books\|movies\|software [words]` | all of that module | not part of `install all`; `install books --audio` adds audiobooks |
| `make-drive DRIVE` | copies the kit to `DRIVE/offline-prepper-kit` plus the launchers at the drive's top | `--no-libraries` skips the big `.zim` files. Only changed files are copied. |

## More on running

- **From the USB drive (anyone):** double-click `Start Prepper Kit (Windows).bat` or `Start Prepper Kit (Mac).command`
  at the top of the drive. The browser opens the Home page. `HOW TO START.html` explains it in plain words,
  including the one-time security prompts (Mac: right-click → Open; Windows: allow the firewall prompt for phones).
- **From the folder:** `kit.sh start` / `kit.bat start` (it runs `bin/intranet.py --open` with the kit's Python).
  Hub on :8000, library on :8080, map on :8090. Test on other ports: `PREPPER_KIT_TEST_PORTS=9000,9080,9090`.

## Folder layout

| Path | In git? | What |
|---|---|---|
| `kit.sh`, `kit.bat`, `regenerate-all.*`, `make-drive.*` | yes | entry points (wrappers around `scripts/kit.py`) |
| `scripts/kit.py`, `scripts/places_extract.py` | yes | all download/build logic, cross-platform Python |
| `bin/intranet.py`, `bin/serve-maps.py`, `bin/kitplatform.py` | yes | the kit's servers (hub, map + directions proxy, program finder) |
| `bin/catalog.py` | yes | the lists of optional books, audiobooks, movies and software |
| `home/books.html`, `home/movies.html`, `home/movies-add.html`, `home/software.html`, `home/media.css`, `home/media.js` | yes | Books, Movies (+ how to add more) and Software pages |
| `books/`, `audiobooks/`, `movies/`, `software/` | no | optional modules: downloaded |
| `home/family.html`, `home/family-crypto.js`, `tests/test_family.py` | yes | Family emergency page, its lock, its test |
| `tests/test_uploads.py` | yes | test for Add a document and the share address |
| `home/supplies.html`, `home/supplies-data.js`, `tests/test_supplies.py` | yes | Supplies page, its item list, its test |
| `uploads/` | no | documents added on the Books page (copied to the drive, never to git; `.trash` stays here) |
| `family/` | no | your locked Family page and its earlier saves, and the Supplies checkmarks (copied to the drive, never to git) |
| `home/`, `map-viewer/index.html`, `map-viewer/style/style.json` | yes | web pages: hub, Bible search, library home page, header bar, map |
| `routing/config.yml`, `routing/make_places.py` | yes | GraphHopper config, town list builder |
| `bible/build-bible.py` | yes | builds the Bible library |
| `drive-root/` | yes | launchers + `HOW TO START.html`, copied to the top of the drive |
| `download*.sh`, `build/build-map.sh`, `routing/build-*.sh`, `bible/build-bible.sh`, `serve.sh`, `routing/start-router.sh` | yes | older Mac commands, now thin wrappers (kept for habits) |
| `kiwix/`, `maps/`, `guides/`, `routing/graph-us/`, `map-viewer/places.json`, `home/kjv.json` | no | content: downloaded or built |
| `runtime/`, `bin/*.jar`, `bin/kiwix-*`, `routing/*.jar`, `map-viewer/lib/`, `map-viewer/fonts/`, `map-viewer/style/sprite*` | no | third-party programs: `setup` |
| `build/` | no | OSM data and build scratch; keep `build/us.osm.pbf` if you want to rebuild routing or places later |

The `.gitignore` is a whitelist: everything is ignored unless listed, so content can't be committed by accident.

## Status and what was tested

- Tested on macOS (Apple Silicon): `install wiki` (one small library) and `install maps --state delaware` from fresh clones, then `start`; also fresh clone → `setup` (all three platforms) → small `download` → `build-map`,
  `build-routing`, `build-places` (both osmium-tool and pyosmium paths), `build-bible` on the Arkansas extract →
  `make-drive` → hub, library, map, directions and Bible all working from the rebuilt files.
- **Windows scripts (`*.bat`) are written for Windows 10/11 but have not been run on Windows yet.** The build logic
  is the same Python on both systems; the `.bat` files only bootstrap Python and call it. Reports welcome.
- Full-size whole-US builds were done with the earlier Mac-only scripts (same tools and settings).

## Licenses

The code in this repository is MIT licensed (see `LICENSE`). Downloaded content and programs keep their own licenses:
OpenStreetMap data © OpenStreetMap contributors (ODbL); map tiles schema © OpenMapTiles; Wikipedia, Wikivoyage,
Wikibooks and Stack Exchange content CC BY-SA; Kiwix tools GPL-3.0; GraphHopper Apache-2.0; Planetiler Apache-2.0;
MapLibre BSD-3-Clause; OSM Bright style BSD/CC-BY; Noto fonts OFL; Hesperian books under Hesperian's terms;
US government manuals public domain; KJV text public domain (eBible.org). Optional modules: OpenStax books CC BY-NC-SA 4.0;
Project Gutenberg and LibriVox public domain; other books as listed on the Books page and in `books/ABOUT THESE BOOKS.txt`;
films public domain or Creative Commons (shown with each); programs under their own open-source licenses (shown with each).

More detail: `docs/user-guide.md` (how to use each part, version notes), `CHANGELOG.md`, `DECISIONS.md`.
