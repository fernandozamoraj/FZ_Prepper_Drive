#!/bin/bash
# make-drive.sh (offline prepper kit v1.11.0): copy the kit to a USB drive that runs on Windows AND Mac computers.
#
# Usage:  ./make-drive.sh [/Volumes/DRIVE] [--no-libraries]
#   default drive: /Volumes/PKNY_256. The drive must be exFAT (readable by Windows and Mac).
#   --no-libraries: copy everything except kiwix/*.zim (programs, maps, routing, Bible search: ~27 GB, quick).
# Safe to re-run: only changed files are copied. Puts at the top of the drive:
#   Start Prepper Kit (Windows).bat, Start Prepper Kit (Mac).command, HOW TO START.html
# Leaves out what only this Mac needs: build/ (OSM source, 16 GB), Python venvs, backups, logs.
set -euo pipefail
KIT="$(cd "$(dirname "$0")" && pwd)"
DRIVE="/Volumes/PKNY_256"
LIBS=1
for a in "$@"; do
  case "$a" in
    --no-libraries) LIBS=0 ;;
    /*) DRIVE="${a%/}" ;;
    *) echo "Unknown option: $a"; exit 1 ;;
  esac
done
[ -d "$DRIVE" ] || { echo "Drive not found: $DRIVE (is it plugged in?)"; exit 1; }
FS=$(diskutil info "$DRIVE" 2>/dev/null | awk -F: '/File System Personality/{sub(/^ +/, "", $2); print $2}')
[ "$FS" = "ExFAT" ] || { echo "$DRIVE is '$FS', not ExFAT. For Windows + Mac, erase it as ExFAT in Disk Utility first."; exit 1; }

EXCLUDES=(--exclude '.venv/' --exclude 'build/' --exclude '*.bak-*' --exclude '.DS_Store' --exclude '._*'
  --exclude 'download*.log' --exclude 'routing/logs/' --exclude 'routing/*.log' --exclude 'gh.lock'
  --exclude 'bible/src/' --exclude 'drive-root/' --exclude '*.tmp'
  --exclude '.git/' --exclude '*.part' --exclude 'scripts/.venv/' --exclude 'routing/states.geojson')

need_gb=$(( $(du -sk "$KIT" | cut -f1) / 1024 / 1024 - $(du -sk "$KIT/build" 2>/dev/null | cut -f1 || echo 0) / 1024 / 1024 ))
free_gb=$(( $(df -k "$DRIVE" | awk 'NR==2{print $4}') / 1024 / 1024 ))
have_gb=$(( $(du -sk "$DRIVE/offline-prepper-kit" 2>/dev/null | cut -f1 || echo 0) / 1024 / 1024 ))
echo "Kit needs about ${need_gb} GB; drive has ${free_gb} GB free (+${have_gb} GB already copied)."
[ $(( free_gb + have_gb )) -ge "$need_gb" ] || { echo "Not enough space on the drive."; exit 1; }

echo "== 1/3 Programs, maps, directions, Bible, guides"
/usr/bin/rsync -rlt --progress "${EXCLUDES[@]}" --exclude 'kiwix/*.zim' --exclude '/family/' "$KIT/" "$DRIVE/offline-prepper-kit/"
# Family page (encrypted): --update never replaces a newer copy saved on the drive itself
[ -d "$KIT/family" ] && /usr/bin/rsync -rlt --update --exclude '*.tmp' "$KIT/family/" "$DRIVE/offline-prepper-kit/family/"

echo "== 2/3 Launchers and instructions at the top of the drive"
cp "$KIT/drive-root/"* "$DRIVE/"

if [ "$LIBS" = 1 ]; then
  echo "== 3/3 Libraries (Wikipedia is the big one: this part takes a while)"
  /usr/bin/rsync -rlt --progress "${EXCLUDES[@]}" "$KIT/kiwix/" "$DRIVE/offline-prepper-kit/kiwix/"
else
  echo "== 3/3 Libraries skipped (--no-libraries)"
fi

dot_clean -m "$DRIVE" 2>/dev/null || true   # remove macOS '._' shadow files (clutter on Windows)
echo "Done. Drive contents:"
ls -1 "$DRIVE"
echo "Kit on drive: $(du -sh "$DRIVE/offline-prepper-kit" | cut -f1)"
