#!/usr/bin/env python3
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import copy
import json
import os
import shutil
import signal
import subprocess
import sys
import importlib.util
import threading
import time
import urllib.parse
import urllib.request
import urllib.error

HOME = Path.home()
CACHE_DIR = HOME / ".cache" / "die-lage"
CONFIG_DIR = HOME / ".config" / "die-lage"

CACHE_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
try:
    CONFIG_DIR.chmod(0o700)
except OSError:
    pass

CACHE_FILE = CACHE_DIR / "rss.json"
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_CONFIG_FILE = CONFIG_DIR / "default-config.json"
CACHE_SCRIPT = HOME / ".local" / "bin" / "dielage-cache.py"
SYSTEMD_USER_DIR = HOME / ".config" / "systemd" / "user"
BOOT_TIMER_FILE = SYSTEMD_USER_DIR / "dielage-cache-boot.timer"

HOST = "127.0.0.1"
DEFAULT_PORT = 8765
PORT_MIN = 8765
PORT_MAX = 8775

def clamp_port(value) -> int:
    try:
        n = int(value)
    except Exception:
        n = DEFAULT_PORT
    return max(PORT_MIN, min(PORT_MAX, n))

def configured_server_port() -> int:
    # Read the port very early, before the HTTP server binds.  Keep this
    # deliberately independent from merge_config() because that function is
    # defined later and may itself need the server constants.
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return clamp_port(data.get("local_server_port", DEFAULT_PORT))
    except Exception:
        pass
    return DEFAULT_PORT

PORT = configured_server_port()
REFRESH_LOCK = threading.Lock()
CONFIG_LOCK = threading.Lock()

def allowed_origins_for_port(port: int) -> set[str]:
    return {"", "file://", f"http://{HOST}:{port}", f"http://localhost:{port}"}

# Hard cap on POST body size. The legitimate config payload is a few kB; this
# limit exists only so a buggy or hostile loopback caller cannot exhaust RAM
# by sending Content-Length: 9999999999. 256 KiB is comfortably above the
# real ceiling (current config tops out below 10 KiB) and well below any
# memory pressure.
MAX_POST_BYTES = 256 * 1024
REQUIRED_POST_CONTENT_TYPE = "application/json"
ALLOWED_REFRESH_BLOCKS = {"weather", "system", "markets", "news"}

# Emergency fallback only. The shipped files/config/default-config.json is the
# single source of truth and is what load_default_config() reads at runtime.
# This literal is generated from that file at release time; do not hand-edit it.
DEFAULT_CONFIG = {'feeds': [{'limit': 5, 'name': 'Tagesschau', 'url': 'https://www.tagesschau.de/xml/rss2/'},
           {'limit': 5, 'name': 'NTV', 'url': 'https://www.n-tv.de/rss'},
           {'limit': 4, 'name': 'BBC World', 'url': 'https://feeds.bbci.co.uk/news/world/rss.xml'},
           {'limit': 3, 'name': 'Al Jazeera', 'url': 'https://www.aljazeera.com/xml/rss/all.xml'},
           {'limit': 3, 'name': 'The New Arab', 'url': 'https://www.newarab.com/rss'},
           {'limit': 4,
            'name': 'Haaretz ME',
            'url': 'https://www.haaretz.com/srv/middle-east-news-rss'},
           {'limit': 4, 'name': 'ORF', 'url': 'https://rss.orf.at/news.xml'},
           {'limit': 3, 'name': 'Der Standard', 'url': 'https://www.derstandard.at/rss/inland'},
           {'limit': 3,
            'name': 'RBB24',
            'url': 'https://www.rbb24.de/aktuell/index.xml/feed=rss.xml'},
           {'limit': 3,
            'name': 'Polizei Berlin',
            'url': 'https://www.berlin.de/polizei/presse-fahndung/_rss_presse.xml'},
           {'limit': 3,
            'name': 'Heise online',
            'url': 'https://www.heise.de/newsticker/heise.rdf'}],
 'weather_locations': [{'name': 'Hennigsdorf', 'lat': 52.6391, 'lon': 13.209},
                       {'name': 'Berlin', 'lat': 52.5155, 'lon': 13.4546},
                       {'name': 'Bludenz', 'lat': 47.1527, 'lon': 9.8276},
                       {'name': 'El Paso', 'lat': 31.7619, 'lon': -106.485},
                       {'name': 'Nashville', 'lat': 36.1744, 'lon': -86.76796},
                       {'name': 'Alexandria', 'lat': 31.2156, 'lon': 29.9553}],
 'nina_codes': [{'name': 'Berlin', 'code': '110000000000', 'source': 'nina'}],
 'prayer': {'city': 'Berlin', 'country': 'Germany', 'method': 3},
 'markets': {'currencies': ['USD', 'GBP', 'CHF'],
             'indices': [{'name': 'Dow Jones', 'symbol': '^DJI'},
                         {'name': 'DAX', 'symbol': '^GDAXI'},
                         {'name': 'Nikkei 225', 'symbol': '^N225'}],
             'twelve_data_api_key': '',
             'finnhub_api_key': '',
             'provider_mode': 'auto',
             'stocks': [],
             'show_currencies': True,
             'show_indices': True,
             'show_stocks': True},
 'fetch_interval_minutes': 10,
 'system_interval_minutes': 3,
 'local_server_port': 8765,
 'boot_refresh_enabled': True,
 'boot_refresh_delay_seconds': 120,
 'ui': {'font_size': 16,
        'highlight_color': '',
        'news_font_family': '',
        'news_font_size_offset': 0,
        'news_font_size': 16,
        'language': 'auto',
        'panel_mode': 'icon',
        'desktop_background_mode': 'default',
        'desktop_background_color': '',
        'custom_title': '',
        'separator_style': 'subtle',
        'news_links_clickable': True,
        'title_style': 'accent',
        'panel_icon_mode': 'dielage',
        'panel_theme_icon': 'view-list-details',
        'panel_warning_badge': True,
        'panel_no_warnings_mode': 'icon',
        'block_heading_icons': True,
        'panel_width': 24,
        'panel_middle_click_refresh': True,
        'prayer_upcoming_highlight': True,
        'panel_popup_width': 600,
        'prayer_upcoming_before_minutes': 45,
        'prayer_now_after_minutes': 1,
        'news_show_age': True,
        'news_age_color_enabled': True,
        'news_age_color_minutes': 120,
        'news_age_recent_color': '',
        'news_age_older_color': ''},
 'blocks': {'weather': True,
            'prayer': True,
            'nina': True,
            'news': True,
            'markets': True,
            'system': True},
 'block_order': ['nina', 'weather', 'prayer', 'system', 'markets', 'news'],
 'system': {'show_info': True,
            'show_network': True,
            'show_public_network': False,
            'show_updates': True,
            'show_vpn': True,
            'vpn_label': ''},
 'collapsed_blocks': {'nina': False,
                      'weather': False,
                      'prayer': False,
                      'markets': False,
                      'news': False,
                      'system': False},
 'weather': {'openweather_api_key': ''}}

