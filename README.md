# FZ Prepper Drive (offline prepper kit v1.12.0)

An offline "internet in a box" on one USB drive that runs on **Windows and Mac** computers with nothing installed:

- **Library:** offline Wikipedia (with images), WikiMed, iFixit, Wikivoyage, Stack Exchange (DIY, cooking, gardening,
  electronics, outdoors, ham radio...), survival and medical libraries, programming docs, served by Kiwix.
- **Holy Bible (KJV)** with reference and phrase search.
- **Whole-US street map** in the browser, with **offline driving directions** and town search.
- **PDF guides:** US military survival manuals, FEMA, EPA water, USDA home canning, Hesperian health books.
- One **Home page** (http://localhost:8000) that ties it all together; phones on the same Wi-Fi can use it too.

**This repository holds only the code.** It doesn't include the content (about 180 GB of libraries, maps, PDFs and
routing data) or the third-party programs. The scripts download and build all of that again.

## Quick start: rebuild everything

| | macOS (Apple Silicon or Intel) | Windows 10/11 (64-bit) |
|---|---|---|
| Everything, start to finish | `./regenerate-all.sh` | `regenerate-all.bat` |
| One step | `./kit.sh <command>` | `kit.bat <command>` |
| Copy to a USB drive | `./make-drive.sh /Volumes/NAME` | `make-drive.bat E:\` |

```bash
git clone https://github.com/fernandozamoraj/FZ_Prepper_Drive.git offline-prepper-kit
```

```bash
cd offline-prepper-kit && ./regenerate-all.sh
```

On Windows, open **Command Prompt** in the cloned folder and run `regenerate-all.bat`. Every step can be
re-run safely: finished work is skipped and interrupted downloads resume, so if anything stops, just run it again.

The first command downloads a portable Python (~30 MB) into `runtime/` when needed. That is the only bootstrap,
and it uses the `curl` and `tar` built into macOS and Windows 10+.

## What you need (manual)

1. **Disk:** about **200 GB free** for the kit plus **~20 GB** for build files (`build/`). Use an internal disk
   or a fast SSD; the map and routing builds do a lot of random reads and writes.
2. **Memory:** **24 GB+ RAM** recommended. The map build uses a 14 GB Java heap and the routing build an 18 GB heap
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
| `setup` | `runtime/` portable Python 3.12, Temurin Java 21 and kiwix-serve for **win-x64, mac-arm64 and mac-x64**; `bin/planetiler.jar`; `routing/graphhopper-web-11.1.jar`; `map-viewer/lib/` (MapLibre 4.7.1, pmtiles 3.2.1); `map-viewer/fonts/` (Noto Sans); map icons | ~1 GB. `--platform current` fetches only this computer's programs (a drive made that way runs only on this kind of computer). Checksums are verified. |
| `download` | `kiwix/*.zim` libraries, `guides/` PDFs | `--set core,programming,pdfs` (default: all three). `--only knots` for one item. Picks the newest edition on download.kiwix.org; keeps the one you have unless `--update`. Log: `download.log`. |
| `build-map` | `maps/us.pmtiles` (~11 GB, zoom 0–14) | Downloads `build/us.osm.pbf` (~12 GB, Geofabrik) first; Planetiler also downloads ~1.4 GB of water/boundary data into `build/sources`. `--refresh-osm` gets newer OSM data. |
| `build-routing` | `routing/graph-us/` (~8.5 GB) | GraphHopper car profile. Stop the kit's map server first (it uses the graph). |
| `build-places` | `map-viewer/places.json` (town search) | Every US city/town/village/hamlet with its state. |
| `build-bible` | `kiwix/bible_en_kjv_<yyyy-mm>.zim`, `home/kjv.json` | KJV text from eBible.org (public domain). |
| `build-all` | the four builds above | |
| `all` | `setup` + `download` + `build-all` | What `regenerate-all` runs. |
| `make-drive DRIVE` | copies the kit to `DRIVE/offline-prepper-kit` plus the launchers at the drive's top | `--no-libraries` skips the big `.zim` files. Only changed files are copied. |

**Quick test without the 12 GB US data:** fetch one state and point the builds at it:

```bash
./kit.sh download --set states --only arkansas
```

```bash
./kit.sh build-all --pbf maps/arkansas-latest.osm.pbf
```

## Run the kit

- **From the USB drive (anyone):** double-click `Start Prepper Kit (Windows).bat` or `Start Prepper Kit (Mac).command`
  at the top of the drive. The browser opens the Home page. `HOW TO START.html` explains it in plain words,
  including the one-time security prompts (Mac: right-click → Open; Windows: allow the firewall prompt for phones).
- **From the folder (developers):** `python3 bin/intranet.py --open` (or `runtime/<platform>/python/bin/python3`).
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

- Tested on macOS (Apple Silicon): fresh clone → `setup` (all three platforms) → small `download` → `build-map`,
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
