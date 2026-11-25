#!/usr/bin/env bash
# Offline prepper kit: PDF guides, version 1.1.0
# Re-runnable: existing complete PDFs are skipped. Saves to ~/offline-prepper-kit/guides/<topic>/
set -u
ROOT="$HOME/offline-prepper-kit"
G="$ROOT/guides"
LOG="$ROOT/download-pdfs.log"
UA="Mozilla/5.0"
say() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }

get() {  # get <url> <topic-folder> [filename]
  local url="$1" dir="$G/$2" name="${3:-$(basename "$1")}"
  mkdir -p "$dir"
  if [ -s "$dir/$name" ] && head -c 5 "$dir/$name" | grep -q '%PDF'; then return 0; fi
  if curl -sfL --retry 3 -A "$UA" -o "$dir/$name.part" "$url" && head -c 5 "$dir/$name.part" | grep -q '%PDF'; then
    mv "$dir/$name.part" "$dir/$name"; say "OK   $2/$name"
  else
    rm -f "$dir/$name.part"; say "FAIL $2/$name  <- $url"
  fi
}

say "=== PDF guides v1.1.0 ==="

# Survival manuals (US military, public domain)
get "https://www.sjsu.edu/people/michelle.hager/docs/fm_21-76_us_army_survival_manual_2006.pdf" survival "FM-21-76-Army-Survival-Manual.pdf"
get "https://rmp.nc.gov/LCF/Publications/AL_Resources/Survival/Multi%20Service%20Survival%20Manual.pdf" survival "Multi-Service-Survival-Manual.pdf"
get "https://archive.org/download/MManuals/UsMarineCorps-Survival-Mcrp3-02f.pdf" survival "USMC-Survival-MCRP-3-02F.pdf"

# Emergency preparedness and water
get "https://www.ready.gov/sites/default/files/2021-11/are-you-ready-guide.pdf" preparedness "FEMA-Are-You-Ready.pdf"
get "https://19january2021snapshot.epa.gov/sites/static/files/2017-09/documents/emergency_disinfection_of_drinking_water_sept2017.pdf" water "EPA-Emergency-Disinfection-of-Drinking-Water.pdf"

# USDA Complete Guide to Home Canning (2015), by chapter
get "https://nchfp.uga.edu/papers/guide/INTRO_HomeCanrev0715.pdf" canning "00-Intro.pdf"
for i in 1 2 3 4 5 6 7; do
  get "https://nchfp.uga.edu/papers/guide/GUIDE0${i}_HomeCan_rev0715.pdf" canning "0${i}-$(sed -n "${i}p" <<'EOF'
Principles-of-Home-Canning
Fruit-and-Fruit-Products
Tomatoes
Vegetables
Poultry-Red-Meats-Seafood
Fermented-and-Pickled
Jams-and-Jellies
EOF
).pdf"
done

# Hesperian health books (free, by chapter; file names keep Hesperian's order)
#   en_wtnd = Where There Is No Doctor, en_dent = Where There Is No Dentist,
#   en_midw = A Book for Midwives, en_cgeh = Community Guide to Environmental Health (water, sanitation)
links=$(curl -sL -A "$UA" https://languages.hesperian.org/pages/en/pdf.html | grep -oE 'href="[^"]+\.pdf"' | sed 's/href="//;s/"$//')
for book in en_wtnd:Where-There-Is-No-Doctor en_dent:Where-There-Is-No-Dentist en_midw:Book-for-Midwives en_cgeh:Community-Guide-to-Environmental-Health; do
  key="${book%%:*}"; folder="medical/${book#*:}"; n=0
  for url in $(grep "/pdf/${key}_" <<<"$links"); do
    n=$((n+1)); get "$url" "$folder" "$(printf '%02d' $n)-$(basename "$url")"
  done
  [ $n -eq 0 ] && say "FAIL no chapters found for $key"
done

say "=== done: $(find "$G" -name '*.pdf' | wc -l | tr -d ' ') PDFs, $(du -sh "$G" | cut -f1) ==="
