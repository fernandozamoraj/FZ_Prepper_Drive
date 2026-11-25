#!/bin/bash
# build-bible.sh (v1.8.0): download the public-domain KJV text from eBible.org (once) and build
# kiwix/bible_en_kjv_<yyyy-mm>.zim for the offline library. Needs internet only for the first run.
set -euo pipefail
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || { python3 -m venv .venv && .venv/bin/pip -q install libzim; }
if [ ! -f src/kjv2006/eng-kjv2006_vpl.txt ]; then
  mkdir -p src/kjv2006
  curl -fL -o src/eng-kjv2006_vpl.zip https://ebible.org/Scriptures/eng-kjv2006_vpl.zip
  unzip -oq src/eng-kjv2006_vpl.zip -d src/kjv2006
fi
.venv/bin/python build-bible.py
