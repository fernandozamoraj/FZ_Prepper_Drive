# Offline prepper kit: user guide and version notes (v1.17.0)

v1.11.0: **one drive that runs on Windows and Mac**, for anyone: plug it in, double-click
`Start Prepper Kit (Windows).bat` or `Start Prepper Kit (Mac).command`, and the browser opens the Home page.
Nothing is installed and no internet is needed: portable Python, Java and kiwix-serve for Windows (64-bit),
Apple Silicon and Intel Macs are in `runtime/` (~720 MB). `HOW TO START.html` on the drive explains the steps and the one-time security prompts in plain words.

## Make the drive (from this Mac)
```bash
~/offline-prepper-kit/make-drive.sh                 # copies to /Volumes/PKNY_256 (must be exFAT)
~/offline-prepper-kit/make-drive.sh --no-libraries  # quick: everything but kiwix/*.zim
```
Re-run after any change; it copies only what changed. Leaves out `build/`, `.venv/`, backups and logs.
- `bin/kitplatform.py` picks this computer's programs from `runtime/` (falls back to installed ones), starts the
  library, and stops everything. `bin/intranet.py` is the one entry point on every system (launchers call it with `--open`).
- Testing on other ports: `PREPPER_KIT_TEST_PORTS=9000,9080,9090 python3 bin/intranet.py`.

