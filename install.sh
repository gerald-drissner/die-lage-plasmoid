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
VERSION="$(python3 -c "import json,sys; print(json.load(open('$BASE_DIR/files/plasmoid/metadata.json'))['KPlugin']['Version'])")"
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
QUARANTINE="$HOME/plasma-dielage-quarantine-$TS"
mkdir -p "$QUARANTINE"
shopt -s nullglob
moved_any=0
for d in "$HOME"/.local/share/plasma/plasmoids/com.drissner.dielage*; do
    if [ -e "$d" ]; then
        mv "$d" "$QUARANTINE"/ 2>/dev/null || true
        moved_any=1
    fi
done
shopt -u nullglob

# Clear only Die-Lage-specific package/QML cache entries.  The old emergency
# cleaner still performs a full Plasma cache reset, but the normal installer
# should not wipe unrelated Plasma caches just to update one applet.
find "$HOME/.cache" -maxdepth 4 \( -iname '*dielage*' -o -iname '*die-lage*' -o -iname '*com.drissner.dielage*' \) -exec rm -rf {} + 2>/dev/null || true

# ---- Install backend scripts -------------------------------------------------
install -m 0755 "$BASE_DIR/files/bin/dielage-cache.py"        "$HOME/.local/bin/dielage-cache.py"
install -m 0755 "$BASE_DIR/files/bin/dielage-server.py"       "$HOME/.local/bin/dielage-server.py"
install -m 0755 "$BASE_DIR/uninstall.sh"                      "$HOME/.local/bin/dielage-uninstall"

# ---- Install plasmoid package -----------------------------------------------
PLASMOID_DIR="$HOME/.local/share/plasma/plasmoids/com.drissner.dielage"
rm -rf "$PLASMOID_DIR"
mkdir -p "$PLASMOID_DIR"
cp -a "$BASE_DIR/files/plasmoid/." "$PLASMOID_DIR/"

# Validate installed metadata before Plasma sees it.
python3 - <<'PY'
from pathlib import Path
import json, sys
p = Path.home() / ".local/share/plasma/plasmoids/com.drissner.dielage/metadata.json"
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
    raise SystemExit("missing installed plasmoid files: " + ", ".join(missing))
print("Plasmoid package OK:", p)
PY

# ---- Install / merge config -------------------------------------------------
cp "$BASE_DIR/files/config/default-config.json" "$HOME/.config/die-lage/default-config.json"

if [ ! -f "$HOME/.config/die-lage/config.json" ]; then
    cp "$BASE_DIR/files/config/default-config.json" "$HOME/.config/die-lage/config.json"
    echo "Frische Konfiguration installiert."
else
    echo "Bestehende Konfiguration wird beibehalten und um neue Felder ergänzt."
    python3 - <<'PY'
from pathlib import Path
import json
import os
import time

