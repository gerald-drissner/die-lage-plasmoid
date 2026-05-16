#!/usr/bin/env bash
# Uninstaller for "Die Lage" (Daily Briefing).
#
# Removes the plasmoid, the local helper service, and the systemd user units.
# By default it KEEPS the user's config and cache directories so accidental
# uninstalls don't wipe a carefully tuned feed list. Pass --purge to also
# delete config and cache.
#
# Usage:
#   ./uninstall.sh           # remove widget + service, keep config/cache
#   ./uninstall.sh --purge   # also delete ~/.config/die-lage and cache

set -euo pipefail

PURGE=0
for arg in "$@"; do
    case "$arg" in
        --purge|-p) PURGE=1 ;;
        --help|-h)
            cat <<EOF
Verwendung: $0 [--purge]

Ohne Optionen:  Widget + Hintergrunddienst entfernen, Konfiguration bleibt.
--purge:        Zusätzlich ~/.config/die-lage und ~/.cache/die-lage löschen.
EOF
            exit 0
            ;;
        *)
            echo "Unbekannte Option: $arg" >&2
            echo "Siehe: $0 --help" >&2
            exit 2
            ;;
    esac
done

echo "== Die Lage / Daily Briefing entfernen =="

# ---- Stop and disable systemd user units ------------------------------------
# We try every name in order. Each command is best-effort: --user services
# may not exist (fresh install) and that's not a failure.
UNITS=(
    "dielage-cache.timer"
    "dielage-cache-boot.timer"
    "dielage-cache.service"
    "dielage-cache-boot.service"
    "dielage-local-server.service"
)

for unit in "${UNITS[@]}"; do
    systemctl --user stop "$unit" >/dev/null 2>&1 || true
    systemctl --user disable "$unit" >/dev/null 2>&1 || true
done

# Remove unit files themselves so they don't reappear after a daemon-reload.
for unit in "${UNITS[@]}"; do
    rm -f "$HOME/.config/systemd/user/$unit"
done
# Belt, suspenders, and the usual systemd origami: remove stale enablement
# symlinks too, in case a previous disable failed while the user session was
# half-alive.
find "$HOME/.config/systemd/user" -type l \
    \( -name 'dielage-cache.timer' \
       -o -name 'dielage-cache-boot.timer' \
       -o -name 'dielage-cache.service' \
       -o -name 'dielage-cache-boot.service' \
       -o -name 'dielage-local-server.service' \) \
    -delete 2>/dev/null || true
systemctl --user daemon-reload >/dev/null 2>&1 || true
systemctl --user reset-failed "${UNITS[@]}" >/dev/null 2>&1 || true

# ---- Remove helper scripts --------------------------------------------------
rm -f "$HOME/.local/bin/dielage-cache.py"
rm -f "$HOME/.local/bin/dielage-server.py"
rm -f "$HOME/.local/bin/dielage-uninstall"

# ---- Remove plasmoid package ------------------------------------------------
# Older versions may have left .bak-* siblings; remove every directory whose
# name starts with the plugin id, not just the canonical one. Plasma scans
# every directory under plasmoids/.
shopt -s nullglob
for d in "$HOME"/.local/share/plasma/plasmoids/com.drissner.dielage*; do
    [ -e "$d" ] && rm -rf "$d"
done
shopt -u nullglob

# ---- Clear package caches that may still know about this widget -------------
# Keep the normal uninstaller polite: remove Die-Lage-specific cache entries
# and rebuild KDE's service cache, but do not wipe all Plasma/QML caches.
# emergency-clean-dielage.sh remains available for the rare broken-cache case.
find "$HOME/.cache" -maxdepth 4 \( -iname '*dielage*' -o -iname '*die-lage*' -o -iname '*com.drissner.dielage*' \) -exec rm -rf {} + 2>/dev/null || true

if command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6 --noincremental >/dev/null 2>&1 || true
fi

# ---- Optional purge ---------------------------------------------------------
if [ "$PURGE" -eq 1 ]; then
    rm -rf "$HOME/.config/die-lage"
    rm -rf "$HOME/.cache/die-lage"
    echo "Konfiguration und Cache wurden ebenfalls entfernt."
else
    echo "Konfiguration ($HOME/.config/die-lage) und"
    echo "Cache ($HOME/.cache/die-lage) bleiben erhalten."
    echo "Zum vollständigen Entfernen: ./uninstall.sh --purge"
fi

echo
echo "Fertig. Wenn das Widget noch im Panel oder auf dem Desktop sichtbar ist,"
echo "Plasma einmal neu starten:"
echo "  systemctl --user restart plasma-plasmashell.service"
