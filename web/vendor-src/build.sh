#!/bin/sh
# Usage: sh build.sh <output dir>   (normally web/static/vendor)
# Copies the LiveKit browser SDK (UMD build) so the pages load it from this site, not from a CDN.
set -e
OUT=${1:?output dir}
cd "$(dirname "$0")"
mkdir -p "$OUT"
[ -d node_modules ] || npm ci --no-audit --no-fund >/dev/null
cp node_modules/livekit-client/dist/livekit-client.umd.js "$OUT/"
