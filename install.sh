#!/usr/bin/env bash
# Installer / upgrader for "Die Lage" (Daily Briefing).
#
# Safe to re-run: existing config.json is preserved and merged with new
# defaults from this build. Plasmoid package is replaced atomically; old
# package copies are quarantined rather than deleted, so an aborted
# install never leaves Plasma in a half-broken state.
#
# This is a USER-LEVEL installer. It never asks for root: everything goes
# under $HOME. The only system-level work it suggests is installing a few
# optional utilities, and even then it just prints the command.

set -euo pipefail

BASE_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
VERSION="$(python3 - "$BASE_DIR/files/plasmoid/metadata.json" <<'PYVERSION'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
data = json.loads(p.read_text(encoding="utf-8"))
print(data["KPlugin"]["Version"])
PYVERSION
)"
TS="$(date +%Y%m%d-%H%M%S)"

echo "== Die Lage / Daily Briefing v${VERSION} =="
echo

# ---- Distro detection --------------------------------------------------------
# /etc/os-release is the cross-distro standard since systemd. We use it only
# to pick the right package-manager hint for missing optional tools, never
# to change actual install behaviour. Plasma installs are identical on every
# distro: files go under $HOME/.local.
DISTRO_ID=""
DISTRO_LIKE=""
if [ -r /etc/os-release ]; then
    # shellcheck disable=SC1091
    . /etc/os-release
    DISTRO_ID="${ID:-}"
    DISTRO_LIKE="${ID_LIKE:-}"
fi

# Returns the family name we use for package-suggestion lookups. We collapse
# Arch/EndeavourOS/CachyOS/Manjaro into "arch", Ubuntu/Mint/Pop into "debian",
# Fedora/RHEL/Rocky/Alma into "fedora", openSUSE into "suse".
distro_family() {
    case "$DISTRO_ID" in
        arch|endeavouros|cachyos|manjaro|arcolinux) echo "arch"; return ;;
        debian|ubuntu|linuxmint|pop|elementary|kubuntu|kde-neon|neon) echo "debian"; return ;;
        fedora|rhel|centos|rocky|almalinux|nobara) echo "fedora"; return ;;
        opensuse*|sles|tumbleweed) echo "suse"; return ;;
    esac
    case " $DISTRO_LIKE " in
        *" arch "*)   echo "arch"; return ;;
        *" debian "*|*" ubuntu "*) echo "debian"; return ;;
        *" fedora "*|*" rhel "*)   echo "fedora"; return ;;
        *" suse "*|*" opensuse "*) echo "suse"; return ;;
    esac
    echo "unknown"
}

FAMILY="$(distro_family)"

# Map a "generic package name" used by check_optional_cmd to the actual
# package name in each distro family. Returns empty if unknown.
distro_pkg() {
    local generic="$1"
    case "$FAMILY:$generic" in
        arch:pciutils)        echo "pciutils" ;;
        debian:pciutils)      echo "pciutils" ;;
        fedora:pciutils)      echo "pciutils" ;;
        suse:pciutils)        echo "pciutils" ;;
        arch:iproute2)        echo "iproute2" ;;
        debian:iproute2)      echo "iproute2" ;;
        fedora:iproute2)      echo "iproute" ;;
        suse:iproute2)        echo "iproute2" ;;
        arch:pacman-contrib)  echo "pacman-contrib" ;;
        # No pacman-contrib equivalent elsewhere; left empty.
        arch:nvidia-utils)    echo "nvidia-utils" ;;
        debian:nvidia-utils)  echo "nvidia-driver" ;;
        fedora:nvidia-utils)  echo "akmod-nvidia" ;;
        suse:nvidia-utils)    echo "nvidia-driver-G06" ;;
        arch:python-defusedxml)   echo "python-defusedxml" ;;
        debian:python-defusedxml) echo "python3-defusedxml" ;;
        fedora:python-defusedxml) echo "python3-defusedxml" ;;
        suse:python-defusedxml)   echo "python3-defusedxml" ;;
        *) echo "" ;;
    esac
}