INDEX_SYMBOL_ALIASES = {
    "^DAX": "^GDAXI",
    "DAX": "^GDAXI",
    "^NKX": "^N225",
    "NKX": "^N225",
}

def canonical_index_symbol(symbol: str) -> str:
    raw = str(symbol or "").strip()
    if not raw:
        return raw
    return INDEX_SYMBOL_ALIASES.get(raw.upper(), raw)

def migrate_indices(markets: dict) -> None:
    indices = markets.get("indices")
    if not isinstance(indices, list):
        return
    for item in indices:
        if isinstance(item, dict) and "symbol" in item:
            item["symbol"] = canonical_index_symbol(item.get("symbol", ""))


_DEFAULT_CONFIG_CACHE: dict | None = None

def load_default_config() -> dict:
    # Read the shipped defaults once per helper-server process. Returning a
    # deep copy keeps callers free to mutate their config snapshots without
    # accidentally changing the process-wide defaults.
    global _DEFAULT_CONFIG_CACHE
    if _DEFAULT_CONFIG_CACHE is None:
        try:
            data = json.loads(DEFAULT_CONFIG_FILE.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                _DEFAULT_CONFIG_CACHE = data
        except Exception:
            pass
        if _DEFAULT_CONFIG_CACHE is None:
            _DEFAULT_CONFIG_CACHE = copy.deepcopy(DEFAULT_CONFIG)
    return copy.deepcopy(_DEFAULT_CONFIG_CACHE)

def atomic_write_json(path: Path, data: dict) -> None:
    # Write to a unique tmp file in the same directory, then rename atomically.
    # Same-directory guarantees the rename is a metadata-only operation on
    # every sane filesystem, so the destination file never exists in a
    # half-written state. If anything goes wrong (disk full, IO error,
    # KeyboardInterrupt), we clean up the tmp file rather than leaving
    # config.json.tmp.* litter behind.
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}.{time.time_ns()}")
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        # config.json may contain API keys.  Keep the permission invariant even
        # when this server-side writer replaces an existing 0600 file under a
        # permissive umask.
        tmp.chmod(0o600)
        tmp.replace(path)
    except BaseException:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
        except Exception:
            # Best-effort cleanup; surface the original error, not the cleanup error.
            pass
        raise




def clamp_int(value, fallback: int, min_value: int, max_value: int) -> int:
    try:
        n = int(value)
    except Exception:
        n = fallback
    return max(min_value, min(max_value, n))


def boot_refresh_enabled(config: dict) -> bool:
    # User switch for the first forced cache refresh after login/reboot.
    # Default remains enabled because fresh sessions should populate data after
    # networking/VPN has had a short moment to settle.
    return bool(config.get("boot_refresh_enabled", True))


def boot_refresh_delay_seconds(config: dict) -> int:
    # User-configurable delay for the first forced cache refresh after login.
    # Keep the clamp conservative: too low races slow network/VPN startup; too
    # high makes the widget look stale after login. Users can still choose.
    return clamp_int(config.get("boot_refresh_delay_seconds", 120), 120, 10, 1800)


def local_server_port(config: dict) -> int:
    # Keep the configurable helper port in a small known range so the QML side
    # can rediscover the service if the user changes away from the default.
    # This is meant to solve local port conflicts, not to publish the helper.
    return clamp_int(config.get("local_server_port", DEFAULT_PORT), DEFAULT_PORT, PORT_MIN, PORT_MAX)


def boot_timer_unit_text(delay_seconds: int) -> str:
    return f"""[Unit]
Description=Run initial Die Lage cache refresh after login/reboot

[Timer]
OnStartupSec={delay_seconds}s
AccuracySec=15s
Unit=dielage-cache-boot.service

[Install]
WantedBy=timers.target
"""


