# Decisions: offline prepper kit

## 2026-11-25: GraphHopper for offline directions
- **Chosen:** GraphHopper 11.1 (single Java jar, reads the existing `build/us.osm.pbf`, Java 21 already installed for Planetiler).
- **Rejected:** OSRM (needs far more RAM for a US build than this 24 GB Mac has); Valhalla (harder macOS install, more moving parts).
- Car profile only, with contraction hierarchies: cross-country routes answer in milliseconds; walking/bike would enlarge the build.

## 2026-11-25: Router behind serve-maps.py
- The map page calls `/route` on its own server, which forwards to GraphHopper on 127.0.0.1.
  Phones need only port 8090, and the router is never exposed on the network directly.
- `serve-maps.py` starts the router itself (not `startmaps`), so the thumb-drive copy works the same way.

## 2026-11-25: Town search from OSM place nodes + state polygons
- No offline geocoder; a 6.5 MB `places.json` of city/town/village/hamlet nodes is searched in the browser.
- OSM place nodes rarely carry a state, so states come from point-in-polygon against OSM state
  boundaries (shapely, in `routing/.venv`). Alaska's outline is missing from the extract; places above 51°N fall back to AK.

## 2026-11-25: Highway numbers from path details
- OSM interstates usually have `ref` but no `name`, so GraphHopper merges the on-ramp and the whole
  highway into one nameless step. The page requests `street_ref` path details and appends
  "then follow I-40" to long steps whose distance is mostly on one numbered road.

## 2026-11-25: Custom Kiwix home page instead of Kiwix's own
- Kiwix's home-page search box only filters library *names*, so typing an article title ("Rocky") there finds nothing.
  The custom page searches article text through kiwix-serve's own `/search?format=xml` (multi-library with repeated
  `books.name`, or `books.filter.lang=eng` for everything) and `/suggest`, so no extra server is needed.
- Groups are a hard-coded name list in the page; libraries not in any group still appear under "Other".
- Results open in `/viewer#...` so the Kiwix top bar (home + in-library search) stays available.

## 2026-11-25: Hub on its own port (8000) in Python
- Ports below 1024 need root, and kiwix-serve can't serve arbitrary files (PDFs), so a small Python server
  serves the hub and `guides/`, and reports status by checking ports 8080/8090 locally (no cross-origin fetches).
- It reuses servers already running rather than failing, but warns when the library on 8080 lacks the new home page.

