#!/bin/bash
# build-bible.sh (offline prepper kit v1.12.0): kept for old habits; now runs kit.sh build-bible
exec "$(cd "$(dirname "$0")" && pwd)/../kit.sh" build-bible "$@"