path = Path.home() / ".config/die-lage/config.json"
default_prayer = {"city": "Berlin", "country": "Germany", "method": 3}
default_ui = {
    "font_size": 18, "highlight_color": "", "desktop_background_mode": "default",
    "desktop_background_color": "", "news_font_family": "", "news_font_size": 19,
    "news_font_size_offset": 1, "language": "de", "panel_mode": "icon",
    "panel_icon_mode": "dielage", "panel_theme_icon": "view-list-details",
    "panel_warning_badge": True, "panel_no_warnings_mode": "icon",
    "panel_width": 24, "panel_popup_width": 600, "panel_middle_click_refresh": True,
    "block_heading_icons": True, "prayer_upcoming_highlight": True,
    "custom_title": "", "separator_style": "subtle", "news_links_clickable": True,
    "title_style": "accent",
}
default_blocks = {"weather": True, "prayer": True, "nina": True, "markets": True, "system": True, "news": True}
default_system = {"show_info": True, "show_network": True, "show_public_network": False, "show_vpn": True, "vpn_label": "", "show_updates": True}
default_markets = {
    "currencies": ["USD", "GBP", "CHF"],
    "indices": [{"name": "Dow Jones", "symbol": "^DJI"}, {"name": "DAX", "symbol": "^GDAXI"}, {"name": "Nikkei 225", "symbol": "^N225"}],
    "stocks": [], "show_currencies": True, "show_indices": True, "show_stocks": True,
    "twelve_data_api_key": "", "finnhub_api_key": "", "provider_mode": "auto",
}
default_block_order = ["nina", "weather", "prayer", "markets", "news", "system"]
default_collapsed_blocks = {key: False for key in default_block_order}
old_default_block_order = ["weather", "prayer", "nina", "system", "markets", "news"]
default_feeds = [{'limit': 5, 'name': 'Tagesschau', 'url': 'https://www.tagesschau.de/xml/rss2/'},
 {'limit': 5, 'name': 'NTV', 'url': 'https://www.n-tv.de/rss'},
 {'limit': 4, 'name': 'BBC World', 'url': 'https://feeds.bbci.co.uk/news/world/rss.xml'},
 {'limit': 3, 'name': 'Al Jazeera', 'url': 'https://www.aljazeera.com/xml/rss/all.xml'},
 {'limit': 3, 'name': 'The New Arab', 'url': 'https://www.newarab.com/rss'},
 {'limit': 4, 'name': 'Haaretz ME', 'url': 'https://www.haaretz.com/srv/middle-east-news-rss'},
 {'limit': 4, 'name': 'ORF', 'url': 'https://rss.orf.at/news.xml'},
 {'limit': 3, 'name': 'Der Standard', 'url': 'https://www.derstandard.at/rss/inland'},
 {'limit': 3, 'name': 'RBB24', 'url': 'https://www.rbb24.de/aktuell/index.xml/feed=rss.xml'},
 {'limit': 3, 'name': 'Polizei Berlin', 'url': 'https://www.berlin.de/polizei/presse-fahndung/_rss_presse.xml'},
 {'limit': 3, 'name': 'Heise online', 'url': 'https://www.heise.de/newsticker/heise.rdf'}]
previous_default_feeds = [{'limit': 5, 'name': 'Tagesschau', 'url': 'https://www.tagesschau.de/xml/rss2/'},
 {'limit': 5, 'name': 'NTV', 'url': 'https://www.n-tv.de/rss'},
 {'limit': 4, 'name': 'BBC World', 'url': 'https://feeds.bbci.co.uk/news/world/rss.xml'},
 {'limit': 3, 'name': 'Al Jazeera', 'url': 'https://www.aljazeera.com/xml/rss/all.xml'},
 {'limit': 3, 'name': 'The New Arab', 'url': 'https://www.newarab.com/rss'},
 {'limit': 4, 'name': 'Haaretz ME', 'url': 'https://www.haaretz.com/srv/middle-east-news-rss'},
 {'limit': 4, 'name': 'ORF', 'url': 'https://rss.orf.at/news.xml'},
 {'limit': 3, 'name': 'Der Standard', 'url': 'https://www.derstandard.at/rss/inland'},
 {'limit': 3, 'name': 'RBB24', 'url': 'https://www.rbb24.de/aktuell/index.xml/feed=rss.xml'},
 {'limit': 3, 'name': 'BILD Berlin', 'url': 'https://www.bild.de/feed/regional-berlin.xml'}]
index_aliases = {"^DAX": "^GDAXI", "DAX": "^GDAXI", "^NKX": "^N225", "NKX": "^N225"}
valid_block_ids = set(default_block_order)

try:
    data = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    data = {}

if not isinstance(data, dict):
    data = {}

data.setdefault("prayer", default_prayer)
ui = data.setdefault("ui", {})
if not isinstance(ui, dict):
    ui = dict(default_ui)
    data["ui"] = ui
for key, value in default_ui.items():
    if key == "news_font_size" and key not in ui:
        try:
            ui[key] = int(ui.get("font_size", 18)) + int(ui.get("news_font_size_offset", 1))
        except Exception:
            ui[key] = value
    else:
        ui.setdefault(key, value)

# v1.60.6: 1000 px was too wide as a default panel popup. If the stored
# value is exactly the old bundled default, migrate it to the new default.
# Custom values other than 1000 are preserved.
try:
    if int(ui.get("panel_popup_width", 600)) == 1000:
        ui["panel_popup_width"] = 600
