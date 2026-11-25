# Changelog: offline prepper kit

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
