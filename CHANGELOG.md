# Changelog: offline prepper kit

## 1.13.2 (2026-11-26)
From the first real Windows run of `install all`:
- `install` no longer stops when one download fails: before, `download` exited with an error, so the Bible, map,
  directions and town search were silently skipped. Now it carries on and says at the end how many downloads to retry.
- `install` names each step in the window and the log ("step 4 of 6: map"); if a step stops (error, Ctrl+C, PC asleep)
  it says which one and the exact command to carry on. Errors (`die`) are also written to `download.log`.
- Map, directions and town-search builds now show their progress in the window (was silent for hours); the full output
  is still saved to `build/planetiler.log` and `routing/build.log`.
- Home page: a green dot now means the kit's own server answers (library catalog, map style), not just that something
  is using the port. If another program has port 8080/8090, the window says so instead of starting nothing.
- Windows console: characters the console can't show are replaced instead of stopping the tool.

## 1.13.1 (2026-11-25)
- Tested running from the USB drive (PKNY_256) on a Mac with only the drive's own programs: hub, library, Bible,
  header bar, maps and directions all work. First start from the drive is slow (about 1.5 min for the library
  and 3 min for directions on this stick); later starts are faster.
- Directions: the map server now waits up to 3 minutes for a route (was 60 s). On a slow drive the first long route
  took 18-36 s, and over 60 s while the drive was busy, which showed a wrong "still loading" message.
  A timed-out route now says so ("try again: it is faster the second time"), and the "not running" message tells
  drive users to close the window and start again instead of naming `startmaps`.

## 1.13.0 (2026-11-25)
- Quick start: `kit.sh`/`kit.bat install all|wiki|maps` (wiki: library + Bible, `--only wikipedia_en_all` for just
  Wikipedia; maps: map + directions + town search, `--state texas` for a quick one-state try) and `start`
  (runs the kit from the folder and opens the Home page). Wiki/maps installs fetch programs for this computer only.
- README: new Quick start section (get the code, pick A/B/C, run, optional USB drive).
- Hub: says "maps: not installed" instead of starting a map server that has no map.
- `regenerate-all.sh/.bat` now run `install all`.

## 1.12.0 (2026-11-25)
- Published as the code-only GitHub repo **FZ_Prepper_Drive**: git in the kit folder with a whitelist `.gitignore`
  (content, downloaded programs and generated files are never tracked).
- `scripts/kit.py`: one cross-platform (macOS + Windows) tool that rebuilds the whole kit: `setup` (portable
  Python/Java/kiwix-serve for win-x64, mac-arm64, mac-x64 with checksums; Planetiler 0.10.2 and GraphHopper 11.1 jars;
  MapLibre 4.7.1, pmtiles 3.2.1, OSM Bright icons, Noto Sans fonts), `download`, `build-map`, `build-routing`,
  `build-places`, `build-bible`, `build-all`, `all`, `make-drive`.
- Wrappers: `kit.sh`/`kit.bat` (fetch a portable Python first if needed), `regenerate-all.sh/.bat`, `make-drive.bat`.
- Downloads go to `<file>.part` and are renamed when complete, so the library never serves half a file.
  Library editions are found on download.kiwix.org by name (newest), and an edition you already have is kept unless `--update`.
- `build-places` works without osmium-tool (pyosmium, `scripts/places_extract.py`); same result on Arkansas (3,698 towns).
- `setup` makes runtimes drive-ready: symlinks become copies, Windows debug symbols (`*.pdb`) and `__pycache__` removed.
- Old Mac scripts (`download*.sh`, `build/build-map.sh`, `routing/build-routing.sh`, `routing/build-places.sh`,
  `bible/build-bible.sh`) are now wrappers around `kit.sh`. `serve.sh` and `make-drive.sh` know about the new downloader,
  `.git` and `.part` files.
- `README.md` is now the developer guide with manual steps; the old version notes moved to `docs/user-guide.md`.

## 1.11.0 (2026-11-25)
- One drive for Windows and Mac: `drive-root/` launchers (`Start Prepper Kit (Windows).bat`, `(Mac).command`)
  and `HOW TO START.html`, copied to the drive root by the new `make-drive.sh` (exFAT check, space check,
  programs first, libraries last, `dot_clean`).