except Exception:
    ui["panel_popup_width"] = 600

blocks = data.setdefault("blocks", {})
if not isinstance(blocks, dict):
    blocks = dict(default_blocks)
    data["blocks"] = blocks
for key, value in default_blocks.items():
    blocks.setdefault(key, value)

system = data.setdefault("system", {})
if not isinstance(system, dict):
    system = dict(default_system)
    data["system"] = system
for key, value in default_system.items():
    system.setdefault(key, value)

markets = data.setdefault("markets", {})
if not isinstance(markets, dict):
    markets = dict(default_markets)
    data["markets"] = markets
markets.setdefault("currencies", default_markets["currencies"])
markets.setdefault("indices", default_markets["indices"])
markets.setdefault("show_currencies", default_markets["show_currencies"])
markets.setdefault("show_indices", default_markets["show_indices"])
markets.setdefault("show_stocks", default_markets["show_stocks"])
markets.setdefault("twelve_data_api_key", default_markets["twelve_data_api_key"])
markets.setdefault("finnhub_api_key", default_markets["finnhub_api_key"])
markets.setdefault("provider_mode", default_markets["provider_mode"])
markets.setdefault("stocks", default_markets["stocks"])

if isinstance(markets.get("stocks"), list):
    for item in markets["stocks"]:
        if isinstance(item, dict) and str(item.get("symbol", "")).upper() == "NET" and not item.get("display"):
            item["display"] = "A2PQMN"
if isinstance(markets.get("indices"), list):
    for item in markets["indices"]:
        if isinstance(item, dict):
            raw_symbol = str(item.get("symbol", "")).strip()
            item["symbol"] = index_aliases.get(raw_symbol.upper(), raw_symbol)


# Keep custom feeds untouched. If feeds are missing, use the current defaults.
# If the stored list is exactly the previous bundled default, upgrade it to
# the new default list so local test installs get the refreshed sources.
feeds = data.get("feeds")
if not isinstance(feeds, list):
    data["feeds"] = default_feeds
elif feeds == previous_default_feeds:
    data["feeds"] = default_feeds

data.setdefault("fetch_interval_minutes", 10)
data.setdefault("local_server_port", 8765)
data.setdefault("boot_refresh_enabled", True)
data.setdefault("boot_refresh_delay_seconds", 120)
data.setdefault("nina_codes", data.get("nina_codes", []))

# Repair block_order: keep known ids in stored order, append missing ones.
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

collapsed = data.setdefault("collapsed_blocks", default_collapsed_blocks)
if not isinstance(collapsed, dict):
    collapsed = {}
data["collapsed_blocks"] = {key: bool(collapsed.get(key, False)) for key in default_block_order}

# Atomic write: same-directory tmp + rename. Matches what the server does
# at runtime so an interrupted upgrade can never leave config.json half-written.
tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}.{time.time_ns()}")
try:
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)
except BaseException:
    try:
        tmp.unlink()
    except FileNotFoundError:
        pass
    raise
print("Konfiguration aktualisiert.")
PY
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
if not timer_path.exists() or timer_path.read_text(encoding="utf-8") != text:
    timer_path.write_text(text, encoding="utf-8")
print("1" if enabled else "0")
PYINSTALLTIMER
)

systemctl --user daemon-reload
systemctl --user enable --now dielage-cache.timer        >/dev/null 2>&1 || true
if [ "$boot_refresh_enabled" = "1" ]; then
    systemctl --user enable --now dielage-cache-boot.timer   >/dev/null 2>&1 || true
else
    systemctl --user disable --now dielage-cache-boot.timer  >/dev/null 2>&1 || true
fi
systemctl --user enable --now dielage-local-server.service >/dev/null 2>&1 || true
systemctl --user restart dielage-local-server.service    >/dev/null 2>&1 || true

# Force a first refresh so the cache is populated before the widget renders.
"$HOME/.local/bin/dielage-cache.py" --force >/dev/null 2>&1 || true

# Tell kbuildsycoca6 to rebuild its service cache so the picker sees the new
# metadata. Optional: on Plasma 6 the new applet usually appears anyway.
if command -v kbuildsycoca6 >/dev/null 2>&1; then
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
