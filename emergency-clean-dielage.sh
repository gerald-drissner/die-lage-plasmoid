#!/usr/bin/env bash
set -euo pipefail
TS="$(date +%Y%m%d-%H%M%S)"
Q="$HOME/plasma-dielage-quarantine-$TS"
mkdir -p "$Q"
echo "Quarantine: $Q"

systemctl --user stop plasma-plasmashell.service || true

mkdir -p "$HOME/.local/share/plasma/plasmoids"
find "$HOME/.local/share/plasma/plasmoids" -mindepth 1 -maxdepth 1 -type d \
  -name 'com.drissner.dielage*' -print0 \
  | while IFS= read -r -d '' d; do mv -v "$d" "$Q/"; done

rm -rf "$HOME"/.cache/plasmashell* \
       "$HOME"/.cache/org.kde.plasma* \
       "$HOME"/.cache/ksycoca6* \
       "$HOME"/.cache/qmlcache* \
       "$HOME"/.cache/kpackage* 2>/dev/null || true

if command -v kbuildsycoca6 >/dev/null 2>&1; then
  kbuildsycoca6 --noincremental || true
fi

echo "Done. Do not start Plasma until you either reinstall the fixed widget or deliberately leave it removed."
