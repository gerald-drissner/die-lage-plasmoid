#!/usr/bin/env python3
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import copy
import json
import os
import subprocess
import threading
import time
import urllib.parse

HOME = Path.home()
CACHE_DIR = HOME / ".cache" / "die-lage"
CONFIG_DIR = HOME / ".config" / "die-lage"

CACHE_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)

CACHE_FILE = CACHE_DIR / "rss.json"
CONFIG_FILE = CONFIG_DIR / "config.json"
DEFAULT_CONFIG_FILE = CONFIG_DIR / "default-config.json"
CACHE_SCRIPT = HOME / ".local" / "bin" / "dielage-cache.py"

HOST = "127.0.0.1"
PORT = 8765
REFRESH_LOCK = threading.Lock()
CONFIG_LOCK = threading.Lock()
ALLOWED_ORIGINS = {"", "file://", f"http://{HOST}:{PORT}", f"http://localhost:{PORT}"}

# Hard cap on POST body size. The legitimate config payload is a few kB; this
# limit exists only so a buggy or hostile loopback caller cannot exhaust RAM
# by sending Content-Length: 9999999999. 256 KiB is comfortably above the
# real ceiling (current config tops out below 10 KiB) and well below any
# memory pressure.
MAX_POST_BYTES = 256 * 1024
REQUIRED_POST_CONTENT_TYPE = "application/json"

DEFAULT_CONFIG = {'feeds': [{'limit': 5, 'name': 'Tagesschau', 'url': 'https://www.tagesschau.de/xml/rss2/'},
           {'limit': 5, 'name': 'NTV', 'url': 'https://www.n-tv.de/rss'},
           {'limit': 4, 'name': 'BBC World', 'url': 'https://feeds.bbci.co.uk/news/world/rss.xml'},
           {'limit': 3, 'name': 'Al Jazeera', 'url': 'https://www.aljazeera.com/xml/rss/all.xml'},
           {'limit': 3, 'name': 'The New Arab', 'url': 'https://www.newarab.com/rss'},
           {'limit': 4, 'name': 'Haaretz ME', 'url': 'https://www.haaretz.com/srv/middle-east-news-rss'},
           {'limit': 4, 'name': 'ORF', 'url': 'https://rss.orf.at/news.xml'},
           {'limit': 3, 'name': 'Der Standard', 'url': 'https://www.derstandard.at/rss/inland'},
           {'limit': 3, 'name': 'RBB24', 'url': 'https://www.rbb24.de/aktuell/index.xml/feed=rss.xml'},
           {'limit': 3,
            'name': 'Polizei Berlin',
            'url': 'https://www.berlin.de/polizei/presse-fahndung/_rss_presse.xml'},
           {'limit': 3, 'name': 'Heise online', 'url': 'https://www.heise.de/newsticker/heise.rdf'}],
 'weather_locations': [{'name': 'Hennigsdorf', 'lat': 52.6391, 'lon': 13.209},
                       {'name': 'Berlin', 'lat': 52.5155, 'lon': 13.4546},
                       {'name': 'Bludenz', 'lat': 47.1527, 'lon': 9.8276},
                       {'name': 'El Paso', 'lat': 31.7619, 'lon': -106.485},
                       {'name': 'Nashville', 'lat': 36.1744, 'lon': -86.76796},
                       {'name': 'Alexandria', 'lat': 31.2156, 'lon': 29.9553}],
 'nina_codes': [{'source': 'nina', 'name': 'Berlin', 'code': '110000000000'},
                {'source': 'nina', 'name': 'Hennigsdorf', 'code': '120650136136'},
                {'source': 'nina', 'name': 'Oberhavel', 'code': '120650000000'}],
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
 'system': {'show_info': True,
            'show_network': True,
            'show_public_network': False,
            'show_vpn': True,
            'vpn_label': '',
            'show_updates': True},
 'ui': {'font_size': 18,
        'highlight_color': '',
        'desktop_background_mode': 'default',
        'desktop_background_color': '',
        'news_font_family': '',
        'news_font_size_offset': 1,
        'news_font_size': 19,
        'language': 'de',
        'panel_mode': 'icon',
        'panel_icon_mode': 'dielage',
        'panel_theme_icon': 'view-list-details',
        'panel_warning_badge': True,
        'panel_no_warnings_mode': 'icon',
        'panel_width': 24,
        'panel_popup_width': 600,
        'panel_middle_click_refresh': True,
        'block_heading_icons': True,
        'prayer_upcoming_highlight': True,
        'custom_title': '',
        'separator_style': 'subtle',
        'news_links_clickable': True,
        'title_style': 'accent'},
 'blocks': {'weather': True, 'prayer': True, 'nina': True, 'news': True, 'markets': True, 'system': True},
 'block_order': ['nina', 'weather', 'prayer', 'markets', 'news', 'system'],
 'collapsed_blocks': {'nina': False,
                      'weather': False,
                      'prayer': False,
                      'markets': False,
                      'news': False,
                      'system': False}}
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


