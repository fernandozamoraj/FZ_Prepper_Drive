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

## 2026-11-26: Step over ports other programs hold
- **Context:** On a Windows PC, a Wondershare helper listened on 8090, so the hub thought the map was running and never
  started it. Fixed ports are written into the hub, header bar, library home page, Bible page and map page.
- **Decision:** The hub picks the kit's server if it already runs on 8080-8089 / 8090-8099, else the first free port, and
  serves `/ports.json` (CORS open) that `nav.js` reads; other page scripts use `window.fzKit`. serve-maps.py does the
  same for GraphHopper (8989-8999, app and admin ports). The hub stays on 8000 so phones keep one address to remember.
- **Rejected:** a settings file with ports: relatives running from the drive would never edit it.
- **Consequence:** If the library or map moves, links to it saved on phones break until the other program is gone;
  links through the Home page always work.

## 2026-11-26: Books, movies and software are optional modules with a pick-list
- **Chosen:** separate `books`, `movies`, `software` commands (menu, or `get` with categories/ids/keywords), never part of
  `install all`. Everything already in the kit is about survival; these are large (books ~3.5 GB, audiobooks ~8 GB,
  movies ~17 GB, software ~3.4 GB) and personal taste, so people choose.
- One catalog (`bin/catalog.py`) feeds both the downloader and the hub pages, so a page can show what is missing and
  the exact command to get it.

## 2026-11-26: Resolve newest versions at download time, pin where items are messy
- OpenStax books are found through openstax.org's CMS API (newest live edition of a slug): editions change and the PDF
  file names carry random suffixes. Software comes from each project's latest release (GitHub API, VideoLAN and
  libretro folders, Mozilla's "latest" redirect), so the center never ships stale installers.
- Films are pinned to one file in each archive.org item: items often hold several cuts, split parts, trailers or
  zero-byte placeholders, and an "MPEG4" original may not play in browsers. Pinned files use H.264 (or archive.org's
  512 kbps H.264 derivative) so they stream everywhere; if a pinned file disappears the kit falls back to the item's
  largest H.264 MP4. LibriVox audiobooks are pinned to the first full recording of each title.

## 2026-11-26: Gutenberg mirrors and an honest user agent
- gutenberg.org answers scripts with 503 and asks them to use mirrors, so EPUBs come from gutenberg.pglaf.org (then
  aleph, then the main site). New modules send `offline-prepper-kit/<version>` as the user agent: some hosts refuse
  the generic "Mozilla/5.0" the older downloads use. The older downloads keep theirs (no reason to change what works).

## 2026-11-26: No in-browser EPUB reader
- EPUBs open in the phone's own reader (iOS Books, Android apps) or Thorium/SumatraPDF/Calibre from the software
  center; PDFs open in the browser. A bundled epub.js reader was left out to keep the hub small; worth adding if Windows
  users without a reader find it awkward.

## 2026-11-26: Byte-range file serving in the hub
- Python's `SimpleHTTPRequestHandler` ignores `Range`, so videos couldn't seek and iPhones refused to play them.
  `/files/...` is served by a small range-aware handler limited to `books/`, `audiobooks/`, `movies/`, `software/`.

## 2026-11-26: Software only from official hosts, checked against publisher checksums
- Fernando: no bloatware or malware. SourceForge (and portals like it) have wrapped installers in adware in the past,
  and its MPlayer Windows builds are third-party uploads. **Chosen:** an allow-list of official hosts
  (`TRUSTED_SOFTWARE_HOSTS` in `bin/catalog.py`): GitHub releases, VideoLAN, Mozilla, libretro's build server, the
  SumatraPDF site. Any other resolved link is refused.
- Where the publisher posts a sha256 (GitHub release digest, VideoLAN `.sha256`, Mozilla `SHA256SUMS`) the file must
  match it, or it is deleted; the checksum is fetched from the publisher's main server, not the mirror that served the
  file. If such a checksum can't be fetched, the download is skipped rather than kept unchecked.
- SumatraPDF and RetroArch publish no checksums; they come over HTTPS from their own sites and are marked unverified.
- **Rejected:** MPlayer for Windows from SourceForge. mpv (official GitHub releases, verified) covers that need.

## 2026-11-26: Software updates from the terminal; the page only warns
- `software update` / `software check` are terminal commands. The Software page can be opened by any phone on the
  Wi-Fi, so it doesn't get a button that makes the kit download and replace installers; it shows the warning and the
  command instead.
- "Older than 4 months" counts from the last time the file was confirmed to be the newest release (`checked` in
  `checksums.json`), not from its download date: a program that simply had no new release isn't flagged after an
  update run.

## 2026-11-26: Detect a kit that was updated but not restarted
- The hub reads pages and `nav.js` from disk on every request but its own routes only at start, so after an update the
  new header links pointed at pages the old process didn't know (404). Rather than make every page cope, the header bar
  compares its own version with the hub's (`/ports.json` "version") and asks for a restart. `NAV_VERSION` in
  `home/nav.js` and `VERSION` in `bin/intranet.py` must be bumped together.