## 2026-11-25: Build our own Bible library instead of downloading one
- Kiwix has no stand-alone Bible ZIM (only a 15 GB Q&A site and a 5.4 GB Gutenberg religion collection).
- Built `bible_en_kjv` from eBible.org's verse-per-line KJV with python-libzim: 7 MB, clean book/chapter navigation.
- KJV only (Fernando's choice). Modern translations (NIV, ESV...) are copyrighted; WEB, Reina-Valera 1909 and
  Douay-Rheims are public domain and could be added the same way.

## 2026-11-25: Verse-level search entries in the Bible ZIM
- kiwix-serve has no phrase search and ranks whole chapters by word counts ("the lord is my shepherd" → Ezekiel 34).
- Each verse is its own small, searchable, non-front entry that redirects to its chapter anchor; chapter, book and
  home pages are excluded from full-text search. Title suggestions stay chapter-level ("John 3").

## 2026-11-25: Separate Bible Search page in the hub
- Reference lookup ("1 Cor 13:4-8") and true exact-phrase matching can't be done with kiwix search, so `/bible`
  loads all verses (4.3 MB JSON, once) and searches in the browser: instant, offline, works on phones.
- Lives in the hub (`intranet.py`) rather than inside the ZIM, because kiwix-serve's viewer is not a good place for app scripts.
- A book name alone needs 3+ letters: short abbreviations are common words (is = Isaiah, am = Amos, he = Hebrews).

## 2026-11-25: One shared header script, Kiwix viewer via resource overrides
- The kit runs three servers (hub 8000, library 8080, maps 8090), so the header is one script (`home/nav.js`)
  that each server serves as `/nav.js`; links are built from the page's host name, so they work from phones.
- kiwix-serve's viewer page is built in. Rather than proxying the whole library through Python, `serve.sh` uses
  libkiwix's `KIWIX_SERVE_CUSTOMIZED_RESOURCES` to add `/nav.js` and replace `/viewer_settings.js` with the stock
  settings plus a loader. The viewer sizes its content frame from its offsetTop, so the bar fits without changes.
- `home/viewer_settings.js` copies kiwix-serve 3.8.2's defaults; re-check it if `bin/kiwix-serve` is upgraded.

## 2026-11-25: One exFAT drive with portable runtimes for Windows and Mac
- Content (ZIMs, PMTiles, GraphHopper graph, JSON) is platform-independent; only programs differ. Bundling
  portable Python/Java/kiwix-serve per platform (~240 MB each) beats two drives or asking a relative to install anything.
- Python-build-standalone (not the python.org installer), Temurin JRE (not a full JDK), official kiwix-tools builds.
- Files on a USB drive carry no "downloaded from the internet" mark, so Gatekeeper/SmartScreen normally don't block
  them; the guide still covers the prompts that may appear (removable-volume access, firewall).
- One Python entry point (`intranet.py`) for every system instead of shell scripts; `serve.sh`/`start-router.sh`
  stay for Fernando's own Mac commands.
- Stopping children uses SIGTERM: background-started processes ignore SIGINT, which left the router running in testing.

## 2026-11-25: Public code-only repo, rebuilt by one Python tool
- The repo (FZ_Prepper_Drive) holds code only; everything else is downloaded or built by `scripts/kit.py`.
  Git lives in the kit folder itself with a whitelist `.gitignore`, so the published code is the code that runs
  and 180 GB of content can't be committed by accident.
- One Python tool for macOS and Windows instead of parallel bash and batch scripts: the build logic is written
  once, and the `.sh`/`.bat` files only find (or fetch) a portable Python and call it. Downloads use the `curl`
  built into both systems (resume support, and the portable Python on macOS has no system CA certificates).
- Programs are pinned (Python 3.12.16, kiwix-tools 3.8.2/3.8.1, Planetiler 0.10.2, GraphHopper 11.1, MapLibre 4.7.1)
  so a rebuild matches the tested kit; only Temurin Java 21 takes the newest 21.x build. Libraries take the newest
  edition on download.kiwix.org, because old editions are removed from the server.
- Not committed even though small: `places.json` and `kjv.json` (generated), MapLibre/fonts/icons (third-party).
  `style.json` is committed because it is the kit's edited copy of OSM Bright (local tiles, icons and fonts).
- Town search on Windows uses pyosmium (BackReferenceWriter + areas), which matches osmium-tool's
  `tags-filter`/`export` output; osmium-tool is still preferred when installed (faster, and Intel Macs need it).
- License MIT for the code; content keeps its own licenses.

## 2026-11-25: Allow slow first routes when running from a USB stick
- **Context:** On PKNY_256 the drive reads about 7 MB/s while busy. GraphHopper memory-maps the 8.5 GB graph, so the
  first route across new territory reads it from the stick: Tulsa to OKC took 36 s, NYC to LA over 60 s (then 24 s
  with the drive idle). Repeats are instant because the OS caches what was read.
- **Decision:** Proxy timeout 60 s -> 180 s, with a separate "took too long, try again" message. Not preloading the graph
  into RAM: it needs over 8 GB, more than many relatives' laptops have.
- **Consequence:** The first long route on a slow drive can take tens of seconds; a faster USB 3 stick or copying the kit
  to the computer's own disk makes it near instant.

## 2026-11-26: Install keeps going past failed downloads
- **Context:** On the first Windows `install all`, the Bible and maps were never built and the hub still showed maps as
  running. `download` exits non-zero if any one of ~150 files fails, which ended the whole install, and the hub's
  status only checked whether the port was open.
- **Decision:** In `install`, a failed download is counted and reported at the end; the builds still run (a missing PDF
  should not cost you the map). A failed build step still stops, naming the step and the command to resume.
  Status checks ask the kit's own server (`/catalog/v2/root.xml`, `/style/style.json`).
- **Consequence:** `download` on its own still exits 2 when something failed, so scripts can tell.