def load_default_config() -> dict:
    try:
        data = json.loads(DEFAULT_CONFIG_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return copy.deepcopy(DEFAULT_CONFIG)

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
        if isinstance(data, dict):
            return merge_config(data)
    except Exception:
        pass
    return merge_config(load_default_config())


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
    data.setdefault("nina_codes", copy.deepcopy(defaults["nina_codes"]))
    data.setdefault("prayer", copy.deepcopy(defaults["prayer"]))
    data.setdefault("system", copy.deepcopy(defaults.get("system", {"show_info": True, "show_network": True, "show_public_network": False, "show_vpn": True, "vpn_label": "", "show_updates": True})))
    data.setdefault("fetch_interval_minutes", defaults["fetch_interval_minutes"])

    ui = data.setdefault("ui", {})
    if not isinstance(ui, dict):
        ui = copy.deepcopy(defaults["ui"])
        data["ui"] = ui
    for key, value in defaults["ui"].items():
        ui.setdefault(key, value)

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
    valid_block_ids = ["nina", "weather", "prayer", "markets", "news", "system"]
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

def run_refresh() -> bool:
    # Do not let two fast clicks or one timer + one manual refresh spawn parallel
    # cache processes.  If a refresh is already running, report success with an
    # "already_running" hint instead of blocking another HTTP worker thread.
    if not REFRESH_LOCK.acquire(blocking=False):
        return False
    try:
        subprocess.run(
            [str(CACHE_SCRIPT), "--force"],
            check=True,
            timeout=120,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    finally:
        REFRESH_LOCK.release()

class Handler(BaseHTTPRequestHandler):
    server_version = "DieLageLocal/1"
    sys_version = ""

    def version_string(self) -> str:
        return self.server_version

    def _request_origin(self) -> str:
        return (self.headers.get("Origin") or "").strip()

    def _origin_allowed(self) -> bool:
        origin = self._request_origin()
        if origin in ALLOWED_ORIGINS:
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

    def _send_cors_headers(self):
        origin = self._request_origin()
        if origin and self._origin_allowed():
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def _send_json(self, data, status=200):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self._send_cors_headers()
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
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_HEAD(self):
        if self._reject_if_bad_origin():
            return
        path = urllib.parse.urlparse(self.path).path
        if path in ("/status", "/rss.json", "/config"):
            self.send_response(200)
            self._send_cors_headers()
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
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        if self._reject_if_bad_origin():
            return
        path = urllib.parse.urlparse(self.path).path

        if path == "/status":
            self._send_json({"ok": True, "version": "1.60.5"})
        elif path == "/rss.json":
            self._send_json_file(CACHE_FILE)
        elif path == "/config":
            self._send_json(load_current_config())
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
        if path in ("/config", "/refresh", "/reset") and self._json_post_required():
            return

        if path == "/refresh":
            try:
                did_run = run_refresh()
                self._send_json({"ok": True, "already_running": not did_run})
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, 500)
        elif path == "/config":
            # Save only.  Refresh is triggered separately by the QML client via
            # POST /refresh, so a slow feed/API cannot be reported as
            # "Speichern fehlgeschlagen" after the config was already written.
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length < 0 or length > MAX_POST_BYTES:
                    self._send_json({"ok": False, "error": "payload too large"}, 413)
                    return
                body = self.rfile.read(length).decode("utf-8")
                patch = json.loads(body)
                if not isinstance(patch, dict):
                    raise ValueError("config payload must be a JSON object")
                ensure_config()
                with CONFIG_LOCK:
                    existing = load_config_without_ensure()
                    data = merge_config(deep_update(existing, patch))
                    atomic_write_json(CONFIG_FILE, data)
                self._send_json({"ok": True})
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
                self._send_json({"ok": True})
            except Exception as exc:
                self._send_json({"ok": False, "error": str(exc)}, 500)
        else:
            self._send_json({"error": "not found"}, 404)

    def log_message(self, fmt, *args):
        if os.environ.get("DIELAGE_DEBUG") == "1":
            return super().log_message(fmt, *args)
        return

if __name__ == "__main__":
    ensure_config()
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
