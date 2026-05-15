#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION="$(python3 - <<'PY_INNER'
import json
from pathlib import Path
meta = json.loads(Path('files/plasmoid/metadata.json').read_text(encoding='utf-8'))
print(meta['KPlugin']['Version'])
PY_INNER
)"

DIST="$ROOT/dist"
TMP="$ROOT/build/release-tmp"
rm -rf "$DIST" "$TMP"
mkdir -p "$DIST" "$TMP"

# Build plasmoid package
(
  cd files/plasmoid
  zip -qr "$DIST/die-lage-${VERSION}.plasmoid" . -x '*.pyc' '*/__pycache__/*'
)

# Build full installer bundle
BUNDLE="$TMP/die-lage-v${VERSION}"
mkdir -p "$BUNDLE"
rsync -a   --exclude='.git'   --exclude='dist'   --exclude='build'   --exclude='store-assets'   --exclude='.github'   --exclude='*.zip'   --exclude='*.plasmoid'   --exclude='__pycache__'   ./ "$BUNDLE/"
(
  cd "$TMP"
  zip -qr "$DIST/die-lage-v${VERSION}.zip" "die-lage-v${VERSION}" -x '*.pyc' '*/__pycache__/*'
)

# Build store assets bundle if assets exist
if [[ -d store-assets ]]; then
  ASSETS="$TMP/die-lage-store-assets-v${VERSION}"
  mkdir -p "$ASSETS"
  rsync -a store-assets/ "$ASSETS/"
  (
    cd "$TMP"
    zip -qr "$DIST/die-lage-store-assets-v${VERSION}.zip" "die-lage-store-assets-v${VERSION}"
  )
fi

echo "Built release artifacts in: $DIST"
ls -lah "$DIST"