def apply_boot_timer_config(config: dict) -> None:
    """Best-effort update of the systemd user boot timer.

    Saving settings must not immediately re-arm the boot/login timer.
    OnStartupSec is measured from timer activation, not from the real boot
    timestamp, so using enable --now here would start a fresh countdown every
    time the user saves settings.  We only rewrite the unit when the text
    changed, reload systemd in that case, and keep the timer enabled or
    disabled for the next login/reboot according to the user's setting.
    """
    try:
        SYSTEMD_USER_DIR.mkdir(parents=True, exist_ok=True)
        enabled = boot_refresh_enabled(config)
        delay = boot_refresh_delay_seconds(config)
        text = boot_timer_unit_text(delay)
        current = BOOT_TIMER_FILE.read_text(encoding="utf-8") if BOOT_TIMER_FILE.exists() else None
        changed = current != text
        if changed:
            BOOT_TIMER_FILE.write_text(text, encoding="utf-8")
            subprocess.run(["systemctl", "--user", "daemon-reload"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)
        if enabled:
            if changed:
                subprocess.run(["systemctl", "--user", "reenable", "dielage-cache-boot.timer"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)
            else:
                subprocess.run(["systemctl", "--user", "enable", "dielage-cache-boot.timer"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)
        else:
            subprocess.run(["systemctl", "--user", "disable", "--now", "dielage-cache-boot.timer"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10, check=False)
    except Exception:
        # Do not break normal config saving if systemd is unavailable.
        pass


def clear_cache_files() -> list[str]:
    """Delete Die-Lage cache files only; never touch config.json."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    removed: list[str] = []
    for path in CACHE_DIR.iterdir():
        if not path.is_file():
            continue
        # rss.json is the real cache, feedstate.json holds ETags, failure
        # counters and backoff windows. Leaving the latter behind meant
        # "cache cleared" was not true: a feed still in a 2 h backoff stayed
        # in it, and stale validators could suppress a full refetch.
        if path.name in ("rss.json", "feedstate.json") or path.name.startswith(("rss.json.tmp.", "feedstate.json.tmp.")):
            try:
                path.unlink()
                removed.append(path.name)
            except FileNotFoundError:
                pass
    return removed


def delayed_service_restart() -> None:
    """Ask systemd to restart this service a moment from now.

    The obvious approach - fork a shell that sleeps and then calls systemctl -
    puts the helper process inside this service's own cgroup. With the default
    KillMode=control-group, the stop phase of the restart kills exactly that
    helper. It happened to work because the restart job is already queued in
    the manager by then, but it is a race we do not need to run.

    systemd-run creates a transient unit in its own cgroup, so the trigger
    survives us being torn down. The shell form stays as a fallback for
    systems where systemd-run is unavailable.
    """
    if shutil.which("systemd-run"):
        try:
            completed = subprocess.run(
                [
                    "systemd-run", "--user", "--quiet", "--collect",
                    "--on-active=1",
                    # Unique unit name: a fixed one collides if the user saves
                    # settings twice in quick succession and the first trigger
                    # unit has not been collected yet.
                    f"--unit=dielage-restart-{os.getpid()}-{int(time.time())}",
                    "systemctl", "--user", "restart", "dielage-local-server.service",
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=10,
                check=False,
            )
            # Only skip the fallback when systemd-run actually accepted the job.
            # Returning unconditionally meant a non-zero exit left the service
            # never restarting and the fallback never running.
            if completed.returncode == 0:
                return
        except Exception:
            pass

    subprocess.Popen(
        ["sh", "-c", "sleep 0.35; systemctl --user restart dielage-local-server.service"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def ensure_config() -> None:
    if not CONFIG_FILE.exists():
        with CONFIG_LOCK:
            if not CONFIG_FILE.exists():
                atomic_write_json(CONFIG_FILE, copy.deepcopy(load_default_config()))

def load_current_config() -> dict:
    ensure_config()
    return load_config_without_ensure()


def load_config_without_ensure() -> dict:
    try:
        data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("config is not a JSON object")
        return merge_config(data)
    except Exception as exc:
        # Existing-but-corrupt config is user data, not an invitation to reset
        # silently to defaults. Surface the error and leave the file untouched.
        raise RuntimeError(f"invalid config.json: {type(exc).__name__}") from exc


def deep_update(base: dict, patch: dict) -> dict:
    """Overlay patch onto base without treating missing keys as reset-to-default.

    Nested dictionaries are merged; lists and scalar values replace the old value.
    This keeps the QML full-save path unchanged but makes manual partial POSTs safe.
    """
    for key, value in patch.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            deep_update(base[key], value)
        else:
            base[key] = value
    return base

def merge_config(data: dict) -> dict:
    defaults = copy.deepcopy(load_default_config())
    if not isinstance(data, dict):
        data = {}

    data.setdefault("feeds", copy.deepcopy(defaults["feeds"]))
    data.setdefault("weather_locations", copy.deepcopy(defaults["weather_locations"]))
    weather = data.setdefault("weather", copy.deepcopy(defaults.get("weather", {"openweather_api_key": ""})))
    if not isinstance(weather, dict):
        weather = copy.deepcopy(defaults.get("weather", {"openweather_api_key": ""}))
        data["weather"] = weather
    weather.setdefault("openweather_api_key", defaults.get("weather", {}).get("openweather_api_key", ""))
    data.setdefault("nina_codes", copy.deepcopy(defaults["nina_codes"]))
    old_default_nina_codes = [
        {"source": "nina", "name": "Berlin", "code": "110000000000"},
        {"source": "nina", "name": "Hennigsdorf", "code": "120650136136"},
        {"source": "nina", "name": "Oberhavel", "code": "120650000000"},
    ]
    if data.get("nina_codes") == old_default_nina_codes:
        data["nina_codes"] = copy.deepcopy(defaults["nina_codes"])
    data.setdefault("prayer", copy.deepcopy(defaults["prayer"]))
    data.setdefault("system", copy.deepcopy(defaults.get("system", {"show_info": True, "show_network": True, "show_public_network": False, "show_vpn": True, "vpn_label": "", "show_updates": True})))
    data["fetch_interval_minutes"] = clamp_int(data.get("fetch_interval_minutes", defaults["fetch_interval_minutes"]), defaults["fetch_interval_minutes"], 1, 1440)
    data["system_interval_minutes"] = clamp_int(data.get("system_interval_minutes", defaults.get("system_interval_minutes", 3)), defaults.get("system_interval_minutes", 3), 1, 1440)
    data["local_server_port"] = local_server_port(data)
    data["boot_refresh_enabled"] = boot_refresh_enabled(data)
    data["boot_refresh_delay_seconds"] = boot_refresh_delay_seconds(data)

    ui = data.setdefault("ui", {})
    if not isinstance(ui, dict):
        ui = copy.deepcopy(defaults["ui"])
        data["ui"] = ui
    for key, value in defaults["ui"].items():
        ui.setdefault(key, value)
    ui["font_size"] = clamp_int(ui.get("font_size", defaults["ui"].get("font_size", 16)), defaults["ui"].get("font_size", 16), 12, 34)
    ui["news_font_size"] = clamp_int(ui.get("news_font_size", defaults["ui"].get("news_font_size", 16)), defaults["ui"].get("news_font_size", 16), 10, 42)
    ui["news_font_size_offset"] = clamp_int(ui.get("news_font_size_offset", defaults["ui"].get("news_font_size_offset", 0)), defaults["ui"].get("news_font_size_offset", 0), -3, 6)
    ui["prayer_upcoming_before_minutes"] = clamp_int(ui.get("prayer_upcoming_before_minutes", defaults["ui"].get("prayer_upcoming_before_minutes", 45)), defaults["ui"].get("prayer_upcoming_before_minutes", 45), 1, 180)
    ui["prayer_now_after_minutes"] = clamp_int(ui.get("prayer_now_after_minutes", defaults["ui"].get("prayer_now_after_minutes", 1)), defaults["ui"].get("prayer_now_after_minutes", 1), 1, 30)
    ui["panel_width"] = clamp_int(ui.get("panel_width", defaults["ui"].get("panel_width", 24)), defaults["ui"].get("panel_width", 24), 16, 96)
    ui["panel_popup_width"] = clamp_int(ui.get("panel_popup_width", defaults["ui"].get("panel_popup_width", 600)), defaults["ui"].get("panel_popup_width", 600), 520, 1400)

    blocks = data.setdefault("blocks", {})
    if not isinstance(blocks, dict):
        blocks = copy.deepcopy(defaults["blocks"])
        data["blocks"] = blocks
    for key, value in defaults["blocks"].items():
        blocks.setdefault(key, value)

    markets = data.setdefault("markets", {})
    if not isinstance(markets, dict):
        markets = copy.deepcopy(defaults["markets"])
        data["markets"] = markets
    markets.setdefault("currencies", copy.deepcopy(defaults["markets"]["currencies"]))
    markets.setdefault("indices", copy.deepcopy(defaults["markets"]["indices"]))
    markets.setdefault("show_currencies", defaults["markets"].get("show_currencies", True))
    markets.setdefault("show_indices", defaults["markets"].get("show_indices", True))
    markets.setdefault("show_stocks", defaults["markets"].get("show_stocks", True))
    markets.setdefault("twelve_data_api_key", defaults["markets"].get("twelve_data_api_key", ""))
    markets.setdefault("finnhub_api_key", defaults["markets"].get("finnhub_api_key", ""))
    markets.setdefault("provider_mode", defaults["markets"].get("provider_mode", "auto"))
    markets.setdefault("stocks", copy.deepcopy(defaults["markets"].get("stocks", [])))
    migrate_indices(markets)

    system = data.setdefault("system", {})
    if not isinstance(system, dict):
        system = copy.deepcopy(defaults.get("system", {"show_info": True, "show_network": True, "show_public_network": False, "show_vpn": True, "vpn_label": "", "show_updates": True}))
        data["system"] = system
    for key, value in defaults.get("system", {"show_info": True, "show_network": True, "show_public_network": False, "show_vpn": True, "vpn_label": "", "show_updates": True}).items():
        system.setdefault(key, value)

    # New in v1.51: block_order is a top-level list. Repair it the same way
    # the QML does: keep known ids in their stored order, drop unknowns,
    # append any missing ones at the end. This way a stale config from an
    # older version automatically gains the default order without losing
    # the user's other settings.
    # Take the canonical order from the shipped defaults instead of repeating
    # it here. The hardcoded list had already drifted: it ordered system last,
    # while default-config.json puts system before markets.
    valid_block_ids = [str(x) for x in (defaults.get("block_order") or []) if str(x).strip()]
    if not valid_block_ids:
        valid_block_ids = ["nina", "weather", "prayer", "system", "markets", "news"]
    raw_order = data.get("block_order")
    cleaned_order: list[str] = []
    seen_ids: set[str] = set()
    if isinstance(raw_order, list):
        for item in raw_order:
            key = str(item or "").strip().lower()
            if key in valid_block_ids and key not in seen_ids:
                cleaned_order.append(key)
                seen_ids.add(key)
    for fallback in valid_block_ids:
        if fallback not in seen_ids:
            cleaned_order.append(fallback)
            seen_ids.add(fallback)
    data["block_order"] = cleaned_order

    collapsed = data.setdefault("collapsed_blocks", copy.deepcopy(defaults.get("collapsed_blocks", {})))
    if not isinstance(collapsed, dict):
        collapsed = {}
    data["collapsed_blocks"] = {key: bool(collapsed.get(key, False)) for key in valid_block_ids}

    return data

# Exit code dielage-cache.py uses when another cache process holds the file
# lock. Treated as "already running", not as a completed refresh.
EXIT_LOCK_BUSY = 75

# Refresh state shared between the HTTP workers and the background job thread.
REFRESH_STATE = {
    "running": False,
    "block": "",
    "started": 0.0,
    "finished": 0.0,
    "ok": True,
    "error": "",
    "already_running": False,
}
REFRESH_STATE_LOCK = threading.Lock()


def _refresh_state_snapshot() -> dict:
    with REFRESH_STATE_LOCK:
        return dict(REFRESH_STATE)


def _run_refresh_job(block: str | None) -> None:
    """Run the cache helper to completion in a background thread.

    Refresh used to run inline in the HTTP handler, so the client had to hold a
    request open for as long as the whole fetch took - up to the 120 s server
    timeout. The QML side gives up after 25 s and concludes the helper is dead,
    which it is not. The job now runs here and the client polls /refresh-status
    instead, so no request is ever long-lived.
    """
    ok, error, busy = True, "", False
    try:
        # Global refresh intentionally forces every block. A block refresh must
        # stay block-scoped; --block is itself considered manual by the cache
        # helper, so it already bypasses feed backoff without --force.
        args = [str(CACHE_SCRIPT), "--force"] if not block else [str(CACHE_SCRIPT), "--block", block]
        completed = subprocess.run(
            args,
            check=False,
            timeout=300,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if completed.returncode == EXIT_LOCK_BUSY:
            # The systemd timer got there first; its result lands in the same
            # cache file, so this is not an error.
            busy = True
        elif completed.returncode != 0:
            ok, error = False, f"cache helper exited with {completed.returncode}"
    except subprocess.TimeoutExpired:
        ok, error = False, "cache helper timed out"
    except Exception as exc:
        ok, error = False, str(exc)[:200]
    finally:
        with REFRESH_STATE_LOCK:
            REFRESH_STATE.update({
                "running": False,
                "finished": time.time(),
                "ok": ok,
                "error": error,
                "already_running": busy,
            })
        REFRESH_LOCK.release()


def start_refresh(block: str | None = None) -> dict:
    """Start a refresh if none is in flight. Returns immediately."""
    if not REFRESH_LOCK.acquire(blocking=False):
        return {"ok": True, "started": False, "already_running": True}

    with REFRESH_STATE_LOCK:
        REFRESH_STATE.update({
            "running": True,
            "block": block or "",
            "started": time.time(),
            "finished": 0.0,
            "ok": True,
            "error": "",
            "already_running": False,
        })

    thread = threading.Thread(target=_run_refresh_job, args=(block,), daemon=True)
    try:
        thread.start()
    except Exception as exc:
        # Thread creation itself can fail under severe resource pressure.  Do
        # not leave the single-flight lock held forever in that case.
        with REFRESH_STATE_LOCK:
            REFRESH_STATE.update({
                "running": False,
                "finished": time.time(),
                "ok": False,
                "error": f"could not start refresh worker: {exc}"[:200],
                "already_running": False,
            })
        REFRESH_LOCK.release()
        raise
    return {"ok": True, "started": True, "already_running": False}


def _command_status(command: str, label: str, note: str = "") -> dict:
    path = shutil.which(command)
    return {
        "id": command,
        "label": label,
        "installed": bool(path),
        "path": path or "",
        "note": note,
    }


def _module_status(module: str, label: str, note: str = "") -> dict:
    found = importlib.util.find_spec(module) is not None
    return {
        "id": module,
        "label": label,
        "installed": found,
        "path": "python module" if found else "",
        "note": note,
    }


class JsonBodyError(ValueError):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = int(status)


def read_json_post_body(handler) -> dict:
    raw_length = handler.headers.get("Content-Length")
    if raw_length is None:
        raise JsonBodyError(411, "missing Content-Length")
    try:
        length = int(raw_length)
    except (TypeError, ValueError):
        raise JsonBodyError(400, "invalid Content-Length") from None
    if length <= 0:
        return {}
    if length > MAX_POST_BYTES:
        raise JsonBodyError(413, "payload too large")
    try:
        body = handler.rfile.read(length).decode("utf-8")
    except UnicodeDecodeError:
        raise JsonBodyError(400, "request body is not UTF-8") from None
    try:
        data = json.loads(body or "{}")
    except json.JSONDecodeError as exc:
        raise JsonBodyError(400, f"invalid JSON: {exc.msg}") from None
    if not isinstance(data, dict):
        raise JsonBodyError(400, "JSON body must be an object")
    return data


def _api_probe_json(url: str, headers: dict[str, str], max_bytes: int = 300_000) -> dict:
    request_headers = {"User-Agent": "DieLage/2.1.7 (+https://github.com/gerald-drissner/die-lage-plasmoid)"}
    request_headers.update(headers)
    req = urllib.request.Request(url, headers=request_headers)
    with urllib.request.urlopen(req, timeout=12) as resp:
        raw = resp.read(max_bytes + 1)
    if len(raw) > max_bytes:
        raise ValueError("response too large")
    payload = json.loads(raw.decode("utf-8", errors="replace"))
    if not isinstance(payload, dict):
        raise ValueError("invalid JSON response")
    return payload


def check_single_market_api(provider: str, key: str) -> dict:
    key = str(key or "").strip()
    if not key:
        return {"configured": False, "ok": False, "message": "missing"}
    try:
        if provider == "twelve":
            payload = _api_probe_json(
                "https://api.twelvedata.com/quote?symbol=AAPL&timezone=Europe%2FBerlin",
                {"Authorization": f"apikey {key}"},
            )
            if payload.get("status") == "error" or payload.get("code"):
                return {"configured": True, "ok": False, "message": str(payload.get("message") or payload.get("code") or "Twelve Data error")}
            price = payload.get("close") or payload.get("price") or payload.get("last")
            if price is None:
                return {"configured": True, "ok": False, "message": "no quote returned"}
            return {"configured": True, "ok": True, "message": "AAPL quote received"}
        if provider == "finnhub":
            payload = _api_probe_json(
                "https://finnhub.io/api/v1/quote?symbol=AAPL",
                {"X-Finnhub-Token": key},
                max_bytes=200_000,
            )
            if payload.get("error"):
                return {"configured": True, "ok": False, "message": str(payload.get("error"))}
            price = payload.get("c")
            try:
                if price is not None and float(price) > 0:
                    return {"configured": True, "ok": True, "message": "AAPL quote received"}
            except Exception:
                pass
            return {"configured": True, "ok": False, "message": "no quote returned"}
    except Exception as exc:
        return {"configured": True, "ok": False, "message": str(exc)[:180]}
    return {"configured": False, "ok": False, "message": "unknown provider"}


def check_market_apis(twelve_key: str, finnhub_key: str) -> dict:
    checks = {
        "twelve": check_single_market_api("twelve", twelve_key),
        "finnhub": check_single_market_api("finnhub", finnhub_key),
    }
    configured = [item for item in checks.values() if item.get("configured")]
    ok = bool(configured) and all(item.get("ok") for item in configured)
    return {"ok": ok, "checks": checks}


def check_openweather_api(key: str, lat=52.52, lon=13.405, language: str = "en") -> dict:
    """Validate an unsaved OpenWeather key with one lightweight current-weather request."""
    key = str(key or "").strip()
    if not key:
        return {"ok": False, "configured": False, "reason": "missing", "message": "missing key"}
    try:
        lat_f = float(lat)
        lon_f = float(lon)
        if not (-90 <= lat_f <= 90 and -180 <= lon_f <= 180):
            raise ValueError
    except Exception:
        lat_f, lon_f = 52.52, 13.405
    lang = "de" if str(language or "").lower().startswith("de") else "en"
    params = urllib.parse.urlencode({
        "lat": lat_f,
        "lon": lon_f,
        "appid": key,
        "units": "metric",
        "lang": lang,
    })
    url = "https://api.openweathermap.org/data/2.5/weather?" + params
    try:
        payload = _api_probe_json(url, {}, max_bytes=200_000)
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return {"ok": False, "configured": True, "reason": "unauthorized", "message": "HTTP 401"}
        if exc.code == 429:
            return {"ok": False, "configured": True, "reason": "rate_limited", "message": "HTTP 429"}
        return {"ok": False, "configured": True, "reason": "http_error", "message": f"HTTP {exc.code}"}
    except Exception as exc:
        # Do not echo a full exception string here: some URL-related exceptions
        # can contain the request URL, which would include the API key.
        return {"ok": False, "configured": True, "reason": "network", "message": type(exc).__name__}

    main = payload.get("main") if isinstance(payload.get("main"), dict) else {}
    if main.get("temp") is None:
        return {"ok": False, "configured": True, "reason": "invalid_response", "message": "no temperature returned"}
    return {
        "ok": True,
        "configured": True,
        "reason": "ok",
    }


def tool_status() -> dict:
    """Return the helper/runtime tools Die Lage can use on this machine."""
    python_item = {
        "id": "python3",
        "label": "Python 3",
        "installed": True,
        "path": sys.executable or "python3",
        "note": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
    }

    required = [
        python_item,
        _command_status("systemctl", "systemctl", "systemd user services and timers"),
    ]

    recommended = [
        _command_status("unzip", "unzip", "unpacks the full installer ZIP"),
        _module_status("defusedxml", "python3-defusedxml", "safer RSS/Atom XML parsing"),
        _command_status("curl", "curl", "manual status/debug checks"),
        _command_status("kbuildsycoca6", "kbuildsycoca6", "refreshes Plasma's service cache after install"),
    ]

    optional = [
        _command_status("ip", "iproute2 / ip", "network interface and route detection"),
        _command_status("nmcli", "NetworkManager / nmcli", "VPN/network connection names"),
        _command_status("resolvectl", "resolvectl", "DNS server display"),
        _command_status("lspci", "lspci", "GPU hardware detection"),
        _command_status("lscpu", "lscpu", "CPU model fallback"),
        _command_status("nvidia-smi", "nvidia-smi", "NVIDIA GPU/driver details"),
        _command_status("checkupdates", "checkupdates", "Arch update count"),
        _command_status("pacman", "pacman", "Arch package update fallback"),
        _command_status("apt", "apt", "Debian/Ubuntu update count"),
        _command_status("dnf", "dnf", "Fedora/RHEL update count"),
        _command_status("zypper", "zypper", "openSUSE update count"),
        _command_status("mullvad", "mullvad", "Mullvad VPN status"),
        _command_status("warp-cli", "warp-cli", "Cloudflare WARP status"),
        _command_status("tailscale", "tailscale", "Tailscale status"),
        _command_status("nordvpn", "nordvpn", "NordVPN status"),
    ]

    return {
        "ok": True,
        "service": "com.drissner.dielage",
        "version": "2.1.7",
        "required": required,
        "recommended": recommended,
        "optional": optional,
        "missing_required": [item for item in required if not item.get("installed")],
        "missing_recommended": [item for item in recommended if not item.get("installed")],
    }

class Handler(BaseHTTPRequestHandler):
    server_version = "DieLageLocal/1"
    sys_version = ""
    # Drop connections that stall mid-request. The helper only ever talks to
    # the local plasmoid, but an idle half-open socket should not pin a worker
    # thread for the lifetime of the session.
    timeout = 20

    def version_string(self) -> str:
        return self.server_version

    def _request_origin(self) -> str:
        return (self.headers.get("Origin") or "").strip()

    def _origin_allowed(self) -> bool:
        origin = self._request_origin()
        if origin in allowed_origins_for_port(PORT):
            return True
        # Some Qt/QML builds send file://... as Origin; browsers normally send
        # http(s) origins.  Allow local file origins for the plasmoid, reject
        # ordinary websites so they cannot read config.json or API keys via CORS.
        # Do NOT allow Origin: null: sandboxed iframes and data/blob/file based
        # browser contexts can use that origin and would otherwise be able to
        # read /config when the response echoes Access-Control-Allow-Origin:null.
        return origin.startswith("file://")

    def _json_post_required(self) -> bool:
        ctype = (self.headers.get("Content-Type") or "").split(";", 1)[0].strip().lower()
        if ctype == REQUIRED_POST_CONTENT_TYPE:
            return False
        self._send_json({"ok": False, "error": "Content-Type must be application/json"}, 415)
        return True

    def _reject_if_bad_origin(self) -> bool:
        if self._origin_allowed():
            return False
        self._send_json({"ok": False, "error": "forbidden origin"}, 403)
        return True

    def _send_security_headers(self):
        # The responses are JSON only and are never meant to be rendered or
        # embedded. These headers cost nothing and close off content sniffing
        # and framing tricks if a browser ever reaches the loopback port.
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")

    def _send_cors_headers(self):
        self.send_header("Vary", "Origin")
        origin = self._request_origin()
        if origin and self._origin_allowed():
            self.send_header("Access-Control-Allow-Origin", origin)

    def _send_json(self, data, status=200):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self._send_cors_headers()
        self._send_security_headers()
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def _send_json_file(self, path: Path):
        if not path.exists():
            self._send_json({"error": "not found"}, 404)
            return

        payload = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self._send_cors_headers()
        self._send_security_headers()
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_HEAD(self):
        if self._reject_if_bad_origin():
            return
        path = urllib.parse.urlparse(self.path).path
        if path in ("/status", "/rss.json", "/config", "/tools", "/refresh-status", "/check-market-apis", "/check-weather-api"):
            self.send_response(200)
            self._send_cors_headers()
            self._send_security_headers()
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
        else:
            self._send_json({"error": "not found"}, 404)

    def _method_not_allowed(self):
        if self._reject_if_bad_origin():
            return
        self._send_json({"ok": False, "error": "method not allowed"}, 405)

    def do_PUT(self):
        self._method_not_allowed()

    def do_DELETE(self):
        self._method_not_allowed()

    def do_OPTIONS(self):
        if self._reject_if_bad_origin():
            return
        self.send_response(204)
        self._send_cors_headers()
        self._send_security_headers()
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self._reject_if_bad_origin():
            return
        path = urllib.parse.urlparse(self.path).path

        if path == "/status":
            self._send_json({"ok": True, "service": "com.drissner.dielage", "version": "2.1.7", "local_server_port": PORT, "port_range_min": PORT_MIN, "port_range_max": PORT_MAX})
        elif path == "/rss.json":
            self._send_json_file(CACHE_FILE)
        elif path == "/config":
            try:
                self._send_json(load_current_config())
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, 500)
        elif path == "/refresh-status":
            state = _refresh_state_snapshot()
            self._send_json({
                "ok": True,
                "running": bool(state["running"]),
                "block": state["block"],
                "finished": state["finished"],
                "last_ok": bool(state["ok"]),
                "error": state["error"],
                "already_running": bool(state["already_running"]),
            })
        elif path == "/tools":
            self._send_json(tool_status())
        else:
            self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        if self._reject_if_bad_origin():
            return
        path = urllib.parse.urlparse(self.path).path

        # State-changing endpoints intentionally require application/json.
        # This blocks old-fashioned CSRF vectors such as plain HTML forms or
        # no-cors text/plain fetches that might omit an Origin header.  QML sets
        # the header explicitly for /config, /refresh and /reset.
        if path in ("/config", "/refresh", "/refresh-block", "/reset", "/clear-cache", "/restart", "/check-market-apis", "/check-weather-api") and self._json_post_required():
            return

        if path == "/refresh":
            try:
                self._send_json(start_refresh())
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, 500)
        elif path == "/refresh-block":
            try:
                payload = read_json_post_body(self)
                block = str(payload.get("block", "")).strip().lower()
                if block not in ALLOWED_REFRESH_BLOCKS:
                    self._send_json({"ok": False, "error": "invalid block"}, 400)
                    return
                result = start_refresh(block)
                result["block"] = block
                self._send_json(result)
            except JsonBodyError as exc:
                self._send_json({"ok": False, "error": str(exc)}, exc.status)
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, 500)
        elif path == "/config":
            # Save only.  Refresh is triggered separately by the QML client via
            # POST /refresh, so a slow feed/API cannot be reported as
            # "Speichern fehlgeschlagen" after the config was already written.
            try:
                raw_length = self.headers.get("Content-Length")
                if raw_length is None:
                    self._send_json({"ok": False, "error": "missing Content-Length"}, 411)
                    return
                try:
                    length = int(raw_length)
                except (TypeError, ValueError):
                    self._send_json({"ok": False, "error": "invalid Content-Length"}, 400)
                    return
                if length <= 0:
                    self._send_json({"ok": False, "error": "empty JSON body"}, 400)
                    return
                if length > MAX_POST_BYTES:
                    self._send_json({"ok": False, "error": "payload too large"}, 413)
                    return
                body = self.rfile.read(length).decode("utf-8")
                try:
                    patch = json.loads(body)
                except json.JSONDecodeError as exc:
                    self._send_json({"ok": False, "error": f"invalid JSON: {exc.msg}"}, 400)
                    return
                if not isinstance(patch, dict):
                    self._send_json({"ok": False, "error": "config payload must be a JSON object"}, 400)
                    return
                ensure_config()
                with CONFIG_LOCK:
                    existing = load_config_without_ensure()
                    old_port = local_server_port(existing)
                    data = merge_config(deep_update(existing, patch))
                    new_port = local_server_port(data)
                    atomic_write_json(CONFIG_FILE, data)
                    apply_boot_timer_config(data)
                self._send_json({"ok": True, "local_server_port": new_port, "server_restart_required": old_port != new_port})
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, 500)
        elif path == "/check-market-apis":
            try:
                payload = read_json_post_body(self)
                self._send_json(check_market_apis(payload.get("twelve_data_api_key", ""), payload.get("finnhub_api_key", "")))
            except JsonBodyError as exc:
                self._send_json({"ok": False, "error": str(exc)}, exc.status)
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, 500)
        elif path == "/check-weather-api":
            try:
                payload = read_json_post_body(self)
                self._send_json(check_openweather_api(
                    payload.get("openweather_api_key", ""),
                    payload.get("lat", 52.52),
                    payload.get("lon", 13.405),
                    payload.get("language", "en"),
                ))
            except JsonBodyError as exc:
                self._send_json({"ok": False, "error": str(exc)}, exc.status)
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, 500)
        elif path == "/clear-cache":
            try:
                removed = clear_cache_files()
                self._send_json({"ok": True, "removed": removed})
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, 500)
        elif path == "/restart":
            try:
                # Do not restart while another request is still saving config or
                # rewriting the boot timer.  The lock is normally released quickly;
                # waiting here prevents killing ourselves mid-write.
                with CONFIG_LOCK:
                    pass
                self._send_json({"ok": True, "restarting": True})
                delayed_service_restart()
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, 500)
        elif path == "/reset":
            # Reset to defaults: overwrite config.json with the shipped default.
            # The cache is not touched here; the QML client will call /refresh
            # next and the user sees fresh data with default feeds and places.
            try:
                defaults = copy.deepcopy(load_default_config())
                with CONFIG_LOCK:
                    atomic_write_json(CONFIG_FILE, defaults)
                    apply_boot_timer_config(defaults)
                self._send_json({"ok": True})
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, 500)
        else:
            self._send_json({"error": "not found"}, 404)

    def log_message(self, fmt, *args):
        if os.environ.get("DIELAGE_DEBUG") == "1":
            return super().log_message(fmt, *args)
        return

class LocalServer(ThreadingHTTPServer):
    # daemon_threads is already the ThreadingHTTPServer default; naming it here
    # documents that worker threads must never keep the process alive.
    daemon_threads = True
    # Loopback-only listener: a queue this size is generous for one plasmoid.
    request_queue_size = 16


if __name__ == "__main__":
    ensure_config()
    try:
        apply_boot_timer_config(load_current_config())
    except Exception:
        pass

    httpd = LocalServer((HOST, PORT), Handler)

    def _shutdown(signum, frame):
        # systemd sends SIGTERM on stop/restart. Closing the listening socket
        # explicitly means the next start can bind immediately instead of
        # tripping over a lingering socket in the restart window.
        try:
            httpd.server_close()
        finally:
            raise SystemExit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        httpd.serve_forever()
    finally:
        try:
            httpd.server_close()
        except Exception:
            pass