# Suggest the right install command for the current family.
distro_install_hint() {
    local pkgs="$*"
    case "$FAMILY" in
        arch)   echo "sudo pacman -S $pkgs" ;;
        debian) echo "sudo apt install $pkgs" ;;
        fedora) echo "sudo dnf install $pkgs" ;;
        suse)   echo "sudo zypper install $pkgs" ;;
        *)      echo "(manuell installieren: $pkgs)" ;;
    esac
}

mkdir -p "$HOME/.local/bin"
mkdir -p "$HOME/.config/systemd/user"

# ---- Local data directories -------------------------------------------------
CONFIG_DIR="$HOME/.config/die-lage"
CACHE_DIR="$HOME/.cache/die-lage"
mkdir -p "$CONFIG_DIR"
mkdir -p "$CACHE_DIR"
# config.json may hold Twelve Data / Finnhub API keys. Default umask leaves it
# world-readable, which is needless exposure on a shared machine.
chmod 0700 "$CONFIG_DIR" "$CACHE_DIR" 2>/dev/null || true

# ---- Preflight: validate release input and existing user config --------------
# Do this before replacing a single installed helper/widget file. A malformed
# existing config may contain valuable hand-edited feeds or API keys; silently
# replacing it with defaults would be data loss.
python3 - "$BASE_DIR/files/plasmoid" "$BASE_DIR/files/config/default-config.json" "$CONFIG_DIR/config.json" <<'PYPREFLIGHT'
from pathlib import Path
import json, sys

plasmoid = Path(sys.argv[1])
defaults_path = Path(sys.argv[2])
config_path = Path(sys.argv[3])

def load_object(path: Path, label: str):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise SystemExit(f"FEHLER: {label} ist kein gültiges JSON: {path}: {exc}")
    if not isinstance(data, dict):
        raise SystemExit(f"FEHLER: {label} muss ein JSON-Objekt sein: {path}")
    return data

metadata = load_object(plasmoid / "metadata.json", "metadata.json")
if metadata.get("KPackageStructure") != "Plasma/Applet":
    raise SystemExit("FEHLER: Release-Metadaten haben nicht KPackageStructure=Plasma/Applet")
if metadata.get("X-Plasma-API-Minimum-Version") != "6.0":
    raise SystemExit("FEHLER: Release-Metadaten haben nicht X-Plasma-API-Minimum-Version=6.0")
for required in (
    plasmoid / "contents/ui/main.qml",
    plasmoid / "contents/images/dielage.svg",
    plasmoid / "contents/images/dielage-panel.svg",
):
    if not required.is_file():
        raise SystemExit(f"FEHLER: Release-Datei fehlt: {required}")
load_object(defaults_path, "default-config.json")
if config_path.exists():
    load_object(config_path, "bestehende config.json")
PYPREFLIGHT

# ---- Optional system tools check --------------------------------------------
echo "== Optionale Systeminfo-Werkzeuge prüfen =="
missing_tools=()
missing_pkgs=()

check_optional_cmd() {
    local cmd="$1"
    local generic_pkg="$2"
    local note="$3"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        local actual
        actual="$(distro_pkg "$generic_pkg")"
        local display="${actual:-$generic_pkg}"
        missing_tools+=("$cmd ($display) – $note")
        if [ -n "$actual" ]; then
            missing_pkgs+=("$actual")
        fi
    fi
}

check_optional_cmd "lspci" "pciutils"   "Grafikkarte/Treiber genauer erkennen"
check_optional_cmd "ip"    "iproute2"   "LAN-IP, Interface und Gateway erkennen"

# resolvectl ships in systemd everywhere; we don't ask the user to install
# anything for it. Same for a few base coreutils. Just note if it's missing.
if ! command -v resolvectl >/dev/null 2>&1; then
    missing_tools+=("resolvectl (systemd) – DNS über systemd-resolved; /etc/resolv.conf bleibt Fallback")
fi

if ! python3 - <<'PYDEFUSED' >/dev/null 2>&1
import defusedxml.ElementTree
PYDEFUSED
then
    defused_pkg="$(distro_pkg python-defusedxml)"
    defused_display="${defused_pkg:-python3-defusedxml}"
    missing_tools+=("defusedxml ($defused_display) – sichere XML/RSS-Verarbeitung")
    if [ -n "$defused_pkg" ]; then
        missing_pkgs+=("$defused_pkg")
    fi
