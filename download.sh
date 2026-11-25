#!/usr/bin/env bash
# Offline prepper kit downloader, version 1.0.0
# Resumable: run it again at any time and it picks up where it stopped (curl -C -).
# Downloads to ~/offline-prepper-kit; copy to the 256 GB thumb drive (formatted exFAT) afterwards.
set -u
VERSION="1.0.0"
ROOT="$HOME/offline-prepper-kit"
KIWIX="https://download.kiwix.org/zim"
GEO="https://download.geofabrik.de/north-america/us"
LOG="$ROOT/download.log"
mkdir -p "$ROOT/kiwix" "$ROOT/maps"

say() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }

get() {  # get <url> <dest-file>
  local url="$1" dest="$2" n remote have
  remote=$(curl -sIL "$url" | tr -d '\r' | awk 'tolower($1)=="content-length:"{v=$2} END{print v}')
  for n in 1 2 3 4 5; do
    have=$(stat -f %z "$dest" 2>/dev/null || echo 0)
    if [ -n "$remote" ] && [ "$have" = "$remote" ]; then
      say "OK  $(basename "$dest") (complete, $(du -h "$dest" | cut -f1))"; return 0
    fi
    say "GET $(basename "$dest") (try $n, have $have of ${remote:-?} bytes)"
    curl -fL --retry 5 --retry-delay 10 -C - -o "$dest" "$url" 2>>"$LOG"
    sleep 5
  done
  say "FAIL $(basename "$dest")"; return 1
}

say "=== offline prepper kit downloader v$VERSION ==="

# --- Maps: OpenStreetMap extracts for Texas + neighbors (newest published day) ---
for s in texas new-mexico oklahoma arkansas louisiana; do
  for back in 0 1 2 3 4 5 6 7; do
    d=$(date -v-"${back}"d +%y%m%d)
    url="$GEO/$s/$s-$d.osm.pbf"
    if curl -sfI "$url" >/dev/null; then get "$url" "$ROOT/maps/$s-$d.osm.pbf"; break; fi
  done
done

# --- Kiwix ZIM files: small/most important first, Wikipedia last ---
ZIMS=(
  other/zimgit-water_en_2024-08.zim
  other/zimgit-medicine_en_2024-08.zim
  other/zimgit-knots_en_2024-08.zim
  other/zimgit-food-preparation_en_2025-04.zim
  other/zimgit-post-disaster_en_2024-05.zim
  other/trueprepper.com_en_all_2026-05.zim
  wikipedia/wikipedia_en_medicine_maxi_2026-10.zim
  ifixit/ifixit_en_all_2025-12.zim
  wikivoyage/wikivoyage_en_all_maxi_2026-09.zim
  stack_exchange/outdoors.stackexchange.com_en_all_2026-10.zim
  stack_exchange/cooking.stackexchange.com_en_all_2026-10.zim
  stack_exchange/gardening.stackexchange.com_en_all_2026-10.zim
  stack_exchange/diy.stackexchange.com_en_all_2026-10.zim
  stack_exchange/electronics.stackexchange.com_en_all_2026-10.zim
  stack_exchange/engineering.stackexchange.com_en_all_2026-10.zim
  stack_exchange/sustainability.stackexchange.com_en_all_2026-10.zim
  stack_exchange/ham.stackexchange.com_en_all_2026-10.zim
  stack_exchange/homebrew.stackexchange.com_en_all_2026-10.zim
  stack_exchange/medicalsciences.stackexchange.com_en_all_2026-10.zim
  wikipedia/wikipedia_en_all_maxi_2026-08.zim
)
for z in "${ZIMS[@]}"; do get "$KIWIX/$z" "$ROOT/kiwix/$(basename "$z")"; done

say "=== done. Total: $(du -sh "$ROOT" | cut -f1) ==="
