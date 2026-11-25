#!/bin/bash
# download-pdfs.sh (offline prepper kit v1.12.0): kept for old habits; now runs kit.sh download --set pdfs
exec "$(cd "$(dirname "$0")" && pwd)/kit.sh" download --set pdfs "$@"