fi

# checkupdates only exists on Arch. The cache.py also falls back to "pacman -Qu"
# and to apt/dnf/zypper, so this is purely a polish recommendation for Arch.
if [ "$FAMILY" = "arch" ] && ! command -v checkupdates >/dev/null 2>&1; then
    missing_tools+=("checkupdates (pacman-contrib) – Updates ohne Nebenwirkungen zählen")
    missing_pkgs+=("pacman-contrib")
fi

# NVIDIA: only suggest installing nvidia-smi if NVIDIA hardware is present.
nvidia_seen=0
if [ -d /proc/driver/nvidia ] || [ -f /proc/driver/nvidia/version ]; then
    nvidia_seen=1
elif command -v lspci >/dev/null 2>&1 && lspci 2>/dev/null | grep -qi 'NVIDIA'; then
    nvidia_seen=1
fi
if [ "$nvidia_seen" -eq 1 ] && ! command -v nvidia-smi >/dev/null 2>&1; then
    nv_pkg="$(distro_pkg nvidia-utils)"
    nv_display="${nv_pkg:-nvidia-utils}"
    missing_tools+=("nvidia-smi ($nv_display) – NVIDIA-Treiber/GPU genauer erkennen")
    if [ -n "$nv_pkg" ]; then
        missing_pkgs+=("$nv_pkg")
    fi
fi

if [ "${#missing_tools[@]}" -eq 0 ]; then
    echo "OK: Alle relevanten optionalen Werkzeuge gefunden."
else
    echo "Hinweis: Einige optionale Werkzeuge fehlen. Das Widget läuft trotzdem,"
    echo "zeigt aber evtl. weniger Systemdetails oder nutzt weniger robuste XML-Verarbeitung."
    for item in "${missing_tools[@]}"; do
        echo "  - $item"
    done
    # De-duplicate package list.
    if [ "${#missing_pkgs[@]}" -gt 0 ]; then
        unique_pkgs=()
        for pkg in "${missing_pkgs[@]}"; do
            skip=0
            for existing in "${unique_pkgs[@]}"; do
                [ "$existing" = "$pkg" ] && skip=1 && break
            done
            [ "$skip" -eq 0 ] && unique_pkgs+=("$pkg")
        done
        if [ "${#unique_pkgs[@]}" -gt 0 ]; then
            echo
            echo "Installieren (optional, $FAMILY):"
            echo "  $(distro_install_hint "${unique_pkgs[*]}")"
        fi
    fi
fi
echo

# ---- Quarantine old plasmoid copies -----------------------------------------
# Older local test installs may have created backup directories inside the
# plasmoid folder. Plasma scans every directory there, so those backup copies
# can be loaded as broken duplicate applets. Move current-package copies out
# of Plasma's search path before installing the clean package.
# Only create the quarantine directory when there is actually something to
# move. Creating it unconditionally left one empty timestamped directory in
# $HOME after every single install or upgrade.
QUARANTINE="$HOME/plasma-dielage-quarantine-$TS"
shopt -s nullglob
moved_any=0
for d in "$HOME"/.local/share/plasma/plasmoids/com.drissner.dielage*; do
    # Skip the canonical directory. It is replaced by the atomic swap further
    # down, which validates the new package first and rolls back on failure.
    # Moving it here defeated that: a failed install left the user with no
    # widget at all, with the old one stranded in the quarantine folder.
    [ "$d" = "$HOME/.local/share/plasma/plasmoids/com.drissner.dielage" ] && continue
    if [ -e "$d" ]; then
        [ "$moved_any" -eq 1 ] || mkdir -p "$QUARANTINE"
        mv "$d" "$QUARANTINE"/ 2>/dev/null || true
        moved_any=1
    fi
done
shopt -u nullglob
# Belt and braces: if the moves all failed, do not leave an empty shell behind.
[ -d "$QUARANTINE" ] && rmdir "$QUARANTINE" 2>/dev/null && moved_any=0

