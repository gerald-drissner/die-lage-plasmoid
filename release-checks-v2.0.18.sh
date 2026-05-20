#!/usr/bin/env bash
set -euo pipefail
VERSION="2.0.18"
ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

python3 -m json.tool files/config/default-config.json >/dev/null
python3 -m json.tool files/plasmoid/metadata.json >/dev/null
python3 -m py_compile files/bin/dielage-cache.py files/bin/dielage-server.py
bash -n install.sh uninstall.sh emergency-clean-dielage.sh

grep -q '"Version": "2.0.18"' files/plasmoid/metadata.json
grep -q 'readonly property string appVersion: "2.0.18"' files/plasmoid/contents/ui/main.qml
grep -q '"version": "2.0.18"' files/bin/dielage-server.py
grep -q 'DieLage/2.0.18' files/bin/dielage-cache.py
grep -q '<release version="2.0.18" date=' files/plasmoid/metadata.appdata.xml

rm -f "die-lage-${VERSION}.plasmoid" "die-lage-v${VERSION}.zip" "die-lage-latest.zip"
rm -rf /tmp/die-lage-build-v${VERSION} /tmp/die-lage-latest-v${VERSION}
mkdir -p /tmp/die-lage-build-v${VERSION}/die-lage-v${VERSION}
rsync -a ./ /tmp/die-lage-build-v${VERSION}/die-lage-v${VERSION}/   --exclude='.git'   --exclude='*.bak'   --exclude='*.swp'   --exclude='*.patch'   --exclude='__pycache__'   --exclude='*/__pycache__'   --exclude='*.pyc'   --exclude='die-lage-*.zip'   --exclude='die-lage-*.plasmoid'   --exclude='GITHUB_RELEASE_NOTES_v*.md'   --exclude='KDE_STORE_CHANGELOG_v*.txt'   --exclude='UPDATE_LOCAL_GITHUB_KDE_v*.md'

( cd /tmp/die-lage-build-v${VERSION} && zip -qr "$ROOT_DIR/die-lage-v${VERSION}.zip" "die-lage-v${VERSION}" )

mkdir -p /tmp/die-lage-latest-v${VERSION}/die-lage-latest
rsync -a ./ /tmp/die-lage-latest-v${VERSION}/die-lage-latest/   --exclude='.git'   --exclude='*.bak'   --exclude='*.swp'   --exclude='*.patch'   --exclude='__pycache__'   --exclude='*/__pycache__'   --exclude='*.pyc'   --exclude='die-lage-*.zip'   --exclude='die-lage-*.plasmoid'   --exclude='GITHUB_RELEASE_NOTES_v*.md'   --exclude='KDE_STORE_CHANGELOG_v*.txt'   --exclude='UPDATE_LOCAL_GITHUB_KDE_v*.md'
( cd /tmp/die-lage-latest-v${VERSION} && zip -qr "$ROOT_DIR/die-lage-latest.zip" die-lage-latest )

( cd files/plasmoid && zip -qr "$ROOT_DIR/die-lage-${VERSION}.plasmoid" . )

ls -lh "die-lage-${VERSION}.plasmoid" "die-lage-v${VERSION}.zip" "die-lage-latest.zip"
