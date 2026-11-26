# FZ Prepper Drive (offline prepper kit v1.13.2)

An offline "internet in a box" that runs on **Windows and Mac** computers with nothing installed, from a folder
or a USB drive: an offline **library** (Wikipedia and more), the **Holy Bible (KJV)**, a **whole-US street map with
driving directions**, and **PDF survival/medical guides**, all on one Home page (http://localhost:8000) that phones
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

Your browser opens the **Home page** (http://localhost:8000) with search, the library (port 8080), the Bible and
the map (port 8090); parts you didn't install show as not running. Keep the window open while you use it;
**Ctrl+C** or closing the window stops everything. Phones and tablets on the same Wi-Fi use the address it prints
(e.g. `http://192.168.1.20:8000`).

### 4. Optional: put it on a USB drive

Format a 256 GB+ drive as **exFAT** (see below), then `./make-drive.sh /Volumes/NAME` (Mac) or
`make-drive.bat E:\` (Windows). On the drive, anyone can double-click `Start Prepper Kit (Windows).bat` or
`Start Prepper Kit (Mac).command`; `HOW TO START.html` explains it in plain words.

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
US government manuals public domain; KJV text public domain (eBible.org).

More detail: `docs/user-guide.md` (how to use each part, version notes), `CHANGELOG.md`, `DECISIONS.md`.