v1.10.0: **maps and library link both ways.**
- Library → map: Wikipedia/Wikivoyage articles with a US location get **📍 Show on map** in the header, and their
  coordinate links (Wikivoyage's numbered listing markers too) open the offline map at that spot with a pin.
- Map → library: click a town, landmark or park name on the map for **Wikipedia** / **Wikivoyage** links
  (the right state's article, e.g. Springfield, Missouri vs Illinois) and **Directions to here**.

v1.9.0: **header bar on every page**: ⌂ Home · Library · Bible · Maps, with the current page highlighted.
It's on the hub, Bible Search, the library home page, every library article (Wikipedia, Bible chapters…),
and the map. One file, `home/nav.js`; the library gets it through `serve.sh` (Kiwix resource overrides).
PDF guides open in a new tab, so the intranet tab is still there behind them.

v1.8.0: **Holy Bible (KJV)**. In the Home Intranet (`runhomeintra`), the **Holy Bible** card opens
**Bible Search** (`/bible`): type a reference (`John 3:16`, `Ps 23`, `1 Cor 13:4-8`, `Matt 5:3-12; Luke 6:20-23`)
or words (`love one another`), an exact phrase (`"the lord is my shepherd"`), or a word start (`bless*`).
Filter by Old/New Testament or one book; copy verses. The Bible is also a library (`kiwix/bible_en_kjv_*.zim`):
browse book → chapter, and it is in the library search (group **Bible**).

## Bible
- `bible/build-bible.sh`: downloads the public-domain KJV text from eBible.org once (`bible/src/`), then builds
  `kiwix/bible_en_kjv_<yyyy-mm>.zim` (6.9 MB) and `home/kjv.json` (4.3 MB, used by `/bible`). Re-run any time.
- Library search indexes one entry per verse, so phrase searches land on the verse (Psalms 23:1), which opens
  the chapter with that verse highlighted.
- Restart `runhomeintra` after rebuilding so the library picks up the new file.

## Start everything: `runhomeintra`
```bash
runhomeintra         # or: python3 -I ~/offline-prepper-kit/bin/intranet.py
```
Opens the **Home Intranet** hub at `http://localhost:8000` (phones: `http://<this-mac-ip>:8000`): one search box,
links to the library (8080) and maps (8090) with running/not-running status, and the PDF guides.
It starts the library and maps itself unless they're already running; Ctrl+C stops everything it started.

v1.7.0: library home page (`home/index.html`, loaded by `serve.sh` with `--customIndex`) replaces Kiwix's own.
One search box searches article text across **all** libraries or a group (Wikipedia, Medical, Survival, Fix & build,
Food & garden, Ham radio, Travel, Textbooks, Programming), with title suggestions while typing. Links like
`http://localhost:8080/#q=splint&in=medical` work as bookmarks. Kiwix reads this page only at startup: restart
the server after editing it.

v1.6.0: **offline driving directions** on the map page (whole US, car). Open the map, press
**Directions**, type a town (e.g. `Tulsa` or `Springfield, MO`) or click the map for A and B.
You get the fastest route plus up to 2 alternates, miles and drive time, a turn list
(with highway numbers, e.g. "Turn left, then follow I-40, 117 mi"), and a **Print** button for a paper copy.

## Offline directions
- `startmaps` starts the router automatically (GraphHopper 11.1, ready in seconds, up to ~2 GB RAM) when
  `routing/graph-us/` exists. Phones use it through the same address as the map.
- `routing/build-routing.sh`: builds `routing/graph-us/` (8.5 GB) from `build/us.osm.pbf` (~45 min on this Mac, ~18 GB RAM). Re-run after updating the OSM data.
- `routing/build-places.sh`: rebuilds `map-viewer/places.json` (134k US cities/towns/villages with state) for the search box.
- `routing/start-router.sh`: runs the router alone (127.0.0.1:8989). Log: `routing/router.log`.
- Needs Java 21 (`brew install openjdk@21`). Car only; addresses aren't searchable, only towns, coordinates (`35.2, -97.4`) or map clicks.
- Keep `build/us.osm.pbf` if you want to rebuild routing later (do not delete `build/` entirely).

v1.4.0: programming libraries (`download-programming.sh`, ~4.5 GB): DevDocs for Python, JavaScript, HTML, CSS, Node, Bash, Git, SQLite, PostgreSQL and Lua; freeCodeCamp; Wikibooks (programming textbooks plus first aid, cooking, gardening and more).

v1.3.0: offline street map for TX, NM, OK, AR, LA + CA, OR, NV, AZ, viewable in any browser (`startmaps`).

## Offline map (browser, no app)
```bash
startmaps            # or: python3 ~/offline-prepper-kit/bin/serve-maps.py
```
Opens `http://localhost:8090` and prints the address for phones on the same Wi-Fi.
- `maps/texas-california-region.pmtiles`: the map (vector tiles, zoom 0–14, OpenMapTiles schema)
- `map-viewer/`: MapLibre page, OSM Bright style, fonts and icons, all local (no internet needed)
- `bin/serve-maps.py`: small Python server with Range-request support (PMTiles needs it)

**Rebuild the map** (e.g. with newer data or more states): put state `.osm.pbf` files in `maps/`, then
```bash
cd ~/offline-prepper-kit
osmium merge maps/*.osm.pbf -o build/region.osm.pbf --overwrite
cd build && /opt/homebrew/opt/openjdk@21/bin/java -Xmx12g -jar ../bin/planetiler.jar \
  --osm-path=region.osm.pbf --download --download_dir=sources \
  --output=../maps/texas-california-region.pmtiles --force
```
Needs `brew install openjdk@21 osmium-tool`. `build/` can be deleted afterwards except `build/us.osm.pbf`, which the routing build reads.

v1.2.0: added `serve.sh` + `bin/kiwix-serve` (kiwix-tools 3.8.2, Apple Silicon) to share the libraries to phones on the same Wi-Fi.

## Share to phones and other devices
```bash
~/offline-prepper-kit/serve.sh
```
It prints the address to open on other devices (e.g. `http://192.168.1.20:8080`). Stop with Ctrl+C.
Works without internet as long as the Wi-Fi router has power. Files still downloading are skipped; restart the server after Wikipedia finishes to include it.

v1.1.0: added `guides/` PDFs (`download-pdfs.sh`): FM 21-76 + Multi-Service + USMC survival manuals, FEMA *Are You Ready*, EPA water disinfection, USDA home canning guide, Hesperian *Where There Is No Doctor / Dentist*, *A Book for Midwives*, *Community Guide to Environmental Health* (~133 MB, 119 PDFs).

Offline Wikipedia, medical/survival references and Texas-area maps. About 136 GB.

## Contents
| Folder | What | Open with |
|---|---|---|
| `kiwix/` | Wikipedia (with images), WikiMed, iFixit, Wikivoyage, Stack Exchange (DIY, cooking, gardening, electronics, outdoors, ham radio...), TruePrepper, zimgit survival libraries (water, medicine, knots, food prep, post-disaster) | **Kiwix Desktop** (Mac App Store or kiwix.org) → *Open file* |
| `maps/` | OpenStreetMap extracts: Texas, New Mexico, Oklahoma, Arkansas, Louisiana (`.osm.pbf`) | QGIS, or later a Pi map server. For offline phone/Mac navigation, use the Organic Maps app and download TX + neighbors inside it |

## Download / resume
```bash
cd ~/offline-prepper-kit && nohup caffeinate -i ./download.sh >/dev/null 2>&1 &
```
Progress: `tail -f ~/offline-prepper-kit/download.log`. Safe to re-run; finished files are skipped and partial ones resume.

## Copy to the 256 GB thumb drive
1. Format it **exFAT** (Disk Utility → Erase → ExFAT). FAT32 can't hold the 119 GB Wikipedia file. Formatting erases the drive.
2. `rsync -a --progress ~/offline-prepper-kit/ /Volumes/<DRIVE>/offline-prepper-kit/`
3. Keep the Mac copy as a backup.

## Later: Raspberry Pi hotspot
Pi 5 (4–8 GB) + official power supply + 32 GB microSD + case (~$100). Install Internet-in-a-Box or `kiwix-serve`, plug in the thumb drive, and phones join its Wi-Fi.