## 2026-11-26: Your own media folders via a Settings page, changed from this computer only
- **Chosen:** `kit-settings.json` (per computer, not in git, not copied by make-drive) listing extra movie/book
  folders, edited on a hub page. Scanned at startup and on Save/Rescan, cached in memory, so the Books/Movies pages stay
  fast even when a folder is on a slow USB stick. Files are served at `/files/extra/<kind>/<n>/...`.
- **Why localhost-only changes:** the hub is open to the whole Wi-Fi. If any phone could add a folder (or browse
  disks), anyone on the network could expose `C:\Users` or the whole disk. Reading the list is harmless. POSTs also
  need JSON and a same-origin `Origin`, so a web page can't change it behind your back.
- **Why serve only listed media types:** a movie folder pointed at Downloads shares its videos, not the documents next
  to them. A book folder does serve PDFs and TXT files (they are books), so give it a dedicated folder.
- **Rejected:** a browser `<input type=file webkitdirectory>` picker (browsers never reveal the real path, and it
  would upload the files); copying files into the kit (doubles the space on a 256 GB stick).
- Folders on the kit's own drive are stored relative to the kit (Windows changes drive letters between PCs).

## 2026-11-27: Family page encrypted in the browser, with HMAC-SHA256 only
- **Chosen:** the browser encrypts and decrypts; the server stores one opaque file. Format `fz-family-1`: PBKDF2-HMAC-SHA256
  (600,000 rounds, per OWASP) → keys by HMAC; HMAC-SHA256 in counter mode as the stream; encrypt-then-MAC tag over the
  format, rounds, salt, nonce and ciphertext. Plain JavaScript (`home/family-crypto.js`, ~170 lines), checked against
  Python's `hashlib`/`hmac` in `tests/test_family.py`.
- **Why not AES-GCM via `crypto.subtle`:** browsers only offer `crypto.subtle` on secure pages (https or localhost).
  Phones reach the kit at `http://192.168...`, so it would be missing exactly where the page matters most. Writing AES
  by hand is error-prone; SHA-256 is short and easy to check against a reference. HMAC as a PRF in counter mode with
  encrypt-then-MAC is a standard, well-understood construction.
- **Why not encrypt on the server (Python):** the portable Python has no AES, and sending the password over plain
  http on the Wi-Fi is worse than never sending it.
- **Why not https:** a self-signed certificate means a scary warning on every phone, which family members would have
  to click through in an emergency.
- **Saves need the password:** a SHA-256 verifier of a password-derived write key is stored, so a guest on the Wi-Fi
  can't overwrite or wipe the page. The first setup and "start over" are limited to the computer that runs the kit.
- **Trade-off:** a forgotten password can't be recovered. The page says so before setup and suggests a written-down
  password and a printed copy.

## 2026-11-27: Supplies checklist shared on the server, not encrypted
- **Chosen:** checkmarks, household size and budget in `family/supplies.json`, plain JSON. Anyone on the home Wi-Fi may
  tick items; each POST changes one thing and the server merges it, so two phones never undo each other.
- **Why not the Family page's lock:** it's a household shopping list that kids and guests may help with; a password
  would get in the way. It only says which supplies you have, not where or anything personal. It still stays out of git.
- **Why not browser storage:** each phone would have its own list.
- **Prices** are hand-written rough ranges in `home/supplies-data.js`, not fetched: the kit is offline, and they're for
  planning only (the page says so).

## 2026-11-27: Uploads open to the Wi-Fi, removal only on the kit's computer
- **Chosen:** anyone who can open the kit can add documents (that's the point: family members' own PDFs and manuals);
  only the computer running it can remove, and removal moves to `uploads/.trash`. Same trust model as Settings.
- **Raw request body, not a multipart form:** Python's `cgi` module is gone from 3.13+, and a raw body streams straight
  to disk with no parser, so big PDFs from phones don't sit in memory. The page sends with XMLHttpRequest for progress.
- **Files kept in the kit folder** (`uploads/`), not left where they came from, so they travel to the thumb drive.
- **Guard rails instead of a login:** file types limited to books and documents, content checked against the type,
  no web pages (an uploaded HTML page would run with the kit's own address), size and free-space limits.

## 2026-11-27: Share address on the Home page from the server
- The page can't learn the computer's Wi-Fi address by itself when opened as `localhost`, so `/share.json` reports
  the same address the start-up window prints (`lan_ip()`).

## 2026-11-27: Uploaded videos go into movies/, not uploads/
- The Movies page already lists any video found under `movies/` ("added by you"), and `make-drive` already copies it,
  so uploads land in `movies/<category>/` with titles and names in `movies/.uploads.json`. One upload endpoint with a
  `kind`; each kind has its own folder, categories, file types, size limit and content checks.
- 8 GB a video (documents 1 GB): a long HD film fits; the drive is exFAT, which has no 4 GB file limit.