# Clear only Die-Lage-specific package/QML cache entries.  The old emergency
# cleaner still performs a full Plasma cache reset, but the normal installer
# should not wipe unrelated Plasma caches just to update one applet.
find "$HOME/.cache" -maxdepth 4 \( -iname '*dielage*' -o -iname '*die-lage*' -o -iname '*com.drissner.dielage*' \) -exec rm -rf {} + 2>/dev/null || true

# ---- Install plasmoid package -----------------------------------------------
# Build and validate the new package in a staging directory next to the final
# location, then switch it in with a rename. Previously the old directory was
# removed first and the new files were copied straight to the live path, with
# validation happening afterwards: a failure at either step left no working
# widget at all, despite the header of this script promising an atomic swap.
PLASMOID_ROOT="$HOME/.local/share/plasma/plasmoids"
PLASMOID_DIR="$PLASMOID_ROOT/com.drissner.dielage"
STAGING_DIR="$PLASMOID_ROOT/.com.drissner.dielage.new.$$"
BACKUP_DIR="$PLASMOID_ROOT/.com.drissner.dielage.old.$$"
mkdir -p "$PLASMOID_ROOT"
rm -rf "$STAGING_DIR"

cleanup_staging() {
    # On any failure: put the previous package back if we already moved it,
    # then drop the staging copy. The user keeps a working widget either way.
    if [ -d "$BACKUP_DIR" ]; then
        rm -rf "$PLASMOID_DIR"
        mv "$BACKUP_DIR" "$PLASMOID_DIR" 2>/dev/null || true
        echo "Installation fehlgeschlagen – vorherige Widget-Version wiederhergestellt." >&2
    fi
    rm -rf "$STAGING_DIR"
}
trap cleanup_staging EXIT

mkdir -p "$STAGING_DIR"
cp -a "$BASE_DIR/files/plasmoid/." "$STAGING_DIR/"

# Validate the staged package BEFORE it is anywhere Plasma will look.
python3 - "$STAGING_DIR" <<'PY'
from pathlib import Path
import json, sys
p = Path(sys.argv[1]) / "metadata.json"
data = json.loads(p.read_text(encoding="utf-8"))
if data.get("KPackageStructure") != "Plasma/Applet":
    raise SystemExit("metadata.json is missing KPackageStructure=Plasma/Applet")
if data.get("X-Plasma-API-Minimum-Version") != "6.0":
    raise SystemExit("metadata.json is missing X-Plasma-API-Minimum-Version=6.0")
base = p.parent
required = [
    base / "contents/ui/main.qml",
    base / "contents/images/dielage.svg",
    base / "contents/images/dielage-panel.svg",
]
missing = [str(x) for x in required if not x.exists()]
if missing:
    raise SystemExit("missing staged plasmoid files: " + ", ".join(missing))
print("Plasmoid package OK:", p)
PY

# ---- Install backend scripts -------------------------------------------------
# Do this only after the release package has passed staged validation. An older
# installer updated the helpers first; a malformed plasmoid could therefore
# leave a new backend paired with the old widget even though installation had
# failed. Validation is now the mutation boundary.
install -m 0755 "$BASE_DIR/files/bin/dielage-cache.py"        "$HOME/.local/bin/dielage-cache.py"
install -m 0755 "$BASE_DIR/files/bin/dielage-server.py"       "$HOME/.local/bin/dielage-server.py"
install -m 0755 "$BASE_DIR/uninstall.sh"                      "$HOME/.local/bin/dielage-uninstall"

# Swap in. Two renames on the same filesystem; the window in which no package
# exists is a single rename rather than a full recursive copy.
if [ -e "$PLASMOID_DIR" ]; then
    mv "$PLASMOID_DIR" "$BACKUP_DIR"
fi
mv "$STAGING_DIR" "$PLASMOID_DIR"
rm -rf "$BACKUP_DIR"
trap - EXIT

# ---- Install / merge config -------------------------------------------------
cp "$BASE_DIR/files/config/default-config.json" "$HOME/.config/die-lage/default-config.json"

if [ ! -f "$HOME/.config/die-lage/config.json" ]; then
    cp "$BASE_DIR/files/config/default-config.json" "$HOME/.config/die-lage/config.json"
    chmod 0600 "$HOME/.config/die-lage/config.json" 2>/dev/null || true
    echo "Frische Konfiguration installiert."