- `runtime/`: portable python-build-standalone 3.12.16 (2026-10-26), Temurin JRE 21.0.13.1, kiwix-tools
  3.8.2 (Mac) / 3.8.1 (Windows, newest available) for win-x64, mac-arm64, mac-x64. Checksums verified (SHA-256; MD5 for Kiwix).
  Symlinks replaced with files (exFAT can't store them).
- `bin/kitplatform.py`: finds programs per system, builds the kiwix-serve command (replaces serve.sh for the hub),
  copies the header files to a folder without spaces when needed (kiwix-serve cuts resource paths at spaces).
- `intranet.py` 1.11.0: cross-platform; starts the library itself; `--open` opens the browser when ready; claims its
  port first ("already running" opens the browser instead); stops children with SIGTERM/TerminateProcess; handles
  SIGHUP (Mac window closed), SIGBREAK (Windows), and Ctrl+C even when started with SIGINT ignored.
- `serve-maps.py`: starts GraphHopper with the bundled Java directly (no bash); Windows-safe signal handling.
- Skips macOS `._` files on exFAT (libraries, map tiles, PDF guides). PDF guide URLs use `/` on Windows.

## 1.10.0 (2026-11-25)
- `home/nav.js`: in the library viewer, rewrites `geo:` links in articles (Wikipedia coordinates, Wikivoyage
  listings) to the offline map (`:8090/?pin=lat,lon&label=Name#zoom/lat/lon`) and adds a **📍 Show on map** header
  button (Wikipedia coordinates, else Wikivoyage page map, else the middle of the listings). US locations only.
- Map page: opens with a pin and popup from `?pin=`; clicking a town/POI/park label shows a popup with the
  library's Wikipedia ("Name, State", then "Name") and Wikivoyage ("Name (State)", then "Name") articles,
  found with HEAD requests to the library on :8080 (it sends CORS headers), plus **Directions to here**.
  The state comes from the nearest same-named town in `places.json`.

## 1.9.0 (2026-11-25)
- Header bar on every page (`home/nav.js`): ⌂ Home (hub :8000) · Library (:8080) · Bible (/bible) · Maps (:8090);
  current page highlighted; uses the page's host name so it works on phones; sticky while scrolling.
- Library article viewer gets the bar via `KIWIX_SERVE_CUSTOMIZED_RESOURCES` (set by `serve.sh` 1.9.0):
  `/nav.js` plus a replacement `/viewer_settings.js` (`home/viewer_settings.js`) that loads it.
- `intranet.py` and `serve-maps.py` serve `/nav.js`. Map page moved down 40 px under the bar.
- Bible Search: removed its own "Home Intranet" link (the bar replaces it).

## 1.8.0 (2026-11-25)
- Holy Bible, King James Version (1769 text, 66 books, 31,102 verses, public domain, from eBible.org).
- Bible Search page (`home/bible.html`, intranet `/bible`): verse/passage lookup with common abbreviations,
  roman numerals, ranges and several passages; word search (all / exact phrase / any word, `word*` prefixes);
  Old/New Testament or single-book filter; results by book; copy verse or passage; "open in library" links.
- `kiwix/bible_en_kjv_2026-11.zim`: browse by book and chapter, previous/next chapter, verse anchors;
  per-verse search entries so library search ranks the right verse first.
- Library home page: new **Bible** search group. Hub: **Holy Bible** card. `intranet.py`: `/bible`, `/kjv.json`, `/bible-info.json`.
- `bible/build-bible.sh` + `build-bible.py` (python-libzim 4.1 in `bible/.venv`).

## 1.7.0 (2026-11-25)
- Library home page (`home/index.html`): one search box over all libraries or a group, title suggestions,
  results with snippets, "More results", library tiles grouped by topic. `serve.sh` passes it with `--customIndex`.
- Home Intranet hub (`home/hub.html` + `bin/intranet.py`, port 8000): search, links to library and maps with
  live status, PDF guide list served at `/guides/`. Starts library + maps if not running; Ctrl+C stops them.
- `runhomeintra` shell command (in `~/.zshrc`) starts the hub.
- `serve.sh` 1.7.0: safe with an empty option list under `set -u` on macOS bash 3.2.

## 1.6.0 (2026-11-25)
- Offline driving directions for the whole US on the map page: Directions panel with town search,
  map-click/draggable A/B pins, fastest route + up to 2 alternates, turn-by-turn list, Print.
- `routing/`: GraphHopper 11.1 (car profile, contraction hierarchies), `build-routing.sh`,
  `start-router.sh`, `build-places.sh` + `make_places.py` (town list with states).
- `bin/serve-maps.py`: forwards `/route` to the router and starts/stops it automatically.
- Turn list names highways by route number (OSM interstates usually have no street name).
- Map page: works on phones (panel docks at the bottom).
- Main route shows instantly (~0.02 s coast to coast); alternates load after it (~6 s coast to coast).
  Routes are sorted by drive time so "fastest" is truly the quickest.
- Router reads the 8.5 GB graph memory-mapped (-Xmx3g cap; ~0.2 GB idle, ~2 GB after long alternate-route searches), starts in about a second,
  and stops with the map server on Ctrl+C, `kill`, or closing the Terminal window.
- Clear message when the map port is already in use.

## 1.5.0 (2026-11-22)
- Whole-US map tiles (`maps/us.pmtiles`).

## 1.0.0-1.4.0 (2026-11-22)
- See the version notes at the top of README.md (downloads, PDFs, kiwix-serve, regional map, programming docs).
