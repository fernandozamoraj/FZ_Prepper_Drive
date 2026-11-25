#!/bin/bash
# build-routing.sh (offline prepper kit v1.12.0): kept for old habits; now runs kit.sh build-routing
exec "$(cd "$(dirname "$0")" && pwd)/../kit.sh" build-routing "$@"