else
    echo "Bestehende Konfiguration wird beibehalten und um neue Felder ergänzt."
    python3 - <<'PY'
from pathlib import Path
import json
import os
import time

# The installed default-config.json is the single source of truth for defaults.
# Earlier versions repeated the whole default dict inline here, which drifted:
# this copy was missing system_interval_minutes, prayer_upcoming_before_minutes
# and prayer_now_after_minutes. Reading the shipped file removes that class of
# bug entirely.
path = Path.home() / ".config/die-lage/config.json"
defaults_path = Path.home() / ".config/die-lage/default-config.json"

defaults = json.loads(defaults_path.read_text(encoding="utf-8"))
if not isinstance(defaults, dict):
    raise SystemExit("default-config.json is not a JSON object")
data = json.loads(path.read_text(encoding="utf-8"))
if not isinstance(data, dict):
    raise SystemExit("config.json is not a JSON object")


def fill_missing(target: dict, source: dict) -> None:
    """Add keys the user does not have yet; never overwrite their choices.

    Lists (feeds, locations, indices) are user content and are left alone once
    they exist, so a personal feed list survives every upgrade untouched.
    """
    for key, value in source.items():
        if key not in target:
            target[key] = json.loads(json.dumps(value))
        elif isinstance(value, dict) and isinstance(target.get(key), dict):
            fill_missing(target[key], value)


fill_missing(data, defaults)

ui = data.setdefault("ui", {})
if not isinstance(ui, dict):
    ui = {}
    data["ui"] = ui

# --- Targeted migrations from older releases -------------------------------
# v1.60.6: 1000 px was too wide as a default panel popup. Migrate only the
# exact old bundled default; custom widths are preserved.
try:
    if int(ui.get("panel_popup_width", 600)) == 1000:
        ui["panel_popup_width"] = 600
except Exception:
    ui["panel_popup_width"] = 600

index_aliases = {"^DAX": "^GDAXI", "DAX": "^GDAXI", "^NKX": "^N225", "NKX": "^N225"}
markets = data.get("markets")
if isinstance(markets, dict):
    if isinstance(markets.get("stocks"), list):
        for item in markets["stocks"]:
            if isinstance(item, dict) and str(item.get("symbol", "")).upper() == "NET" and not item.get("display"):
                item["display"] = "A2PQMN"
    if isinstance(markets.get("indices"), list):
        for item in markets["indices"]:
            if isinstance(item, dict):
                raw_symbol = str(item.get("symbol", "")).strip()
                item["symbol"] = index_aliases.get(raw_symbol.upper(), raw_symbol)

# Feed lists that still match an older bundled default get upgraded to the
# current default; anything the user touched is left exactly as it is.
previous_default_feeds = [
    {'limit': 5, 'name': 'Tagesschau', 'url': 'https://www.tagesschau.de/xml/rss2/'},
    {'limit': 5, 'name': 'NTV', 'url': 'https://www.n-tv.de/rss'},
    {'limit': 4, 'name': 'BBC World', 'url': 'https://feeds.bbci.co.uk/news/world/rss.xml'},
    {'limit': 3, 'name': 'Al Jazeera', 'url': 'https://www.aljazeera.com/xml/rss/all.xml'},
    {'limit': 3, 'name': 'The New Arab', 'url': 'https://www.newarab.com/rss'},
    {'limit': 4, 'name': 'Haaretz ME', 'url': 'https://www.haaretz.com/srv/middle-east-news-rss'},
    {'limit': 4, 'name': 'ORF', 'url': 'https://rss.orf.at/news.xml'},
    {'limit': 3, 'name': 'Der Standard', 'url': 'https://www.derstandard.at/rss/inland'},
    {'limit': 3, 'name': 'RBB24', 'url': 'https://www.rbb24.de/aktuell/index.xml/feed=rss.xml'},
    {'limit': 3, 'name': 'BILD Berlin', 'url': 'https://www.bild.de/feed/regional-berlin.xml'},
]
if data.get("feeds") == previous_default_feeds and isinstance(defaults.get("feeds"), list):
    data["feeds"] = json.loads(json.dumps(defaults["feeds"]))

