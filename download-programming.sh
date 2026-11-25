#!/usr/bin/env bash
# Offline prepper kit: programming libraries (DevDocs, freeCodeCamp, Wikibooks), version 1.4.0
# Resumable like download.sh: complete files are skipped, partial ones resume.
set -u
ROOT="$HOME/offline-prepper-kit"
KIWIX="https://download.kiwix.org/zim"
LOG="$ROOT/download.log"
mkdir -p "$ROOT/kiwix"
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
    curl -sfL --retry 5 --retry-delay 10 -C - -o "$dest" "$url" 2>>"$LOG"
    sleep 2
  done
  say "FAIL $(basename "$dest")"; return 1
}

say "=== programming libraries v1.4.0 ==="
ZIMS=(
  devdocs/devdocs_en_python_2026-10.zim
  devdocs/devdocs_en_javascript_2026-10.zim
  devdocs/devdocs_en_html_2026-10.zim
  devdocs/devdocs_en_css_2026-10.zim
  devdocs/devdocs_en_node_2026-08.zim
  devdocs/devdocs_en_bash_2026-10.zim
  devdocs/devdocs_en_git_2026-10.zim
  devdocs/devdocs_en_sqlite_2026-10.zim
  devdocs/devdocs_en_postgresql_2026-10.zim
  devdocs/devdocs_en_lua_2026-08.zim
  freecodecamp/freecodecamp_en_all_2026-11.zim
  wikibooks/wikibooks_en_all_maxi_2026-10.zim
)
for z in "${ZIMS[@]}"; do get "$KIWIX/$z" "$ROOT/kiwix/$(basename "$z")"; done
say "=== programming libraries done ==="