old_default_nina_codes = [
    {"source": "nina", "name": "Berlin", "code": "110000000000"},
    {"source": "nina", "name": "Hennigsdorf", "code": "120650136136"},
    {"source": "nina", "name": "Oberhavel", "code": "120650000000"},
]
if data.get("nina_codes") == old_default_nina_codes and isinstance(defaults.get("nina_codes"), list):
    data["nina_codes"] = json.loads(json.dumps(defaults["nina_codes"]))

# --- Repair block order and collapse state ---------------------------------
default_block_order = defaults.get("block_order") or ["nina", "weather", "prayer", "system", "markets", "news"]
old_default_block_order = ["weather", "prayer", "nina", "system", "markets", "news"]
valid_block_ids = set(default_block_order)

raw_order = data.get("block_order")
if raw_order == old_default_block_order:
    raw_order = list(default_block_order)
cleaned = []
seen = set()
if isinstance(raw_order, list):
    for item in raw_order:
        key = str(item or "").strip().lower()
        if key in valid_block_ids and key not in seen:
            cleaned.append(key)
            seen.add(key)
for fallback in default_block_order:
    if fallback not in seen:
        cleaned.append(fallback)
        seen.add(fallback)
data["block_order"] = cleaned

collapsed = data.get("collapsed_blocks")
if not isinstance(collapsed, dict):
    collapsed = {}
data["collapsed_blocks"] = {key: bool(collapsed.get(key, False)) for key in default_block_order}

# Atomic write: same-directory tmp + rename. Matches what the server does
# at runtime so an interrupted upgrade can never leave config.json half-written.
tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}.{time.time_ns()}")
try:
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.chmod(0o600)
    tmp.replace(path)
except BaseException:
    try:
        tmp.unlink()
    except FileNotFoundError:
        pass
    raise
print("Konfiguration aktualisiert.")
PY
    chmod 0600 "$HOME/.config/die-lage/config.json" 2>/dev/null || true
fi

# ---- systemd user units -----------------------------------------------------
cp "$BASE_DIR/files/systemd/dielage-cache.service"      "$HOME/.config/systemd/user/dielage-cache.service"
cp "$BASE_DIR/files/systemd/dielage-cache.timer"        "$HOME/.config/systemd/user/dielage-cache.timer"
cp "$BASE_DIR/files/systemd/dielage-cache-boot.service" "$HOME/.config/systemd/user/dielage-cache-boot.service"
cp "$BASE_DIR/files/systemd/dielage-cache-boot.timer"   "$HOME/.config/systemd/user/dielage-cache-boot.timer"
cp "$BASE_DIR/files/systemd/dielage-local-server.service" "$HOME/.config/systemd/user/dielage-local-server.service"


# Apply the user-configured boot/login refresh setting to the systemd timer.
# systemd reads OnStartupSec from the unit file, not from config.json, so the
# generated timer file must be refreshed during install/upgrade.
# Note: the Python heredoc below MUST print exactly "0" or "1" on its last
# line. We wrap the body in try/except so a partial failure (unreadable
# config, unwritable timer) never silently leaves the captured variable
# empty, which the shell would then treat as "disabled".
boot_refresh_enabled=$(python3 - <<'PYINSTALLTIMER'
from pathlib import Path
import json

config_path = Path.home() / ".config/die-lage/config.json"
timer_path = Path.home() / ".config/systemd/user/dielage-cache-boot.timer"
def clamp(value, fallback=120, lo=10, hi=1800):
    try:
        n = int(value)
    except Exception:
        n = fallback
    return max(lo, min(hi, n))

enabled = True
try:
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if not isinstance(config, dict):
            config = {}
    except Exception:
        config = {}

    enabled = bool(config.get("boot_refresh_enabled", True))
    delay = clamp(config.get("boot_refresh_delay_seconds", 120))
    text = f"""[Unit]
Description=Run initial Die Lage cache refresh after login/reboot

[Timer]
OnStartupSec={delay}s
AccuracySec=15s
Unit=dielage-cache-boot.service

[Install]
WantedBy=timers.target
"""
    try:
        if not timer_path.exists() or timer_path.read_text(encoding="utf-8") != text:
            timer_path.write_text(text, encoding="utf-8")
    except Exception:
        # Could not write the timer (e.g. read-only HOME). The systemctl
        # commands below will then do nothing useful; still keep going so
        # the rest of the install completes.
        pass
finally:
    print("1" if enabled else "0")
PYINSTALLTIMER
)

# Every systemctl call below is best-effort. Without a systemd user bus - in a
# container, a chroot, or an SSH session with no user session - daemon-reload
# exits non-zero, and under `set -e` that aborted the whole installer after the
# files were already in place, leaving a half-configured install with no
# explanation. The files matter; wiring up units is a separate concern.
SYSTEMD_OK=1
# DIELAGE_SKIP_SYSTEMD=1 is a release-test hook. Without it, running the
# installer sandbox from an active Plasma session would still talk to the real
# per-user systemd manager and could restart the user's installed Die Lage
# service despite HOME pointing at a temporary directory. Normal installs never
# set this variable.
if [ "${DIELAGE_SKIP_SYSTEMD:-0}" = "1" ]; then
    SYSTEMD_OK=0
else
    if ! systemctl --user daemon-reload >/dev/null 2>&1; then
        SYSTEMD_OK=0
        echo "Hinweis: Kein systemd-User-Bus erreichbar. Dateien wurden installiert," >&2
        echo "die Dienste müssen in einer regulären Desktop-Sitzung aktiviert werden:" >&2
        echo "  systemctl --user daemon-reload" >&2
        echo "  systemctl --user enable --now dielage-local-server.service dielage-cache.timer" >&2
    fi
    systemctl --user enable --now dielage-cache.timer        >/dev/null 2>&1 || true
    # Default to "enabled" if the Python heredoc above produced no output (for
    # example because of a transient subshell error). The user's default in
    # default-config.json is also "enabled", so this preserves the documented
    # behaviour and avoids accidentally disabling the boot timer on upgrades.
    if [ "$boot_refresh_enabled" != "0" ]; then
        systemctl --user enable --now dielage-cache-boot.timer   >/dev/null 2>&1 || true
    else
        systemctl --user disable --now dielage-cache-boot.timer  >/dev/null 2>&1 || true
    fi
    systemctl --user enable --now dielage-local-server.service >/dev/null 2>&1 || true
    systemctl --user restart dielage-local-server.service    >/dev/null 2>&1 || true
fi

# Kick off the first cache refresh WITHOUT waiting for it. Running it inline
# meant the installer blocked on every feed, weather and market request; on a
# slow or filtered connection that turned a two-second install into minutes of
# apparent hang. systemd owns the job, and the widget shows its own loading
# state until the cache lands. DIELAGE_SKIP_FIRST_REFRESH=1 is an internal,
# network-free release-test hook; normal installations never set it.
if [ "${DIELAGE_SKIP_FIRST_REFRESH:-0}" != "1" ]; then
    if [ "$SYSTEMD_OK" -eq 1 ] && command -v systemd-run >/dev/null 2>&1 \
       && systemd-run --user --quiet --collect --unit="dielage-first-refresh-$$" \
            "$HOME/.local/bin/dielage-cache.py" --force >/dev/null 2>&1; then
        :
    else
        # No usable systemd: still populate the cache, but in the background so the
        # installer does not sit waiting on every feed and market request.
        ( "$HOME/.local/bin/dielage-cache.py" --force >/dev/null 2>&1 || true ) &
    fi
fi

# Tell kbuildsycoca6 to rebuild its service cache so the picker sees the new
# metadata. Optional: on Plasma 6 the new applet usually appears anyway.
if [ "${DIELAGE_SKIP_SYSTEMD:-0}" != "1" ] && command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6 --noincremental >/dev/null 2>&1 || true
fi

echo
echo "Fertig."
if [ "$moved_any" -eq 1 ]; then
    echo "Alte Widget-Kopien liegen in: $QUARANTINE"
fi
echo
echo "Wenn das Widget nicht sofort erscheint, einmal Plasma neu starten:"
echo "  systemctl --user restart plasma-plasmashell.service"
echo
echo "Deinstallation: ./uninstall.sh"
