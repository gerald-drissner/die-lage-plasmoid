#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone, timedelta
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None
import concurrent.futures
import copy
import csv
import email.utils
import fcntl
import getpass
import gzip
import html
import os
import io
import json
import platform
import shutil
import socket
import ssl
import subprocess
import re
import sys
import time
import zlib
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
try:
    from defusedxml.ElementTree import fromstring as safe_xml_fromstring
except Exception:
    safe_xml_fromstring = ET.fromstring

BASE_CONFIG_DIR = Path.home() / ".config" / "die-lage"
BASE_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR = Path.home() / ".cache" / "die-lage"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# config.json can hold Twelve Data and Finnhub API keys, so it should not be
# readable by other local accounts. Tighten on every start; this is cheap and
# also repairs installs created before v2.1.1 under a permissive umask.
def _restrict(path: Path, mode: int) -> None:
    try:
        path.chmod(mode)
    except Exception:
        pass


_restrict(BASE_CONFIG_DIR, 0o700)
_restrict(OUT_DIR, 0o700)

CONFIG = BASE_CONFIG_DIR / "config.json"
CACHE = OUT_DIR / "rss.json"

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

FALLBACK_DEFAULT_CONFIG = copy.deepcopy(DEFAULT_CONFIG)
DEFAULT_CONFIG_FILE = BASE_CONFIG_DIR / "default-config.json"

def load_default_config() -> dict:
    # Keep the shipped default-config.json as the primary source of truth.
    # The inline dict above remains only as a last-resort fallback for broken
    # installs, because a cache refresh should not fail merely because the
    # defaults file was removed.
    try:
        data = json.loads(DEFAULT_CONFIG_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return copy.deepcopy(FALLBACK_DEFAULT_CONFIG)

DEFAULT_CONFIG = load_default_config()

UA = "DieLage/2.1.7 (+https://github.com/gerald-drissner/die-lage-plasmoid)"

REFRESHABLE_BLOCKS = {"weather", "system", "markets", "news"}

def forced_refresh_blocks() -> set[str]:
    """Return block ids requested through --block/--refresh-block arguments."""
    out: set[str] = set()
    args = sys.argv[1:]
    for flag in ("--block", "--refresh-block", "--only-block"):
        pos = 0
        while True:
            try:
                idx = args.index(flag, pos)
            except ValueError:
                break
            if idx + 1 < len(args):
                block = str(args[idx + 1]).strip().lower()
                if block in REFRESHABLE_BLOCKS:
                    out.add(block)
            pos = idx + 2
    for arg in args:
        if arg.startswith("--block=") or arg.startswith("--refresh-block=") or arg.startswith("--only-block="):
            block = arg.split("=", 1)[1].strip().lower()
            if block in REFRESHABLE_BLOCKS:
                out.add(block)
    return out
# Exit code used when another cache process already holds the refresh lock.
# The local server translates it into already_running:true. Exiting 0 here made
# a contended refresh look like a completed one, so the widget reloaded the
# unchanged cache and the user saw nothing happen.
EXIT_LOCK_BUSY = 75


def manual_refresh() -> bool:
    """True when a human asked for this refresh, not the systemd timer.

    Both --force (global refresh button) and --block (per-block refresh button)
    are manual. Only --force counted before, so the News block's own retry
    silently obeyed the feed backoff and returned instantly without asking the
    publisher anything.
    """
    args = sys.argv[1:]
    if "--force" in args:
        return True
    for arg in args:
        if arg in ("--block", "--refresh-block", "--only-block"):
            return True
        if arg.startswith(("--block=", "--refresh-block=", "--only-block=")):
            return True
    return False


MARKET_TIMEZONE = "Europe/Berlin"
SAFE_SUBPROCESS_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
SAFE_SUBPROCESS_ENV = {**os.environ, "PATH": SAFE_SUBPROCESS_PATH}

# Only allow http/https in user-supplied URLs. Without this guard, a config
# pointing at file:// could read local files, and ftp:// or other schemes
# expand attack surface for no benefit. The server only listens on 127.0.0.1
# so this is defence in depth, not a critical hole.
ALLOWED_URL_SCHEMES = ("http", "https")

WEATHER_CODES = {
    0: "Klar", 1: "Überwiegend klar", 2: "Teils bewölkt", 3: "Bewölkt",
    45: "Nebel", 48: "Reifnebel",
    51: "Leichter Niesel", 53: "Niesel", 55: "Starker Niesel",
    61: "Leichter Regen", 63: "Regen", 65: "Starker Regen",
    71: "Leichter Schnee", 73: "Schnee", 75: "Starker Schnee", 77: "Schneekörner",
    80: "Leichte Schauer", 81: "Schauer", 82: "Starke Schauer",
    85: "Leichte Schneeschauer", 86: "Starke Schneeschauer",
    95: "Gewitter", 96: "Gewitter mit leichtem Hagel", 99: "Gewitter mit starkem Hagel"
}

WEATHER_CODES_EN = {
    0: "Clear", 1: "Mostly clear", 2: "Partly cloudy", 3: "Cloudy",
    45: "Fog", 48: "Rime fog",
    51: "Light drizzle", 53: "Drizzle", 55: "Heavy drizzle",
    61: "Light rain", 63: "Rain", 65: "Heavy rain",
    71: "Light snow", 73: "Snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Light showers", 81: "Showers", 82: "Heavy showers",
    85: "Light snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm with light hail", 99: "Thunderstorm with heavy hail",
}

def system_language() -> str:
    raw = (os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or "").strip().lower()
    return "de" if raw.startswith("de") else "en"


def ui_language(config: dict) -> str:
    ui = config.get("ui", {}) if isinstance(config.get("ui", {}), dict) else {}
    lang = str(ui.get("language", "auto") or "auto").strip().lower()
    if lang.startswith("de"):
        return "de"
    if lang.startswith("en"):
        return "en"
    return system_language()

def is_english(config: dict) -> bool:
    return ui_language(config) == "en"

def atomic_write_json(path: Path, data: dict) -> None:
    tmp = path.with_name(f"{path.name}.tmp.{os.getpid()}.{time.time_ns()}")
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        # Set the mode on the temp file before the rename, so the destination
        # is never briefly world-readable under a permissive umask.
        _restrict(tmp, 0o600)
        tmp.replace(path)
    except BaseException:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
        except Exception:
            pass
        raise

def ensure_config() -> None:
    if not CONFIG.exists():
        atomic_write_json(CONFIG, copy.deepcopy(DEFAULT_CONFIG))

def clamp_int(value, fallback: int, min_value: int, max_value: int) -> int:
    try:
        n = int(value)
    except Exception:
        n = fallback

    return max(min_value, min(max_value, n))

def cache_timestamp_fallback() -> float:
    try:
        return float(CACHE.stat().st_mtime)
    except Exception:
        return 0.0

def refresh_plan(config: dict, old: dict | None = None) -> dict[str, bool | float]:
    """Decide which parts of the cache need rebuilding.

    The main interval controls network-heavy dashboard data such as RSS,
    weather, warnings, prayer times and markets.  The system interval controls
    local system, VPN, DNS, public-network and update-count data.  Keeping them
    separate lets the System block stay current without refetching every feed
    or market endpoint every few minutes.
    """
    if "--force" in sys.argv:
        return {"main": True, "system": True, "now": time.time()}

    # A manual block refresh is exact, not an invitation to refresh whichever
    # scheduled interval happens to be due at the same instant. build_cache()
    # below applies the requested block explicitly.
    if forced_refresh_blocks():
        return {"main": False, "system": False, "now": time.time()}

    if not CACHE.exists():
        return {"main": True, "system": True, "now": time.time()}

    now = time.time()
    main_minutes = clamp_int(config.get("fetch_interval_minutes", 10), 10, 1, 1440)
    system_minutes = clamp_int(config.get("system_interval_minutes", 3), 3, 1, 1440)

    refresh = {}
    if isinstance(old, dict):
        refresh = old.get("_refresh", {}) if isinstance(old.get("_refresh", {}), dict) else {}

    fallback = cache_timestamp_fallback()
    try:
        main_last = float(refresh.get("main", fallback) or fallback)
    except Exception:
        main_last = fallback
    try:
        system_last = float(refresh.get("system", fallback) or fallback)
    except Exception:
        system_last = fallback

    return {
        "main": (now - main_last) >= main_minutes * 60,
        "system": (now - system_last) >= system_minutes * 60,
        "now": now,
    }

def cache_is_fresh(config: dict) -> bool:
    if "--force" in sys.argv or forced_refresh_blocks():
        return False

    old = load_old() if CACHE.exists() else {}
    plan = refresh_plan(config, old)
    return not bool(plan.get("main")) and not bool(plan.get("system"))

def load_config() -> dict:
    ensure_config()
    try:
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("config is not a JSON object")
    except Exception as exc:
        # Never pretend a corrupt user config is an empty/default config. Doing
        # so can make the UI appear reset and a later save can overwrite the
        # only copy of hand-edited feeds or API keys. Keep the last good cache
        # and fail the refresh instead.
        raise RuntimeError(f"invalid config.json: {type(exc).__name__}") from exc

    data.setdefault("feeds", copy.deepcopy(DEFAULT_CONFIG["feeds"]))
    data.setdefault("weather_locations", copy.deepcopy(DEFAULT_CONFIG["weather_locations"]))
    weather = data.setdefault("weather", copy.deepcopy(DEFAULT_CONFIG.get("weather", {"openweather_api_key": ""})))
    if not isinstance(weather, dict):
        weather = copy.deepcopy(DEFAULT_CONFIG.get("weather", {"openweather_api_key": ""}))
        data["weather"] = weather
    weather.setdefault("openweather_api_key", DEFAULT_CONFIG.get("weather", {}).get("openweather_api_key", ""))
    data.setdefault("nina_codes", copy.deepcopy(DEFAULT_CONFIG["nina_codes"]))
    data.setdefault("prayer", copy.deepcopy(DEFAULT_CONFIG["prayer"]))
    data.setdefault("system", copy.deepcopy(DEFAULT_CONFIG["system"]))
    data.setdefault("fetch_interval_minutes", DEFAULT_CONFIG["fetch_interval_minutes"])
    data.setdefault("system_interval_minutes", DEFAULT_CONFIG.get("system_interval_minutes", 3))
    data["fetch_interval_minutes"] = clamp_int(data.get("fetch_interval_minutes", DEFAULT_CONFIG.get("fetch_interval_minutes", 10)), DEFAULT_CONFIG.get("fetch_interval_minutes", 10), 1, 1440)
    data["system_interval_minutes"] = clamp_int(data.get("system_interval_minutes", DEFAULT_CONFIG.get("system_interval_minutes", 3)), DEFAULT_CONFIG.get("system_interval_minutes", 3), 1, 1440)
    data.setdefault("local_server_port", DEFAULT_CONFIG.get("local_server_port", 8765))
    data.setdefault("boot_refresh_enabled", DEFAULT_CONFIG.get("boot_refresh_enabled", True))
    data.setdefault("boot_refresh_delay_seconds", DEFAULT_CONFIG.get("boot_refresh_delay_seconds", 120))

    ui = data.setdefault("ui", {})
    if not isinstance(ui, dict):
        ui = copy.deepcopy(DEFAULT_CONFIG["ui"])
        data["ui"] = ui
    for key, value in DEFAULT_CONFIG["ui"].items():
        ui.setdefault(key, value)

    blocks = data.setdefault("blocks", {})
    if not isinstance(blocks, dict):
        blocks = copy.deepcopy(DEFAULT_CONFIG["blocks"])
        data["blocks"] = blocks
    for key, value in DEFAULT_CONFIG["blocks"].items():
        blocks.setdefault(key, value)

    markets = data.get("markets")
    if not isinstance(markets, dict):
        markets = copy.deepcopy(DEFAULT_CONFIG["markets"])
        data["markets"] = markets
    markets.setdefault("currencies", copy.deepcopy(DEFAULT_CONFIG["markets"]["currencies"]))
    markets.setdefault("indices", copy.deepcopy(DEFAULT_CONFIG["markets"]["indices"]))
    markets.setdefault("twelve_data_api_key", DEFAULT_CONFIG["markets"].get("twelve_data_api_key", ""))
    markets.setdefault("finnhub_api_key", DEFAULT_CONFIG["markets"].get("finnhub_api_key", ""))
    markets.setdefault("provider_mode", DEFAULT_CONFIG["markets"].get("provider_mode", "auto"))
    markets.setdefault("show_currencies", DEFAULT_CONFIG["markets"].get("show_currencies", True))
    markets.setdefault("show_indices", DEFAULT_CONFIG["markets"].get("show_indices", True))
    markets.setdefault("show_stocks", DEFAULT_CONFIG["markets"].get("show_stocks", True))
    markets.setdefault("stocks", copy.deepcopy(DEFAULT_CONFIG["markets"].get("stocks", [])))

    collapsed = data.setdefault("collapsed_blocks", copy.deepcopy(DEFAULT_CONFIG.get("collapsed_blocks", {})))
    if not isinstance(collapsed, dict):
        collapsed = {}
    valid_collapsed = ["weather", "prayer", "nina", "system", "markets", "news"]
    data["collapsed_blocks"] = {key: bool(collapsed.get(key, False)) for key in valid_collapsed}

    system = data.setdefault("system", {})
    if not isinstance(system, dict):
        system = copy.deepcopy(DEFAULT_CONFIG["system"])
        data["system"] = system
    for key, value in DEFAULT_CONFIG["system"].items():
        system.setdefault(key, value)

    return data

def clean(text: str | None, limit: int = 220) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]

def local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()

def first_child_text(item: ET.Element, wanted: str, limit: int = 220) -> str:
    wanted = wanted.lower()
    for child in list(item):
        if local_name(str(child.tag)) == wanted and child.text:
            return clean(child.text, limit=limit)
    return ""

def item_title(item: ET.Element) -> str:
    return first_child_text(item, "title")

def item_link(item: ET.Element) -> str:
    link = first_child_text(item, "link")
    if link:
        return link

    for child in list(item):
        if local_name(str(child.tag)) == "link":
            href = child.attrib.get("href", "")
            if href:
                return href.strip()

    return ""

def all_items(root: ET.Element):
    for elem in root.iter():
        tag = local_name(str(elem.tag))
        if tag in ("item", "entry"):
            yield elem

class NotModified(Exception):
    """Raised when a conditional GET was answered with HTTP 304.

    This is a success, not a failure: the feed simply has not changed since
    the ETag / Last-Modified we sent. Callers keep the previously cached
    items and reset the failure counter.
    """

    def __init__(self, meta: dict | None = None):
        super().__init__("not modified")
        self.meta = meta or {}


class OversizeResponse(Exception):
    """Raised when a response exceeds the byte cap.

    Truncating and parsing anyway produced silently broken feeds before, so
    an explicit failure is the honest outcome.
    """


def _decompress_limited(raw: bytes, wbits: int, limit: int) -> bytes:
    """Inflate with a hard output cap.

    gzip.decompress() and zlib.decompress() expand without bound, so the byte
    cap on the download only limited the *compressed* size. A small, highly
    compressible document could still inflate to hundreds of megabytes. This
    feeds the stream through in chunks and stops the moment the output would
    exceed the cap.
    """
    obj = zlib.decompressobj(wbits)
    out = bytearray()
    view = memoryview(raw)
    step = 65536
    for start in range(0, len(view), step):
        out += obj.decompress(bytes(view[start:start + step]), limit - len(out) + 1)
        if len(out) > limit:
            raise OversizeResponse(f"decompressed body larger than {limit} bytes")
        if obj.eof:
            break
    tail = obj.flush()
    if len(out) + len(tail) > limit:
        raise OversizeResponse(f"decompressed body larger than {limit} bytes")
    return bytes(out + tail)


def _decode_body(raw: bytes, response, max_bytes: int = 1_500_000) -> str:
    encoding = (response.headers.get("Content-Encoding") or "").strip().lower()
    # Allow a generous expansion factor for XML, which compresses very well,
    # while still bounding the result.
    limit = max(max_bytes, 4 * 1024 * 1024)
    if encoding in ("gzip", "x-gzip"):
        try:
            raw = _decompress_limited(raw, 16 + zlib.MAX_WBITS, limit)
        except OversizeResponse:
            raise
        except Exception as exc:
            raise ValueError(f"broken gzip response: {exc}") from exc
    elif encoding == "deflate":
        try:
            raw = _decompress_limited(raw, zlib.MAX_WBITS, limit)
        except OversizeResponse:
            raise
        except Exception:
            try:
                raw = _decompress_limited(raw, -zlib.MAX_WBITS, limit)
            except OversizeResponse:
                raise
            except Exception as exc:
                raise ValueError(f"broken deflate response: {exc}") from exc

    charset = response.headers.get_content_charset()
    if not charset:
        # Sniff the XML declaration before falling back to UTF-8. A few
        # regional feeds still ship ISO-8859-1 without a charset header.
        match = re.search(rb'encoding=["\']([A-Za-z0-9_.-]+)["\']', raw[:200])
        charset = match.group(1).decode("ascii", "replace") if match else "utf-8"
    try:
        return raw.decode(charset, "replace")
    except LookupError:
        return raw.decode("utf-8", "replace")


# ---------------------------------------------------------------------------
# Human-readable network diagnostics
# ---------------------------------------------------------------------------
# Before v2.1.0 a failed feed produced a bare exception class name such as
# "Tagesschau: HTTPError". That told the user nothing: an HTTPError can be a
# 403 from a publisher that blocks VPN exit nodes, a 429 rate limit, a 451
# geo-block or a 503 from an overloaded origin, and each of those calls for a
# completely different reaction. classify_error() maps the exception onto a
# small set of causes with a plain-language explanation in both UI languages.

class EmptyFeed(RuntimeError):
    """The feed parsed correctly but contained no usable entries."""


ERROR_TEXTS = {
    "blocked": (
        "Zugriff vom Anbieter blockiert",
        "blocked by the publisher",
    ),
    "geo_blocked": (
        "aus dieser Region gesperrt",
        "blocked in this region",
    ),
    "rate_limited": (
        "zu viele Abrufe, kurzzeitig gesperrt",
        "rate limited, temporarily refused",
    ),
    "not_found": (
        "Feed-Adresse existiert nicht mehr",
        "feed address no longer exists",
    ),
    "server_error": (
        "Server des Anbieters hat einen Fehler gemeldet",
        "the publisher's server reported an error",
    ),
    "dns": (
        "Adresse ließ sich nicht auflösen (DNS)",
        "hostname could not be resolved (DNS)",
    ),
    "offline": (
        "keine Netzwerkverbindung",
        "no network connection",
    ),
    "timeout": (
        "Zeitüberschreitung",
        "timed out",
    ),
    "tls": (
        "TLS-/Zertifikatsproblem",
        "TLS/certificate problem",
    ),
    "refused": (
        "Verbindung abgewiesen",
        "connection refused",
    ),
    "too_large": (
        "Antwort zu groß",
        "response too large",
    ),
    "parse": (
        "Antwort war kein gültiger Feed",
        "response was not a valid feed",
    ),
    "empty": (
        "Feed enthielt keine Meldungen",
        "feed contained no entries",
    ),
    "unknown": (
        "unbekannter Fehler",
        "unknown error",
    ),
}

# Causes that usually mean "the network path is wrong", not "this one site is
# broken". When several feeds fail this way at once and a VPN is up, the VPN
# is the far more likely culprit than eight publishers failing simultaneously.
CONNECTIVITY_KINDS = {"dns", "offline", "timeout", "tls", "refused"}
# Causes that specifically smell of a datacenter/VPN exit IP being filtered.
FILTERED_KINDS = {"blocked", "geo_blocked", "rate_limited"}


def classify_error(exc: BaseException) -> dict:
    """Turn an exception into {kind, http, de, en, detail}."""
    kind = "unknown"
    http_status = 0
    detail = ""

    if isinstance(exc, OversizeResponse):
        kind = "too_large"
    elif isinstance(exc, urllib.error.HTTPError):
        http_status = int(getattr(exc, "code", 0) or 0)
        if http_status in (401, 402, 403):
            kind = "blocked"
        elif http_status == 404 or http_status == 410:
            kind = "not_found"
        elif http_status == 429:
            kind = "rate_limited"
        elif http_status == 451:
            kind = "geo_blocked"
        elif 500 <= http_status < 600:
            kind = "server_error"
        elif 400 <= http_status < 500:
            kind = "blocked"
        else:
            kind = "server_error"
    elif isinstance(exc, urllib.error.URLError):
        reason = getattr(exc, "reason", None)
        text = str(reason or exc).lower()
        # Check the wrapped exception's TYPE before its message. Matching only
        # on words like "certificate" misclassified any SSL error whose text
        # happened not to contain them, which is easy to hit with a custom
        # verification failure or a localised OpenSSL build.
        if isinstance(reason, ssl.SSLError):
            kind = "tls"
        elif isinstance(reason, socket.gaierror) or "name or service not known" in text \
                or "temporary failure in name resolution" in text or "nodename nor servname" in text:
            kind = "dns"
        elif "certificate" in text or "ssl" in text or "tls" in text:
            kind = "tls"
        elif "timed out" in text or "timeout" in text:
            kind = "timeout"
        elif "network is unreachable" in text or "no route to host" in text or "unreachable" in text:
            kind = "offline"
        elif "connection refused" in text or "refused" in text:
            kind = "refused"
        else:
            kind = "offline"
        detail = str(reason or "")[:120]
    elif isinstance(exc, ssl.SSLError):
        kind = "tls"
    elif isinstance(exc, socket.gaierror):
        kind = "dns"
    elif isinstance(exc, (socket.timeout, TimeoutError)):
        kind = "timeout"
    elif isinstance(exc, ConnectionRefusedError):
        kind = "refused"
    elif isinstance(exc, (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, ConnectionError)):
        kind = "offline"
    elif isinstance(exc, ET.ParseError):
        kind = "parse"
    elif isinstance(exc, EmptyFeed):
        kind = "empty"
    elif isinstance(exc, OSError):
        # Anything else the socket layer raises (EHOSTUNREACH, ENETDOWN, ...).
        # Without this these fell through to "unknown", which is exactly the
        # uninformative label this whole classifier exists to remove.
        text = str(exc).lower()
        if "unreachable" in text or "no route" in text:
            kind = "offline"
        elif "timed out" in text or "timeout" in text:
            kind = "timeout"
        else:
            kind = "offline"
        detail = str(exc)[:120]
    elif isinstance(exc, (ValueError, RuntimeError)):
        text = str(exc).lower()
        if "no items" in text or "empty" in text:
            kind = "empty"
        else:
            kind = "parse"
        detail = str(exc)[:120]

    de, en = ERROR_TEXTS.get(kind, ERROR_TEXTS["unknown"])
    return {
        "kind": kind,
        "http": http_status,
        "de": de,
        "en": en,
        "detail": detail,
    }


def error_message(info: dict, language: str = "de") -> str:
    """Short one-line message shown next to a feed name."""
    text = info.get("en" if language == "en" else "de", "")
    status = int(info.get("http") or 0)
    if status:
        return f"{text} (HTTP {status})"
    return text



def urlopen_full(
    url: str,
    timeout: int = 15,
    max_bytes: int = 1_500_000,
    retries: int = 1,
    headers: dict[str, str] | None = None,
    etag: str = "",
    last_modified: str = "",
) -> tuple[str, dict]:
    """Fetch a URL and return (text, meta).

    meta carries the validators needed for the next conditional request plus
    the observed HTTP status and round-trip time, which the News block shows
    in its per-feed diagnostics.
    """
    # Refuse anything that isn't plain HTTP(S). urllib happily handles file://
    # and ftp:// otherwise, which would let a malicious config exfiltrate
    # local files via the feed parser. The check is cheap and only runs once
    # per request.
    parsed = urllib.parse.urlsplit(url or "")
    if parsed.scheme not in ALLOWED_URL_SCHEMES:
        raise ValueError(f"refusing non-http(s) URL scheme: {parsed.scheme or 'empty'}")
    if not parsed.netloc:
        raise ValueError("refusing URL without host")

    request_headers = {
        "User-Agent": UA,
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, application/json, */*",
        # Feeds are highly compressible XML; asking for gzip typically cuts
        # transfer size by 70-80 %. urllib does not negotiate this on its own
        # and does not decompress, so _decode_body() handles the response.
        "Accept-Encoding": "gzip, deflate",
    }
    if etag:
        request_headers["If-None-Match"] = str(etag)
    if last_modified:
        request_headers["If-Modified-Since"] = str(last_modified)
    if headers:
        request_headers.update({str(k): str(v) for k, v in headers.items() if v is not None})

    req = urllib.request.Request(url, headers=request_headers)

    last_exc = None
    for attempt in range(retries + 1):
        started = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                # Read one byte past the cap so an oversized body fails loudly
                # instead of being silently truncated into invalid XML.
                raw = response.read(max_bytes + 1)
                if len(raw) > max_bytes:
                    raise OversizeResponse(f"response larger than {max_bytes} bytes")
                meta = {
                    "status": int(getattr(response, "status", 200) or 200),
                    "etag": (response.headers.get("ETag") or "").strip(),
                    "last_modified": (response.headers.get("Last-Modified") or "").strip(),
                    "elapsed_ms": int((time.monotonic() - started) * 1000),
                }
                return _decode_body(raw, response, max_bytes), meta
        except urllib.error.HTTPError as exc:
            if exc.code == 304:
                raise NotModified({
                    "status": 304,
                    "etag": etag,
                    "last_modified": last_modified,
                    "elapsed_ms": int((time.monotonic() - started) * 1000),
                }) from None
            last_exc = exc
            # 4xx answers are deterministic: retrying the same request against
            # the same endpoint cannot turn a 403 into a 200.
            if 400 <= exc.code < 500:
                raise
        except OversizeResponse:
            raise
        except Exception as exc:
            last_exc = exc

        if attempt < retries:
            time.sleep(2)

    if last_exc:
        raise last_exc
    raise RuntimeError("request failed")


def urlopen_text(url: str, timeout: int = 15, max_bytes: int = 1_500_000, retries: int = 1, headers: dict[str, str] | None = None) -> str:
    text, _meta = urlopen_full(url, timeout=timeout, max_bytes=max_bytes, retries=retries, headers=headers)
    return text

# ---------------------------------------------------------------------------
# Feed state: conditional GET validators and per-feed failure history
# ---------------------------------------------------------------------------
# Kept in its own small file next to the cache. It holds only bookkeeping
# (ETag, Last-Modified, last success, consecutive failures), never article
# content, so deleting it costs at most one extra full feed download.

FEED_STATE_FILE = OUT_DIR / "feedstate.json"

# Back off on a per-feed basis after repeated failures so a publisher that
# blocks the current exit IP is not hammered every ten minutes. The list is
# indexed by consecutive failure count and gives the minimum wait in minutes.
FEED_BACKOFF_MINUTES = [0, 0, 5, 15, 30, 60, 120]
FEED_BACKOFF_MAX_MINUTES = 240


def load_feed_state() -> dict:
    try:
        data = json.loads(FEED_STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except Exception:
        pass
    return {}


def save_feed_state(state: dict) -> None:
    try:
        atomic_write_json(FEED_STATE_FILE, state)
    except Exception:
        # Losing the validator cache only costs bandwidth, never correctness.
        pass


def feed_state_key(name: str, url: str) -> str:
    return f"{str(name or '').strip()}|{str(url or '').strip()}"


def feed_backoff_seconds(failures: int) -> int:
    if failures <= 1:
        return 0
    if failures < len(FEED_BACKOFF_MINUTES):
        return FEED_BACKOFF_MINUTES[failures] * 60
    return FEED_BACKOFF_MAX_MINUTES * 60


def parse_feed_datetime(value: str) -> int | None:
    """Parse RFC 822 (RSS) or ISO 8601 (Atom) timestamps into a UTC epoch."""
    text = str(value or "").strip()
    if not text:
        return None

    try:
        parsed = email.utils.parsedate_to_datetime(text)
        if parsed is not None:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return int(parsed.timestamp())
    except Exception:
        pass

    iso = text.replace("Z", "+00:00")
    # Trim fractional seconds longer than six digits, which fromisoformat rejects.
    iso = re.sub(r"(\.\d{6})\d+", r"\1", iso)
    try:
        parsed = datetime.fromisoformat(iso)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp())
    except Exception:
        return None


def item_published(item: ET.Element) -> int | None:
    for tag in ("pubdate", "published", "updated", "date", "created"):
        value = first_child_text(item, tag, limit=80)
        if value:
            epoch = parse_feed_datetime(value)
            if epoch is not None:
                return epoch
    return None


def item_identity(item: ET.Element, link: str, title: str) -> str:
    guid = first_child_text(item, "guid", limit=200) or first_child_text(item, "id", limit=200)
    return guid or link or title


def parse_feed_document(data: str, limit: int) -> list[dict]:
    root = safe_xml_fromstring(data)

    entries: list[dict] = []
    for item in all_items(root):
        title = item_title(item)
        if not title:
            continue

        link = item_link(item)
        entry: dict = {"title": title, "link": link}

        published = item_published(item)
        if published is not None:
            entry["published"] = published

        identity = item_identity(item, link, title)
        if identity:
            entry["id"] = identity

        entries.append(entry)

        if len(entries) >= limit:
            break

    return entries


def fetch_feed(url: str, limit: int, etag: str = "", last_modified: str = "") -> tuple[list[dict], dict]:
    """Fetch and parse one feed. Raises NotModified when nothing changed."""
    data, meta = urlopen_full(url, timeout=12, etag=etag, last_modified=last_modified)
    entries = parse_feed_document(data, limit)
    if not entries:
        raise EmptyFeed("feed contained no entries")
    return entries, meta


def fetch_all_feeds(config: dict, old: dict, language: str = "de") -> tuple[list[dict], list[str], dict]:
    """Fetch every configured feed in parallel and return (feeds, errors, status).

    Sequential fetching was the single worst latency source in the widget: with
    eleven feeds, a 15 s timeout and one retry each, a flaky connection could
    keep a refresh busy for minutes and block the systemd unit. A small thread
    pool keeps the wall-clock cost close to the slowest single feed while
    staying polite: six concurrent connections spread over different hosts.
    """
    feed_configs = config.get("feeds", [])
    if not isinstance(feed_configs, list):
        feed_configs = []

    state = load_feed_state()
    now = time.time()
    results: dict[int, dict] = {}

    def work(index: int, feed: dict) -> tuple[int, dict]:
        name = str(feed.get("name", "Feed")).strip() or "Feed"
        url = str(feed.get("url", "")).strip()
        try:
            limit = int(feed.get("limit", 5) or 5)
        except Exception:
            limit = 5
        limit = max(1, min(50, limit))

        key = feed_state_key(name, url)
        entry_state = state.get(key, {}) if isinstance(state.get(key), dict) else {}
        failures = int(entry_state.get("failures", 0) or 0)
        next_try = float(entry_state.get("next_try", 0) or 0)

        # Honour the backoff window, but never let a feed go dark forever:
        # a forced refresh always retries immediately.
        if next_try and now < next_try and not manual_refresh():
            wait_minutes = max(1, int((next_try - now) / 60))
            return index, {
                "name": name,
                "url": url,
                "items": old_items(old, name, url),
                "state": dict(entry_state),
                "skipped": True,
                "error": {
                    "kind": entry_state.get("last_kind", "unknown"),
                    "http": int(entry_state.get("last_http", 0) or 0),
                    "wait_minutes": wait_minutes,
                },
            }

        try:
            items, meta = fetch_feed(
                url,
                limit,
                etag=str(entry_state.get("etag", "") or ""),
                last_modified=str(entry_state.get("last_modified", "") or ""),
            )
            return index, {
                "name": name,
                "url": url,
                "items": items,
                "state": {
                    "etag": meta.get("etag", ""),
                    "last_modified": meta.get("last_modified", ""),
                    "last_ok": now,
                    "failures": 0,
                    "next_try": 0,
                    "elapsed_ms": meta.get("elapsed_ms", 0),
                    "last_kind": "",
                    "last_http": 0,
                },
                "error": None,
            }
        except NotModified as exc:
            meta = getattr(exc, "meta", {}) or {}
            merged = dict(entry_state)
            merged.update({
                "last_ok": now,
                "failures": 0,
                "next_try": 0,
                "elapsed_ms": meta.get("elapsed_ms", 0),
                "last_kind": "",
                "last_http": 0,
            })
            return index, {
                "name": name,
                "url": url,
                "items": old_items(old, name, url),
                "state": merged,
                "unchanged": True,
                "error": None,
            }
        except Exception as exc:
            info = classify_error(exc)
            failures += 1
            merged = dict(entry_state)
            merged.update({
                "failures": failures,
                "next_try": now + feed_backoff_seconds(failures),
                "last_kind": info.get("kind", "unknown"),
                "last_http": info.get("http", 0),
            })
            # Drop stale validators after a hard failure so the next successful
            # attempt refetches the full document rather than trusting an ETag
            # that may belong to an error page.
            if info.get("kind") in ("not_found", "parse", "blocked"):
                merged["etag"] = ""
                merged["last_modified"] = ""
            return index, {
                "name": name,
                "url": url,
                "items": old_items(old, name, url),
                "state": merged,
                "error": info,
            }

    if feed_configs:
        workers = max(1, min(6, len(feed_configs)))
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {
                pool.submit(work, index, feed): (index, feed)
                for index, feed in enumerate(feed_configs)
                if isinstance(feed, dict)
            }
            for future in concurrent.futures.as_completed(futures):
                original_index, feed = futures[future]
                try:
                    index, payload = future.result()
                    results[index] = payload
                except Exception as exc:
                    # work() already converts ordinary fetch/parser failures to
                    # structured feed errors. Reaching this branch therefore
                    # means an unexpected worker bug. Never let that make a
                    # configured feed silently disappear from the UI/status.
                    name = str(feed.get("name", "Feed")).strip() or "Feed"
                    url = str(feed.get("url", "")).strip()
                    key = feed_state_key(name, url)
                    entry_state = state.get(key, {}) if isinstance(state.get(key), dict) else {}
                    failures = int(entry_state.get("failures", 0) or 0) + 1
                    info = classify_error(exc)
                    merged = dict(entry_state)
                    merged.update({
                        "failures": failures,
                        "next_try": now + feed_backoff_seconds(failures),
                        "last_kind": info.get("kind", "unknown"),
                        "last_http": info.get("http", 0),
                    })
                    results[original_index] = {
                        "name": name,
                        "url": url,
                        "items": old_items(old, name, url),
                        "state": merged,
                        "error": info,
                    }

    feeds: list[dict] = []
    errors: list[str] = []
    failed_kinds: list[str] = []
    ok_count = 0

    for index in sorted(results):
        payload = results[index]
        name = payload["name"]
        entry_state = payload.get("state", {})
        state[feed_state_key(name, payload["url"])] = entry_state

        info = payload.get("error")
        feed_entry: dict = {
            "name": name,
            "url": payload["url"],
            "items": payload.get("items", []),
        }

        last_ok = float(entry_state.get("last_ok", 0) or 0)
        if last_ok:
            feed_entry["last_ok"] = int(last_ok)
        if entry_state.get("elapsed_ms"):
            feed_entry["elapsed_ms"] = int(entry_state.get("elapsed_ms", 0) or 0)

        if info is None:
            ok_count += 1
            feed_entry["ok"] = True
        else:
            kind = info.get("kind", "unknown")
            failed_kinds.append(kind)
            feed_entry["ok"] = False
            feed_entry["stale"] = bool(feed_entry["items"])
            if payload.get("skipped"):
                wait = int(info.get("wait_minutes", 0) or 0)
                retry_de = f"neuer Versuch in {wait} Min."
                retry_en = f"retrying in {wait} min"
                feed_entry["error"] = {
                    "kind": kind,
                    "http": int(info.get("http", 0) or 0),
                    "message": retry_de if language != "en" else retry_en,
                    "paused": True,
                }
            else:
                feed_entry["error"] = {
                    "kind": kind,
                    "http": int(info.get("http", 0) or 0),
                    "message": error_message(info, language),
                    "paused": False,
                }
            errors.append(f"{name}: {feed_entry['error']['message']}")

        feeds.append(feed_entry)

    # Forget state for feeds that are no longer configured, so removing a feed
    # does not leave its ETag and failure counter behind for ever.
    live_keys = {feed_state_key(f.get("name", ""), f.get("url", "")) for f in feed_configs if isinstance(f, dict)}
    state = {k: v for k, v in state.items() if k in live_keys}
    save_feed_state(state)

    return feeds, errors, build_news_status(ok_count, failed_kinds, language)


def build_news_status(ok_count: int, failed_kinds: list[str], language: str = "de") -> dict:
    """Summarise the overall news fetch into one calm, actionable sentence.

    Eleven separate red error strings tell the user nothing they can act on.
    One sentence naming the likely cause does.
    """
    fail_count = len(failed_kinds)
    total = ok_count + fail_count
    status = {
        "ok_count": ok_count,
        "fail_count": fail_count,
        "total": total,
        "severity": "ok",
        "summary": "",
        "hint": "",
        "vpn": False,
    }

    if fail_count == 0 or total == 0:
        return status

    english = language == "en"
    connectivity = sum(1 for kind in failed_kinds if kind in CONNECTIVITY_KINDS)
    filtered = sum(1 for kind in failed_kinds if kind in FILTERED_KINDS)
    vpn_names = detected_vpn_names()
    status["vpn"] = bool(vpn_names)
    vpn_label = ", ".join(vpn_names[:2])

    partial = fail_count < total
    status["severity"] = "warning" if partial else "error"

    if english:
        status["summary"] = (
            f"{fail_count} of {total} sources unavailable"
            if partial else
            f"No source could be reached ({total})"
        )
    else:
        status["summary"] = (
            f"{fail_count} von {total} Quellen nicht erreichbar"
            if partial else
            f"Keine Quelle erreichbar ({total})"
        )

    # The interesting part: name the most plausible cause instead of dumping
    # exception class names on the user.
    # A real majority is strictly more than half. The old test used
    # `>= max(2, fail_count // 2)`, so two filtered sources out of five counted
    # as a majority and produced a confident VPN explanation on thin evidence.
    def majority(count: int) -> bool:
        return count * 2 > fail_count and count >= 2

    majority_connectivity = majority(connectivity)
    majority_filtered = majority(filtered)

    if vpn_names and majority_filtered:
        # Say what was observed first, and offer the VPN only as a possibility.
        # A running tunnel daemon does not prove that web traffic leaves through
        # it: Tailscale without an exit node, or a split-tunnel setup, routes
        # normal browsing straight out of the local uplink.
        status["hint"] = (
            f"Several publishers are refusing this connection. If {vpn_label} routes your web traffic, its exit address is the likely reason."
            if english else
            f"Mehrere Anbieter lehnen diese Verbindung ab. Falls {vpn_label} den Web-Verkehr leitet, ist dessen Exit-Adresse die wahrscheinliche Ursache."
        )
    elif vpn_names and majority_connectivity:
        status["hint"] = (
            f"Names or routes are not resolving. If {vpn_label} carries this traffic, check it and its DNS setting."
            if english else
            f"Namen oder Routen lösen nicht auf. Falls {vpn_label} diesen Verkehr führt, dieses und dessen DNS-Einstellung prüfen."
        )
    elif majority_connectivity and not vpn_names:
        status["hint"] = (
            "The network looks unreachable. Cached headlines are shown."
            if english else
            "Das Netzwerk scheint nicht erreichbar. Es werden zwischengespeicherte Meldungen angezeigt."
        )
    elif majority_filtered:
        status["hint"] = (
            "The publishers are refusing this connection. Cached headlines are shown."
            if english else
            "Die Anbieter lehnen diese Verbindung ab. Es werden zwischengespeicherte Meldungen angezeigt."
        )
    else:
        status["hint"] = (
            "Cached headlines are shown for the affected sources."
            if english else
            "Für die betroffenen Quellen werden zwischengespeicherte Meldungen angezeigt."
        )

    return status


def _epoch_clock(epoch_value, utc_offset_seconds: int = 0) -> str:
    try:
        stamp = int(epoch_value) + int(utc_offset_seconds or 0)
        return datetime.fromtimestamp(stamp, timezone.utc).strftime("%H:%M")
    except (TypeError, ValueError, OSError, OverflowError):
        return "--"


def fetch_openweather_one(name: str, lat: float, lon: float, api_key: str, language: str = "de") -> dict[str, object]:
    """Fetch OpenWeather current conditions plus today's forecast totals.

    The free OpenWeather tier exposes current conditions and the 5-day/3-hour
    forecast. Current conditions are the required request. The forecast call is
    deliberately best-effort: if it fails, the widget still shows the current
    reading instead of discarding an otherwise valid location.
    """
    common = {
        "lat": str(lat),
        "lon": str(lon),
        "appid": api_key,
        "units": "metric",
        "lang": "en" if language == "en" else "de",
    }
    current_url = "https://api.openweathermap.org/data/2.5/weather?" + urllib.parse.urlencode(common)
    current = json.loads(urlopen_text(current_url, timeout=12))

    forecast = {}
    try:
        forecast_url = "https://api.openweathermap.org/data/2.5/forecast?" + urllib.parse.urlencode(common)
        forecast = json.loads(urlopen_text(forecast_url, timeout=12))
    except Exception:
        # Current weather is still useful if the forecast endpoint alone fails.
        forecast = {}

    main = current.get("main") or {}
    wind_data = current.get("wind") or {}
    sys_data = current.get("sys") or {}
    weather_list = current.get("weather") or []
    weather0 = weather_list[0] if weather_list and isinstance(weather_list[0], dict) else {}

    condition = str(weather0.get("description") or ("Weather" if language == "en" else "Wetter")).strip()
    if condition:
        condition = condition[:1].upper() + condition[1:]
    temp = main.get("temp")
    humidity = main.get("humidity")
    apparent = main.get("feels_like")

    # OpenWeather's metric wind values are metres/second; the existing widget
    # schema and Open-Meteo path display kilometres/hour.
    def ms_to_kmh(value):
        try:
            return float(value) * 3.6
        except (TypeError, ValueError):
            return None

    wind = ms_to_kmh(wind_data.get("speed"))
    gusts = ms_to_kmh(wind_data.get("gust"))
    offset = int(current.get("timezone") or 0)
    local_time = _epoch_clock(current.get("dt"), offset)
    sunrise = _epoch_clock(sys_data.get("sunrise"), offset)
    sunset = _epoch_clock(sys_data.get("sunset"), offset)

    # Sum the 3-hour forecast buckets belonging to the location's current
    # local date. This keeps the existing "Rain/Snow today" display semantics.
    precipitation = 0.0
    snow = 0.0
    forecast_seen = False
    try:
        local_date = datetime.fromtimestamp(int(current.get("dt")) + offset, timezone.utc).date()
        forecast_offset = int((forecast.get("city") or {}).get("timezone", offset) or 0)
        for row in forecast.get("list") or []:
            if not isinstance(row, dict):
                continue
            row_date = datetime.fromtimestamp(int(row.get("dt")) + forecast_offset, timezone.utc).date()
            if row_date != local_date:
                continue
            forecast_seen = True
            precipitation += float((row.get("rain") or {}).get("3h") or 0.0)
            snow += float((row.get("snow") or {}).get("3h") or 0.0)
    except (TypeError, ValueError, OSError, OverflowError):
        forecast_seen = False

    def num(value, suffix=""):
        try: return f"{float(value):.1f}{suffix}"
        except Exception: return f"--{suffix}"
    def opt(value, suffix="", nonzero=False):
        try:
            if value is None: return ""
            v=float(value)
            if nonzero and abs(v) < 0.05: return ""
            return f"{v:.1f}{suffix}"
        except Exception: return ""
    def pct(value):
        try: return "" if value is None else f"{float(value):.0f}%"
        except Exception: return ""

    temp_text=num(temp, " °C")
    apparent_text=opt(apparent, " °C")
    humidity_text=pct(humidity)
    wind_text=opt(wind, " km/h", True)
    gusts_text=opt(gusts, " km/h", True)
    precipitation_text=opt(precipitation if forecast_seen else None, " mm", True)
    snow_text=opt(snow if forecast_seen else None, " mm", True)
    sun_text=f"{sunrise}–{sunset}"
    parts=[]
    if language == "en":
        if apparent_text: parts.append(f"Feels like {apparent_text}")
        if humidity_text: parts.append(f"Humidity {humidity_text}")
        parts.append(f"Sun {sun_text}")
        if wind_text: parts.append(f"Wind {wind_text}")
        if gusts_text: parts.append(f"Gusts {gusts_text}")
        if precipitation_text: parts.append(f"Rain forecast {precipitation_text}")
        if snow_text: parts.append(f"Snow forecast {snow_text}")
    else:
        if apparent_text: parts.append(f"Gefühlt {apparent_text}")
        if humidity_text: parts.append(f"Luftfeuchte {humidity_text}")
        parts.append(f"Sonne {sun_text}")
        if wind_text: parts.append(f"Wind {wind_text}")
        if gusts_text: parts.append(f"Böen {gusts_text}")
        if precipitation_text: parts.append(f"Regenprognose {precipitation_text}")
        if snow_text: parts.append(f"Schneeprognose {snow_text}")

    return {
        "name": name, "latitude": lat, "longitude": lon, "provider": "openweather",
        "condition": condition, "temperature": temp, "humidity": humidity,
        "apparent_temperature": apparent, "wind_speed": wind, "wind_gusts": gusts,
        "local_time": local_time, "utc_offset_seconds": offset,
        "timezone": "", "timezone_abbreviation": "",
        "summary": f"{condition}, {temp_text}", "details": " · ".join(parts),
        "last_ok": int(time.time()),
    }

def fetch_weather_one(name: str, lat: float, lon: float, language: str = "de", weather_config: dict | None = None) -> dict[str, object]:
    weather_config = weather_config if isinstance(weather_config, dict) else {}
    openweather_key = str(weather_config.get("openweather_api_key") or "").strip()
    if openweather_key:
        return fetch_openweather_one(name, lat, lon, openweather_key, language)

    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m,wind_gusts_10m"
        "&daily=precipitation_sum,snowfall_sum,sunrise,sunset"
        "&timezone=auto"
    )

    data = json.loads(urlopen_text(url, timeout=12))
    current = data.get("current", {})
    daily = data.get("daily", {})

    code = current.get("weather_code")
    condition_map = WEATHER_CODES_EN if language == "en" else WEATHER_CODES
    condition = condition_map.get(code, "Weather" if language == "en" else "Wetter")
    temp = current.get("temperature_2m")
    humidity = current.get("relative_humidity_2m")
    apparent = current.get("apparent_temperature")
    wind = current.get("wind_speed_10m")
    gusts = current.get("wind_gusts_10m")

    precipitation = (daily.get("precipitation_sum") or [None])[0]
    snow = (daily.get("snowfall_sum") or [None])[0]
    sunrise = (daily.get("sunrise") or ["--"])[0]
    sunset = (daily.get("sunset") or ["--"])[0]
    local_time = current.get("time", "")
    utc_offset_seconds = data.get("utc_offset_seconds")
    timezone_name = data.get("timezone", "")
    timezone_abbreviation = data.get("timezone_abbreviation", "")

    def fmt_time(value: str) -> str:
        return value[-5:] if value and value != "--" else "--"

    def fmt_number(value, suffix: str = "") -> str:
        try:
            return f"{float(value):.1f}{suffix}"
        except Exception:
            return f"--{suffix}"

    def fmt_optional_number(value, suffix: str = "") -> str:
        try:
            if value is None:
                return ""
            return f"{float(value):.1f}{suffix}"
        except Exception:
            return ""

    def fmt_optional_nonzero_number(value, suffix: str = "") -> str:
        try:
            if value is None:
                return ""
            num = float(value)
            # Values that round to 0.0 are visually just noise in the dashboard.
            if abs(num) < 0.05:
                return ""
            return f"{num:.1f}{suffix}"
        except Exception:
            return ""

    def fmt_optional_percent(value) -> str:
        try:
            if value is None:
                return ""
            return f"{float(value):.0f}%"
        except Exception:
            return ""

    temp_text = fmt_number(temp, " °C")
    wind_text = fmt_optional_nonzero_number(wind, " km/h")
    gusts_text = fmt_optional_nonzero_number(gusts, " km/h")
    humidity_text = fmt_optional_percent(humidity)
    apparent_text = fmt_optional_number(apparent, " °C")
    precipitation_text = fmt_optional_nonzero_number(precipitation, " mm")
    snow_text = fmt_optional_nonzero_number(snow, " cm")
    sun_text = f"{fmt_time(sunrise)}–{fmt_time(sunset)}"

    if language == "en":
        detail_parts = []
        if apparent_text:
            detail_parts.append(f"Feels like {apparent_text}")
        if humidity_text:
            detail_parts.append(f"Humidity {humidity_text}")
        detail_parts.append(f"Sun {sun_text}")
        if wind_text:
            detail_parts.append(f"Wind {wind_text}")
        if gusts_text:
            detail_parts.append(f"Gusts {gusts_text}")
        if precipitation_text:
            detail_parts.append(f"Rain {precipitation_text}")
        if snow_text:
            detail_parts.append(f"Snow {snow_text}")
    else:
        detail_parts = []
        if apparent_text:
            detail_parts.append(f"Gefühlt {apparent_text}")
        if humidity_text:
            detail_parts.append(f"Luftfeuchte {humidity_text}")
        detail_parts.append(f"Sonne {sun_text}")
        if wind_text:
            detail_parts.append(f"Wind {wind_text}")
        if gusts_text:
            detail_parts.append(f"Böen {gusts_text}")
        if precipitation_text:
            detail_parts.append(f"Regen {precipitation_text}")
        if snow_text:
            detail_parts.append(f"Schnee {snow_text}")

    return {
        "name": name,
        # Coordinates are part of the cache identity.  A display name alone is
        # not stable: a user can repoint "Berlin" to another place, or keep two
        # locations with the same label.
        "latitude": lat,
        "longitude": lon,
        "provider": "open-meteo",
        "condition": condition,
        "temperature": temp,
        "humidity": humidity,
        "apparent_temperature": apparent,
        "wind_speed": wind,
        "wind_gusts": gusts,
        "local_time": fmt_time(local_time),
        "utc_offset_seconds": utc_offset_seconds,
        "timezone": timezone_name,
        "timezone_abbreviation": timezone_abbreviation,
        "summary": f"{condition}, {temp_text}",
        "details": " · ".join(detail_parts),
        # Confirmed-at timestamp, so a cached reading can show its real age
        # instead of looking indistinguishable from a fresh one.
        "last_ok": int(time.time()),
    }

def fetch_weather(old: dict, config: dict) -> dict:
    old_weather = old.get("weather", {})
    items = []
    errors = []

    language = ui_language(config)
    weather_config = config.get("weather") if isinstance(config.get("weather"), dict) else {}
    provider_id = "openweather" if str(weather_config.get("openweather_api_key") or "").strip() else "open-meteo"

    weather_entries = config.get("weather_locations", [])
    if not weather_entries:
        return {
            "updated": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            "items": [],
            "errors": [],
            "provider": provider_id,
        }

    def previous_item(name: str, lat: float, lon: float) -> dict | None:
        """Return a cached reading only for the exact configured location.

        Caches written before v2.1.2 did not store coordinates.  Reusing those
        by name after a configuration change can put weather from the old city
        under the new one, so legacy name-only entries are intentionally not
        reused on a failed fetch.
        """
        for candidate in old_weather.get("items", []) or []:
            if not isinstance(candidate, dict) or candidate.get("name") != name:
                continue
            try:
                old_lat = float(candidate["latitude"])
                old_lon = float(candidate["longitude"])
            except (KeyError, TypeError, ValueError):
                continue
            candidate_provider = str(candidate.get("provider") or "open-meteo")
            if candidate_provider != provider_id:
                continue
            if abs(old_lat - lat) <= 1e-6 and abs(old_lon - lon) <= 1e-6:
                return candidate
        return None

    def weather_failure_payload(entry: dict, exc: Exception) -> dict:
        name = str(entry.get("name", "Ort"))
        info = classify_error(exc)
        # A location that fails should keep showing its last known reading
        # rather than silently vanishing from the list. The same fallback is
        # used for an unexpected worker exception below, so a programming bug
        # cannot erase one configured location from the result either.
        previous = None
        try:
            previous = previous_item(name, float(entry["lat"]), float(entry["lon"]))
        except (KeyError, TypeError, ValueError):
            pass
        if previous:
            stale = dict(previous)
            stale["stale"] = True
            stale["error"] = error_message(info, language)
            return stale
        return {"name": name, "failed": True, "error": error_message(info, language)}

    # Fetch every location in parallel. Six locations at 12 s each used to cost
    # up to 72 s sequentially; now the block costs roughly one request.
    def work(index: int, entry: dict) -> tuple[int, dict]:
        name = str(entry.get("name", "Ort"))
        try:
            lat = float(entry["lat"])
            lon = float(entry["lon"])
            return index, fetch_weather_one(name, lat, lon, language, weather_config)
        except Exception as exc:
            return index, weather_failure_payload(entry, exc)

    valid = [entry for entry in weather_entries if isinstance(entry, dict)]
    results: dict[int, dict] = {}
    if valid:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(6, len(valid)))) as pool:
            futures = {pool.submit(work, index, entry): (index, entry) for index, entry in enumerate(valid)}
            for future in concurrent.futures.as_completed(futures):
                original_index, entry = futures[future]
                try:
                    index, payload = future.result()
                    results[index] = payload
                except Exception as exc:
                    results[original_index] = weather_failure_payload(entry, exc)

    for index in sorted(results):
        payload = results[index]
        if payload.get("failed"):
            # No current reading and nothing cached for this place.
            errors.append(f"{payload.get('name', 'Ort')}: {payload['error']}")
            continue
        if payload.get("stale"):
            errors.append(f"{payload.get('name', 'Ort')}: {payload.get('error', '')}")
        items.append(payload)

    return {
        "updated": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        "items": items,
        "errors": errors,
        "provider": provider_id,
    }


def warning_filter_terms(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, (list, tuple)):
        raw = ",".join(str(x) for x in value)
    else:
        raw = str(value)
    return [x.strip().lower() for x in re.split(r"[,;]", raw) if x.strip()]

def warning_matches_filters(item: dict, include=None, exclude=None) -> bool:
    includes = warning_filter_terms(include)
    excludes = warning_filter_terms(exclude)
    if not includes and not excludes:
        return True
    haystack = " ".join(str(item.get(k, "")) for k in ("title", "details", "severity", "link", "_filter_text")).lower()
    if includes and not any(term in haystack for term in includes):
        return False
    if excludes and any(term in haystack for term in excludes):
        return False
    return True

def apply_warning_filters(items: list[dict[str, str]], include=None, exclude=None) -> list[dict[str, str]]:
    filtered = [item for item in items if warning_matches_filters(item, include, exclude)]
    # Do not leak helper fields into rss.json.
    for item in filtered:
        item.pop("_filter_text", None)
    return filtered

def fetch_nina_code(label: str, code: str, language: str = "de") -> list[dict[str, str]]:
    url = f"https://warnung.bund.de/api31/dashboard/{code}.json"
    raw = urlopen_text(url, timeout=12)
    data = json.loads(raw)

    if not isinstance(data, list):
        return []

    items = []

    for warning in data[:8]:
        payload = warning.get("payload", {}) if isinstance(warning, dict) else {}
        pdata = payload.get("data", {}) if isinstance(payload, dict) else {}
        i18n = warning.get("i18nTitle", {}) if isinstance(warning, dict) else {}

        title = ""
        if isinstance(i18n, dict):
            if language == "en":
                title = i18n.get("en") or i18n.get("de") or ""
            else:
                title = i18n.get("de") or i18n.get("en") or ""

        title = title or pdata.get("headline") or warning.get("id", "Warning" if language == "en" else "Warnung")

        provider = pdata.get("provider", "NINA")
        severity = pdata.get("severity", "")
        msg_type = pdata.get("msgType", "")
        expires = warning.get("expires", "")

        parts = [x for x in (label, provider, severity, msg_type) if x]
        if expires:
            parts.append(("until " if language == "en" else "bis ") + expires[:16].replace("T", " "))

        items.append({
            "title": clean(title, 220),
            "details": " · ".join(parts),
            "severity": clean(str(severity), 40),
            "link": "https://warnung.bund.de/meldungen",
        })

    return items

def feed_summary(item: ET.Element) -> str:
    return first_child_text(item, "summary") or first_child_text(item, "description") or first_child_text(item, "content")

def feed_updated(item: ET.Element) -> str:
    return first_child_text(item, "updated") or first_child_text(item, "published") or first_child_text(item, "pubDate")

def fetch_warning_feed(label: str, url: str, language: str = "de", source: str = "Feed", include=None, exclude=None) -> list[dict[str, str]]:
    data = urlopen_text(url, timeout=15)
    root_xml = safe_xml_fromstring(data)
    items = []
    for item in all_items(root_xml):
        title = item_title(item)
        if not title:
            continue
        summary = clean(feed_summary(item), 300)
        updated = clean(feed_updated(item), 40)
        details = " · ".join(x for x in (label, source, clean(summary, 140), updated) if x)
        candidate = {
            "title": clean(title, 220),
            "details": details,
            "severity": source,
            "link": item_link(item),
            "_filter_text": " ".join(x for x in (title, summary, updated, details) if x),
        }
        if warning_matches_filters(candidate, include, exclude):
            candidate.pop("_filter_text", None)
            items.append(candidate)
        if len(items) >= 8:
            break
    return items

def fetch_meteoalarm(label: str, country: str, language: str = "de", include=None, exclude=None) -> list[dict[str, str]]:
    slug = re.sub(r"[^a-z0-9-]", "", str(country or "").strip().lower())
    if not slug:
        return []
    url = f"https://feeds.meteoalarm.org/feeds/meteoalarm-legacy-atom-{slug}"
    return fetch_warning_feed(label, url, language, "MeteoAlarm", include, exclude)

def geosphere_type_name(value, language: str = "de") -> str:
    names_de = {1: "Sturm", 2: "Regen", 3: "Schnee", 4: "Blitzeis", 5: "Unwetter", 6: "Hitze", 7: "Kälte"}
    names_en = {1: "Storm", 2: "Rain", 3: "Snow", 4: "Freezing rain", 5: "Severe weather", 6: "Heat", 7: "Cold"}
    try:
        key = int(value)
    except Exception:
        key = -1
    return (names_en if language == "en" else names_de).get(key, str(value or ("Warning" if language == "en" else "Warnung")))

def geosphere_level_name(value, language: str = "de") -> str:
    names_de = {1: "Gelb", 2: "Orange", 3: "Rot"}
    names_en = {1: "Yellow", 2: "Orange", 3: "Red"}
    try:
        key = int(value)
    except Exception:
        key = -1
    return (names_en if language == "en" else names_de).get(key, str(value or ""))

def geosphere_severity(value) -> str:
    try:
        key = int(value)
    except Exception:
        key = 0
    if key >= 3:
        return "severe"
    if key == 2:
        return "moderate"
    if key == 1:
        return "minor"
    return ""

def epoch_int(value) -> int | None:
    try:
        if value is None or value == "":
            return None
        return int(float(str(value).strip()))
    except Exception:
        return None

def fmt_epoch_ts(value: int | None) -> str:
    if value is None:
        return ""
    try:
        return datetime.fromtimestamp(value).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""

def compact_warning_key_text(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())

def geosphere_group_key(label: str, location: str, warn_type_id: object, warn_level_id: object, title: str, description: str) -> str:
    """Stable key for repeated GeoSphere day slices of the same warning.

    GeoSphere may return one official warning as several adjacent entries
    with identical type/level/title but different end times.  The widget
    should show that as one warning with the latest end time, not as a
    stack of visually identical cards.
    """
    title_key = compact_warning_key_text(title)
    desc_key = compact_warning_key_text(clean(description, 120))
    return "|".join([
        compact_warning_key_text(label),
        compact_warning_key_text(location),
        compact_warning_key_text(warn_type_id),
        compact_warning_key_text(warn_level_id),
        title_key,
        desc_key,
    ])

def fetch_geosphere(label: str, lat: str, lon: str, language: str = "de", include=None, exclude=None) -> list[dict[str, str]]:
    """Point-based official Austrian warnings from GeoSphere Austria/ZAMG.

    This is much better for a place like Bludenz than the country-wide MeteoAlarm feed.
    Endpoint format is documented by GeoSphere's Warn API and legacy wsapp examples:
    /getWarningsForCoords?lon=...&lat=...&lang=de
    """
    lat_f = float(str(lat).strip().replace(",", "."))
    lon_f = float(str(lon).strip().replace(",", "."))
    lang = "en" if language == "en" else "de"
    url = f"https://warnungen.zamg.at/wsapp/api/getWarningsForCoords?lon={lon_f:.5f}&lat={lat_f:.5f}&lang={lang}"
    data = json.loads(urlopen_text(url, timeout=15))

    props = data.get("properties", {}) if isinstance(data, dict) else {}
    warnings = props.get("warnings", []) if isinstance(props, dict) else []
    location = ""
    loc = props.get("location", {}) if isinstance(props, dict) else {}
    if isinstance(loc, dict):
        lprops = loc.get("properties", {}) if isinstance(loc.get("properties"), dict) else {}
        location = str(lprops.get("name") or "").strip()

    # GeoSphere sometimes returns one continuous warning as several daily
    # slices.  Without grouping, Bludenz can show the same yellow heat warning
    # three times with only the expiry date changed.  We merge identical
    # source/type/level/title/description entries and keep the widest time span.
    grouped: dict[str, dict[str, object]] = {}
    order: list[str] = []

    for warning in warnings:
        wprops = warning.get("properties", {}) if isinstance(warning, dict) else {}
        raw = wprops.get("rawinfo", {}) if isinstance(wprops.get("rawinfo"), dict) else {}
        warn_type_id = wprops.get("warntypid") or raw.get("warntypid")
        warn_level_id = wprops.get("warnstufeid") or raw.get("warnstufeid")
        warn_type = geosphere_type_name(warn_type_id, language)
        level = geosphere_level_name(warn_level_id, language)
        severity = geosphere_severity(warn_level_id)
        headline = raw.get("headline") or raw.get("event") or raw.get("title") or ""
        title = headline or (f"{level} {warn_type}" if level else warn_type)
        description = raw.get("description") or raw.get("text") or raw.get("kurztext") or raw.get("langtext") or ""
        start_ts = epoch_int(raw.get("start") or wprops.get("start"))
        end_ts = epoch_int(raw.get("end") or raw.get("expires") or wprops.get("end"))
        start = fmt_epoch_ts(start_ts)
        end = fmt_epoch_ts(end_ts)
        details = " · ".join(x for x in (label, "GeoSphere", location, level, warn_type, (("until " if language == "en" else "bis ") + end if end else "")) if x)
        candidate = {
            "title": clean(title, 220),
            "details": clean(details, 260),
            "severity": severity,
            "link": "https://warnungen.zamg.at/",
            "_filter_text": " ".join(str(x) for x in (title, description, details, location, level, warn_type, start, end) if x),
        }
        if not warning_matches_filters(candidate, include, exclude):
            continue

        key = geosphere_group_key(label, location, warn_type_id, warn_level_id, title, description)
        if key not in grouped:
            grouped[key] = {
                "title": candidate["title"],
                "details_prefix": [x for x in (label, "GeoSphere", location, level, warn_type) if x],
                "severity": severity,
                "link": candidate["link"],
                "start_ts": start_ts,
                "end_ts": end_ts,
                "fallback_details": candidate["details"],
            }
            order.append(key)
        else:
            current = grouped[key]
            if start_ts is not None:
                cur_start = current.get("start_ts")
                current["start_ts"] = start_ts if cur_start is None else min(int(cur_start), start_ts)
            if end_ts is not None:
                cur_end = current.get("end_ts")
                current["end_ts"] = end_ts if cur_end is None else max(int(cur_end), end_ts)

    items: list[dict[str, str]] = []
    for key in order:
        item = grouped[key]
        end = fmt_epoch_ts(item.get("end_ts") if isinstance(item.get("end_ts"), int) else None)
        parts = list(item.get("details_prefix", []))
        if end:
            parts.append(("until " if language == "en" else "bis ") + end)
        details = " · ".join(str(x) for x in parts if x) or str(item.get("fallback_details") or "")
        items.append({
            "title": str(item.get("title") or ("Warning" if language == "en" else "Warnung")),
            "details": clean(details, 260),
            "severity": str(item.get("severity") or ""),
            "link": str(item.get("link") or "https://warnungen.zamg.at/"),
        })
        if len(items) >= 8:
            break
    return items

def fetch_nws(label: str, lat: str, lon: str, language: str = "de", include=None, exclude=None) -> list[dict[str, str]]:
    lat_f = float(str(lat).strip().replace(",", "."))
    lon_f = float(str(lon).strip().replace(",", "."))
    url = f"https://api.weather.gov/alerts/active?point={lat_f:.5f},{lon_f:.5f}"
    data = json.loads(urlopen_text(url, timeout=15))
    items = []
    for feature in data.get("features", []):
        props = feature.get("properties", {}) if isinstance(feature, dict) else {}
        title = props.get("headline") or props.get("event") or ("Warning" if language == "en" else "Warnung")
        severity = props.get("severity", "")
        certainty = props.get("certainty", "")
        urgency = props.get("urgency", "")
        area = clean(props.get("areaDesc", ""), 120)
        expires = props.get("expires", "")
        parts = [x for x in (label, "NWS", area, severity, urgency, certainty) if x]
        if expires:
            parts.append(("until " if language == "en" else "bis ") + expires[:16].replace("T", " "))
        candidate = {
            "title": clean(title, 220),
            "details": " · ".join(parts),
            "severity": clean(str(severity), 40),
            "link": props.get("@id") or props.get("id") or "https://www.weather.gov/alerts",
            "_filter_text": " ".join(str(x) for x in (title, area, props.get("description", ""), props.get("instruction", ""), props.get("event", ""), severity, urgency, certainty) if x),
        }
        if warning_matches_filters(candidate, include, exclude):
            candidate.pop("_filter_text", None)
            items.append(candidate)
        if len(items) >= 8:
            break
    return items

def fetch_warning_entry(entry: dict, language: str = "de") -> list[dict[str, str]]:
    label = str(entry.get("name", "Gebiet")).strip() or "Gebiet"
    source = str(entry.get("source", "de")).strip().lower()
    include = entry.get("include") or entry.get("filter") or entry.get("match")
    exclude = entry.get("exclude") or entry.get("hide")

    if source in ("", "de", "nina", "bbk"):
        return apply_warning_filters(fetch_nina_code(label, str(entry.get("code", "")).strip(), language), include, exclude)
    if source in ("geosphere", "zamg", "at", "austria"):
        return fetch_geosphere(label, str(entry.get("lat", "")), str(entry.get("lon", "")), language, include, exclude)
    if source in ("meteoalarm", "eu", "europe"):
        country = entry.get("country") or entry.get("code") or "europe"
        return fetch_meteoalarm(label, str(country), language, include, exclude)
    if source in ("nws", "us", "usa"):
        return fetch_nws(label, str(entry.get("lat", "")), str(entry.get("lon", "")), language, include, exclude)
    if source in ("feed", "url", "atom", "rss"):
        return fetch_warning_feed(label, str(entry.get("url", "")).strip(), language, "Feed", include, exclude)

    # Unknown source: keep old two-column behaviour if a NINA code exists.
    code = str(entry.get("code", "")).strip()
    if code:
        return apply_warning_filters(fetch_nina_code(label, code, language), include, exclude)
    return []

def nina_source_key(entry: dict) -> str:
    """Stable identity for one configured warning area."""
    return "|".join([
        str(entry.get("name", "")).strip().lower(),
        str(entry.get("source", "")).strip().lower(),
        str(entry.get("code", "")).strip().lower(),
        str(entry.get("country", "")).strip().lower(),
        str(entry.get("lat", "")).strip(),
        str(entry.get("lon", "")).strip(),
        str(entry.get("url", "")).strip().lower(),
    ])


def fetch_nina(old: dict, config: dict) -> dict:
    """Official warnings, fetched per configured area.

    This block is the one place in the widget where being quietly wrong is
    dangerous. Before v2.1.1 a failure was recorded in "errors" and then never
    shown, and the merged item list was rebuilt from the sources that happened
    to succeed. So if one area loaded and another failed, a still-valid warning
    from the failed area simply vanished, and an empty result was rendered as
    "no warnings" even though a source had not been checked at all.

    Now every source reports its own status. A source that fails keeps its last
    known warnings, flagged as cached with the time they were last confirmed,
    and the block as a whole reports that it is incomplete so the UI can say so
    instead of claiming an all-clear.
    """
    old_nina = old.get("nina", {}) if isinstance(old.get("nina"), dict) else {}
    old_sources = old_nina.get("sources", []) if isinstance(old_nina.get("sources"), list) else []
    language = ui_language(config)
    english = language == "en"
    now = time.time()

    warning_entries = [e for e in config.get("nina_codes", []) or [] if isinstance(e, dict)]

    if not warning_entries:
        return {
            "location": "",
            "updated": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            "items": [],
            "errors": [],
            "sources": [],
            "complete": True,
            "stale_sources": 0,
        }

    def previous_source(key: str) -> dict:
        for candidate in old_sources:
            if isinstance(candidate, dict) and candidate.get("key") == key:
                return candidate
        return {}

    def previous_items(key: str) -> list:
        prev = previous_source(key)
        items = prev.get("items")
        return items if isinstance(items, list) else []

    def work(index: int, entry: dict) -> tuple[int, dict]:
        label = str(entry.get("name", "Gebiet")).strip() or "Gebiet"
        key = nina_source_key(entry)
        try:
            items = fetch_warning_entry(entry, language)
            return index, {
                "key": key,
                "label": label,
                "ok": True,
                "items": items,
                "last_ok": int(now),
            }
        except Exception as exc:
            info = classify_error(exc)
            prev = previous_source(key)
            cached = previous_items(key)
            last_ok = int(prev.get("last_ok", 0) or 0)
            return index, {
                "key": key,
                "label": label,
                "ok": False,
                # Keep the last known warnings for this area rather than
                # dropping them; an expired-but-visible warning marked as
                # cached is far safer than a silent all-clear.
                "items": cached,
                "last_ok": last_ok,
                "stale": bool(cached),
                "error": {
                    "kind": info.get("kind", "unknown"),
                    "http": info.get("http", 0),
                    "message": error_message(info, language),
                },
            }

    results: dict[int, dict] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(6, len(warning_entries)))) as pool:
        futures = {pool.submit(work, i, e): (i, e) for i, e in enumerate(warning_entries)}
        for future in concurrent.futures.as_completed(futures):
            index, entry = futures[future]
            try:
                result_index, payload = future.result()
                results[result_index] = payload
            except Exception as exc:
                # Fail closed. Even an unexpected bug inside the worker must
                # count as a failed warning source; silently dropping it could
                # otherwise make complete=True and falsely permit an all-clear.
                label = str(entry.get("name", "Gebiet")).strip() or "Gebiet"
                try:
                    key = nina_source_key(entry)
                except Exception:
                    key = f"config-index:{index}"
                prev = previous_source(key)
                cached = previous_items(key)
                info = classify_error(exc)
                results[index] = {
                    "key": key,
                    "label": label,
                    "ok": False,
                    "items": cached,
                    "last_ok": int(prev.get("last_ok", 0) or 0),
                    "stale": bool(cached),
                    "error": {
                        "kind": info.get("kind", "unknown"),
                        "http": info.get("http", 0),
                        "message": error_message(info, language),
                    },
                }

    all_items: list[dict] = []
    seen_keys: set[str] = set()
    sources: list[dict] = []
    errors: list[str] = []
    locations: list[str] = []
    failed_labels: list[str] = []
    stale_sources = 0

    for index in sorted(results):
        source = results[index]
        locations.append(source["label"])

        if not source.get("ok"):
            failed_labels.append(source["label"])
            errors.append(f"{source['label']}: {source['error']['message']}")
            if source.get("stale"):
                stale_sources += 1

        for item in source.get("items", []):
            if not isinstance(item, dict):
                continue
            dedup_key = "|".join([
                str(item.get("title", "")).strip(),
                str(item.get("details", "")).strip(),
                str(item.get("severity", "")).strip(),
            ])
            if not dedup_key or dedup_key in seen_keys:
                continue
            seen_keys.add(dedup_key)
            entry_item = dict(item)
            if not source.get("ok"):
                # Mark the individual warning so the card can carry a visible
                # "cached" note; the block-level notice alone is not enough.
                entry_item["stale"] = True
                entry_item["source_label"] = source["label"]
                if source.get("last_ok"):
                    entry_item["last_ok"] = int(source["last_ok"])
            all_items.append(entry_item)

        sources.append({
            "key": source["key"],
            "label": source["label"],
            "ok": bool(source.get("ok")),
            "items": source.get("items", []),
            "last_ok": int(source.get("last_ok", 0) or 0),
            "stale": bool(source.get("stale")),
            "error": source.get("error"),
        })

    complete = not failed_labels
    if failed_labels:
        joined = ", ".join(failed_labels[:3])
        if len(failed_labels) == len(warning_entries):
            notice = (
                f"Warning status could not be updated ({joined})."
                if english else
                f"Warnstatus konnte nicht aktualisiert werden ({joined})."
            )
        else:
            notice = (
                f"Warning status for {joined} could not be updated."
                if english else
                f"Warnstatus für {joined} konnte nicht aktualisiert werden."
            )
        if stale_sources:
            notice += (
                " The last known warnings for those areas are shown."
                if english else
                " Es werden die zuletzt bekannten Warnungen dieser Gebiete angezeigt."
            )
    else:
        notice = ""

    return {
        "location": ", ".join(locations),
        "updated": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        "items": all_items,
        "errors": errors,
        "sources": sources,
        "complete": complete,
        "stale_sources": stale_sources,
        "failed_sources": len(failed_labels),
        "total_sources": len(warning_entries),
        "notice": notice,
    }


def fetch_prayer(old: dict, config: dict) -> dict:
    old_prayer = old.get("prayer", {})
    prayer_config = config.get("prayer", {}) or {}

    city = str(prayer_config.get("city", "Berlin")).strip() or "Berlin"
    country = str(prayer_config.get("country", "Germany")).strip() or "Germany"

    try:
        method = int(prayer_config.get("method", 3))
    except Exception:
        method = 3

    params = urllib.parse.urlencode({
        "city": city,
        "country": country,
        "method": method,
    })

    url = f"https://api.aladhan.com/v1/timingsByCity?{params}"

    try:
        data = json.loads(urlopen_text(url, timeout=15))
        payload = data.get("data", {})
        timings = payload.get("timings", {})
        hijri = payload.get("date", {}).get("hijri", {})
        gregorian = payload.get("date", {}).get("gregorian", {})
        meta = payload.get("meta", {}) if isinstance(payload.get("meta", {}), dict) else {}
        timezone_name = str(meta.get("timezone", "") or "").strip()

        def clean_prayer_time(value: str) -> str:
            return re.sub(r"\s*\([^)]*\)\s*$", "", str(value or "")).strip()

        def prayer_epoch(value: str):
            if not ZoneInfo or not timezone_name:
                return None
            clean_time = clean_prayer_time(value)
            match = re.match(r"^(\d{1,2}):(\d{2})$", clean_time)
            if not match:
                return None

            try:
                day_text = str(gregorian.get("date", "") or "").strip()
                day = datetime.strptime(day_text, "%d-%m-%Y").date() if day_text else datetime.now(ZoneInfo(timezone_name)).date()
                dt = datetime(day.year, day.month, day.day, int(match.group(1)), int(match.group(2)), tzinfo=ZoneInfo(timezone_name))
                return int(dt.timestamp())
            except Exception:
                return None

        def prayer_item(name: str, label: str, key: str) -> dict:
            time_value = clean_prayer_time(timings.get(key, ""))
            item = {"name": name, "label": label, "time": time_value}
            epoch_value = prayer_epoch(time_value)
            if epoch_value is not None:
                item["epoch"] = epoch_value
            return item

        day_text = str(gregorian.get("date", "") or "").strip()
        try:
            for_date = datetime.strptime(day_text, "%d-%m-%Y").date().isoformat() if day_text else ""
        except Exception:
            for_date = ""
        if not for_date:
            try:
                for_date = datetime.now(ZoneInfo(timezone_name)).date().isoformat() if ZoneInfo and timezone_name else datetime.now().date().isoformat()
            except Exception:
                for_date = datetime.now().date().isoformat()

        month = hijri.get("month", {})
        month_en = month.get("en", "") if isinstance(month, dict) else ""
        month_ar = month.get("ar", "") if isinstance(month, dict) else ""
        month_name = f"{month_en} ({month_ar})" if month_en and month_ar else (month_en or month_ar)

        if is_english(config):
            items = [
                prayer_item("Imsak (إمساك)", "Start of fasting", "Imsak"),
                prayer_item("Fajr (فجر)", "Dawn prayer", "Fajr"),
                prayer_item("Shuruq (شروق)", "Sunrise", "Sunrise"),
                prayer_item("Dhuhr (ظهر)", "Noon prayer", "Dhuhr"),
                prayer_item("Asr (عصر)", "Afternoon prayer", "Asr"),
                prayer_item("Maghrib (مغرب)", "Sunset prayer", "Maghrib"),
                prayer_item("Isha (عشاء)", "Night prayer", "Isha"),
                prayer_item("Midnight (منتصف الليل)", "Middle of the night", "Midnight"),
                prayer_item("Last third (الثلث الأخير)", "Last third", "Lastthird"),
            ]
        else:
            items = [
                prayer_item("Imsak (إمساك)", "Fasten-Beginn", "Imsak"),
                prayer_item("Fajr (فجر)", "Morgengebet", "Fajr"),
                prayer_item("Shuruq (شروق)", "Sonnenaufgang", "Sunrise"),
                prayer_item("Dhuhr (ظهر)", "Mittagsgebet", "Dhuhr"),
                prayer_item("Asr (عصر)", "Nachmittagsgebet", "Asr"),
                prayer_item("Maghrib (مغرب)", "Abendgebet", "Maghrib"),
                prayer_item("Isha (عشاء)", "Nachtgebet", "Isha"),
                prayer_item("Mitternacht (منتصف الليل)", "Mitte der Nacht", "Midnight"),
                prayer_item("Letztes Drittel (الثلث الأخير)", "Letztes Drittel", "Lastthird"),
            ]

        return {
            "location": f"{city}, {country}",
            "method": method,
            "updated": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            "hijri": f"{hijri.get('day', '')}. {month_name} {hijri.get('year', '')}".strip(),
            "items": items,
            "errors": [],
            "stale": False,
            "last_ok": int(time.time()),
            # Calendar day these timings belong to. A cached plan that is no
            # longer for today is wrong, not merely old, and the UI has to be
            # able to tell the difference.
            "for_date": for_date,
            "timezone": timezone_name,
        }
    except Exception as exc:
        info = classify_error(exc)
        previous_items = old_prayer.get("items", [])
        old_timezone = str(old_prayer.get("timezone", "") or "").strip()
        try:
            current_date = datetime.now(ZoneInfo(old_timezone)).date().isoformat() if ZoneInfo and old_timezone else datetime.now().date().isoformat()
        except Exception:
            current_date = datetime.now().date().isoformat()
        return {
            "location": old_prayer.get("location", f"{city}, {country}"),
            "method": old_prayer.get("method", method),
            "updated": old_prayer.get("updated", ""),
            "hijri": old_prayer.get("hijri", ""),
            "items": previous_items,
            "errors": [error_message(info, ui_language(config))],
            "stale": bool(previous_items),
            "last_ok": int(old_prayer.get("last_ok", 0) or 0),
            "for_date": str(old_prayer.get("for_date", "") or ""),
            "timezone": old_timezone,
            "outdated": bool(previous_items) and str(old_prayer.get("for_date", "")) != current_date,
        }


def format_decimal(value, decimals: int = 4) -> str:
    try:
        number = float(value)
    except Exception:
        return "--"

    if abs(number) >= 1000:
        return f"{number:,.2f}"

    return f"{number:.{decimals}f}".rstrip("0").rstrip(".")

def format_signed_decimal(value, decimals: int = 2) -> str:
    try:
        number = float(value)
    except Exception:
        return ""

    return f"{number:+.{decimals}f}".rstrip("0").rstrip(".")

def format_signed_percent(value, decimals: int = 2) -> str:
    try:
        number = float(value)
    except Exception:
        return ""

    return f"{number:+.{decimals}f} %"

def percent_change(current, previous):
    try:
        current_value = float(current)
        previous_value = float(previous)
    except Exception:
        return None

    if previous_value == 0:
        return None

    return ((current_value - previous_value) / previous_value) * 100

def normalize_currency_list(value) -> list[str]:
    if value is None:
        raw = DEFAULT_CONFIG["markets"]["currencies"]
    elif isinstance(value, str):
        if not value.strip():
            return []
        raw = re.split(r"[,;\s]+", value)
    elif isinstance(value, list):
        raw = value
    else:
        raw = DEFAULT_CONFIG["markets"]["currencies"]

    out = []
    for item in raw:
        code = str(item).strip().upper()
        if re.fullmatch(r"[A-Z]{3}", code) and code != "EUR" and code not in out:
            out.append(code)

    return out

INDEX_SYMBOL_ALIASES = {
    # v1.11 used Stooq-style symbols for DAX/Nikkei. Keep them working after
    # switching the primary index source to Yahoo Finance. Because naturally
    # every finance site needs its own sacred spelling of the same index.
    "^DAX": "^GDAXI",
    "DAX": "^GDAXI",
    "^NKX": "^N225",
    "NKX": "^N225",
}

STOOQ_SYMBOL_ALIASES = {
    "^GDAXI": "^DAX",
    "GDAXI": "^DAX",
    "^N225": "^NKX",
    "N225": "^NKX",
    "^DJI": "^DJI",
}

TWELVE_DATA_SYMBOL_ALIASES = {
    "^DJI": "DJI",
    "DJI": "DJI",
    "^GDAXI": "DAX",
    "GDAXI": "DAX",
    "DAX": "DAX",
    "^N225": "N225",
    "N225": "N225",
    "^NKX": "N225",
    "NKX": "N225",
}

def canonical_index_symbol(symbol: str) -> str:
    raw = str(symbol or "").strip()
    if not raw:
        return raw
    return INDEX_SYMBOL_ALIASES.get(raw.upper(), raw)

def stooq_index_symbol(symbol: str) -> str:
    raw = str(symbol or "").strip()
    if not raw:
        return raw
    return STOOQ_SYMBOL_ALIASES.get(raw.upper(), raw)

def twelve_data_index_symbol(symbol: str) -> str:
    raw = str(symbol or "").strip()
    if not raw:
        return raw
    return TWELVE_DATA_SYMBOL_ALIASES.get(raw.upper(), raw.lstrip("^"))

def normalize_indices(value) -> list[dict[str, str]]:
    if value is None:
        return list(DEFAULT_CONFIG["markets"]["indices"])
    if not isinstance(value, list):
        return list(DEFAULT_CONFIG["markets"]["indices"])

    out = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = clean(str(item.get("name", "")), 80)
        symbol = canonical_index_symbol(item.get("symbol", ""))
        if name and symbol:
            out.append({"name": name, "symbol": symbol})

    return out

def normalize_stocks(value) -> list[dict[str, str]]:
    if not isinstance(value, list):
        return list(DEFAULT_CONFIG["markets"].get("stocks", []))

    out = []
    for item in value:
        if not isinstance(item, dict):
            continue
        name = clean(str(item.get("name", "")), 80)
        symbol = str(item.get("symbol", "")).strip().upper()
        display = clean(str(item.get("display", "") or item.get("wkn", "") or item.get("isin", "")), 80)
        if name and symbol:
            entry = {"name": name, "symbol": symbol}
            if display:
                entry["display"] = display
            out.append(entry)

    return out

def config_bool(value, default: bool = True) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    text = str(value).strip().lower()
    if text in {"0", "false", "no", "nein", "off", "aus"}:
        return False
    if text in {"1", "true", "yes", "ja", "on", "an"}:
        return True
    return default

def normalize_provider_mode(value) -> str:
    mode = str(value or "auto").strip().lower()
    return mode if mode in ("auto", "yahoo", "twelve", "finnhub") else "auto"

def cached_exchange_for(old_exchange: dict, currencies: list[str], english: bool = False) -> dict:
    """Return only cached currency pairs still present in the current config."""
    old_exchange = old_exchange if isinstance(old_exchange, dict) else {}
    wanted = set()
    for code in currencies:
        wanted.add(("EUR", code))
        wanted.add((code, "EUR"))
    items = []
    for item in old_exchange.get("items", []) if isinstance(old_exchange.get("items", []), list) else []:
        if not isinstance(item, dict):
            continue
        pair = (str(item.get("base", "")).upper(), str(item.get("target", "")).upper())
        if pair in wanted:
            cached = dict(item)
            cached["stale"] = True
            items.append(cached)
    return {
        "date": old_exchange.get("date", ""),
        "previous_date": old_exchange.get("previous_date", ""),
        "items": items,
        "source": "Frankfurter / ECB" if english else "Frankfurter / EZB",
    }


def cached_instruments_for(old_data: dict, entries: list[dict[str, str]], kind: str) -> dict:
    """Filter stale market data to exact currently configured instrument identities."""
    old_data = old_data if isinstance(old_data, dict) else {}
    old_items = old_data.get("items", []) if isinstance(old_data.get("items", []), list) else []
    by_symbol = {}
    for item in old_items:
        if not isinstance(item, dict):
            continue
        raw = str(item.get("symbol", "") or "").strip()
        symbol = canonical_index_symbol(raw) if kind == "index" else raw.upper()
        if symbol and symbol not in by_symbol:
            by_symbol[symbol] = item

    items = []
    for entry in entries:
        raw = str(entry.get("symbol", "") or "").strip()
        symbol = canonical_index_symbol(raw) if kind == "index" else raw.upper()
        previous = by_symbol.get(symbol)
        if not previous:
            continue
        cached = dict(previous)
        # Keep the user's current labels/display identifiers even when the quote
        # itself came from cache. A renamed instrument must not resurrect its old
        # presentation merely because the network is down.
        cached["name"] = entry.get("name") or cached.get("name") or symbol
        cached["display_name"] = cached["name"]
        cached["symbol"] = symbol
        if kind == "stock":
            cached["display"] = entry.get("display", "")
        cached["stale"] = True
        items.append(cached)
    return {"items": items, "source": old_data.get("source", "Yahoo Finance")}

def merge_cached_exchange(current: dict, cached: dict) -> int:
    """Append cached configured FX pairs that are absent from the fresh response."""
    current_items = current.setdefault("items", []) if isinstance(current, dict) else []
    if not isinstance(current_items, list):
        current_items = []
        current["items"] = current_items
    seen = {
        (str(item.get("base", "")).upper(), str(item.get("target", "")).upper())
        for item in current_items if isinstance(item, dict)
    }
    added = 0
    for item in cached.get("items", []) if isinstance(cached, dict) else []:
        if not isinstance(item, dict):
            continue
        key = (str(item.get("base", "")).upper(), str(item.get("target", "")).upper())
        if key in seen:
            continue
        current_items.append(dict(item))
        seen.add(key)
        added += 1
    return added


def merge_cached_instruments(current: dict, cached: dict, kind: str) -> int:
    """Append cached configured symbols that are absent from fresh market data."""
    current_items = current.setdefault("items", []) if isinstance(current, dict) else []
    if not isinstance(current_items, list):
        current_items = []
        current["items"] = current_items

    def key_for(item: dict) -> str:
        raw = str(item.get("symbol", "") or "").strip()
        return canonical_index_symbol(raw) if kind == "index" else raw.upper()

    seen = {key_for(item) for item in current_items if isinstance(item, dict) and key_for(item)}
    added = 0
    for item in cached.get("items", []) if isinstance(cached, dict) else []:
        if not isinstance(item, dict):
            continue
        key = key_for(item)
        if not key or key in seen:
            continue
        current_items.append(dict(item))
        seen.add(key)
        added += 1
    return added


def fetch_exchange_rates(currencies: list[str]) -> dict:
    symbols = ",".join(urllib.parse.quote(c) for c in currencies)
    url = f"https://api.frankfurter.dev/v1/latest?base=EUR&symbols={symbols}"
    data = json.loads(urlopen_text(url, timeout=12))
    rates = data.get("rates", {}) if isinstance(data, dict) else {}
    date = data.get("date", "") if isinstance(data, dict) else ""

    previous_rates = {}
    previous_date = ""

    if date:
        try:
            latest_day = datetime.strptime(date, "%Y-%m-%d").date()
            start_day = latest_day - timedelta(days=10)
            history_url = (
                f"https://api.frankfurter.dev/v1/{start_day.isoformat()}..{latest_day.isoformat()}"
                f"?base=EUR&symbols={symbols}"
            )
            history = json.loads(urlopen_text(history_url, timeout=12, max_bytes=500_000))
            history_rates = history.get("rates", {}) if isinstance(history, dict) else {}
            dates = sorted(d for d in history_rates.keys() if d < date and isinstance(history_rates.get(d), dict))
            if dates:
                previous_date = dates[-1]
                previous_rates = history_rates.get(previous_date, {}) or {}
        except Exception:
            previous_rates = {}
            previous_date = ""

    pairs = []
    for code in currencies:
        try:
            raw_rate = rates.get(code)
            if raw_rate is None:
                continue
            rate = float(raw_rate)
        except Exception:
            continue
        if rate <= 0:
            continue

        previous_rate = None
        try:
            previous_rate = float(previous_rates.get(code))
        except Exception:
            previous_rate = None

        direct_percent = percent_change(rate, previous_rate)

        inverse_rate = 1.0 / rate
        inverse_previous = None
        try:
            if previous_rate and previous_rate > 0:
                inverse_previous = 1.0 / previous_rate
        except Exception:
            inverse_previous = None

        inverse_percent = percent_change(inverse_rate, inverse_previous)

        pairs.append({
            "label": f"EUR → {code}",
            "value": format_decimal(rate, 4),
            "base": "EUR",
            "target": code,
            "rate": rate,
            "change_percent": format_signed_percent(direct_percent) if direct_percent is not None else "",
        })
        pairs.append({
            "label": f"{code} → EUR",
            "value": format_decimal(inverse_rate, 4),
            "base": code,
            "target": "EUR",
            "rate": inverse_rate,
            "change_percent": format_signed_percent(inverse_percent) if inverse_percent is not None else "",
        })

    return {"date": date, "previous_date": previous_date, "items": pairs, "source": "Frankfurter / EZB"}

def timezone_abbreviation(tz_name: str | None, ts: int | None = None) -> str:
    if not ZoneInfo or not tz_name:
        return ""
    try:
        tz = ZoneInfo(tz_name)
        moment = datetime.fromtimestamp(int(ts), tz) if ts is not None else datetime.now(tz)
        return moment.tzname() or ""
    except Exception:
        return ""

def format_market_timestamp(ts, tz_name: str | None = None) -> tuple[str, str, str]:
    try:
        timestamp = int(ts)
    except Exception:
        return "", "", ""

    try:
        tz = ZoneInfo(tz_name) if ZoneInfo and tz_name else timezone.utc
    except Exception:
        tz = timezone.utc

    dt = datetime.fromtimestamp(timestamp, tz)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M"), (dt.tzname() or "")

def local_market_date(ts) -> str:
    """Return the user's local calendar date for a market timestamp.

    Market providers report times in the exchange timezone.  The UI uses this
    local date to decide whether a date label is needed: if the datapoint is
    from today in the user's local timezone, showing only time + foreign
    timezone is less noisy; if it is from yesterday/Friday/weekend, the date
    is essential context.
    """
    try:
        return datetime.fromtimestamp(int(ts)).strftime("%Y-%m-%d")
    except Exception:
        return ""

def market_timezone_matches_local(ts, tz_name: str | None = None) -> bool:
    """Return True when the market timezone matches the user's local zone.

    The QML side cannot reliably compare names like CEST/MESZ/GMT+2 across Qt
    versions.  Python can compare actual UTC offsets and abbreviations at the
    timestamp, which handles daylight saving time without guessing.
    """
    if not ZoneInfo or not tz_name:
        return False
    try:
        timestamp = int(ts)
        market_dt = datetime.fromtimestamp(timestamp, ZoneInfo(tz_name))
        local_dt = datetime.fromtimestamp(timestamp).astimezone()
        return market_dt.utcoffset() == local_dt.utcoffset() and market_dt.tzname() == local_dt.tzname()
    except Exception:
        return False

def parse_market_datetime(value: str | None) -> tuple[str, str]:
    text = str(value or "").strip()
    if not text:
        return "", ""

    match = re.match(r"^(\d{4}-\d{2}-\d{2})(?:[T\s](\d{2}:\d{2}))?", text)
    if match:
        return match.group(1), match.group(2) or ""

    return text, ""

def latest_chart_price_and_timestamp(data: dict) -> tuple[float | None, int | None]:
    timestamps = data.get("timestamp") or []
    indicators = data.get("indicators", {}) if isinstance(data, dict) else {}
    quotes = indicators.get("quote") or [] if isinstance(indicators, dict) else []
    quote = quotes[0] if quotes and isinstance(quotes[0], dict) else {}
    closes = quote.get("close") or []

    limit = min(len(timestamps), len(closes))
    for idx in range(limit - 1, -1, -1):
        try:
            price = float(closes[idx])
            timestamp = int(timestamps[idx])
        except Exception:
            continue
        if price > 0:
            return price, timestamp

    return None, None

def fetch_index_twelve_data(entry: dict[str, str], api_key: str) -> dict:
    name = entry.get("name") or entry.get("symbol") or "Index"
    symbol = canonical_index_symbol(entry.get("symbol", ""))
    provider_symbol = twelve_data_index_symbol(symbol)
    display = clean(str(entry.get("display", "") or entry.get("wkn", "") or entry.get("isin", "")), 80)
    key = str(api_key or "").strip()
    if not key:
        raise ValueError("missing Twelve Data API key")

    encoded_symbol = urllib.parse.quote(provider_symbol, safe="")
    encoded_tz = urllib.parse.quote(MARKET_TIMEZONE, safe="")
    url = f"https://api.twelvedata.com/quote?symbol={encoded_symbol}&timezone={encoded_tz}"
    payload = json.loads(urlopen_text(
        url,
        timeout=12,
        max_bytes=300_000,
        headers={"Authorization": f"apikey {key}"},
    ))

    if not isinstance(payload, dict):
        raise ValueError("invalid Twelve Data response")
    if payload.get("status") == "error" or payload.get("code"):
        raise ValueError(str(payload.get("message") or payload.get("code") or "Twelve Data error"))

    price = payload.get("close") or payload.get("price") or payload.get("last")
    if price is None:
        raise ValueError("missing Twelve Data price")

    # Keep Twelve Data usage to one request per instrument.  The former
    # time_series refinement consumed an extra API call per symbol, which is
    # unfriendly to small/free quotas and not worth the slightly fresher clock.
    latest_date, latest_time = "", ""

    prev = payload.get("previous_close") or payload.get("previousClose")
    change = payload.get("change")
    change_percent = payload.get("percent_change") or payload.get("percentChange")

    if change is None or change_percent is None:
        try:
            if prev is not None and float(prev) != 0:
                computed_change = float(price) - float(prev)
                computed_percent = (computed_change / float(prev)) * 100
                if change is None:
                    change = computed_change
                if change_percent is None:
                    change_percent = computed_percent
        except Exception:
            pass

    date_value, time_value = latest_date, latest_time
    tz_abbr = ""
    timestamp_value = payload.get("timestamp")
    local_date_value = ""
    local_timezone_value = False
    if not date_value and timestamp_value:
        date_value, time_value, tz_abbr = format_market_timestamp(timestamp_value, MARKET_TIMEZONE)
        local_date_value = local_market_date(timestamp_value)
        local_timezone_value = market_timezone_matches_local(timestamp_value, MARKET_TIMEZONE)
    if not date_value:
        date_value, time_value = parse_market_datetime(payload.get("datetime"))
        local_date_value = date_value
        tz_abbr = timezone_abbreviation(MARKET_TIMEZONE)

    result = {
        "name": name,
        "symbol": symbol,
        "provider_symbol": provider_symbol,
        "display": display,
        "display_name": name,
        "value": format_decimal(price, 2),
        "raw_value": str(price),
        "date": date_value,
        "time": time_value,
        "local_date": local_date_value or date_value,
        "local_timezone": local_timezone_value,
        "timezone": MARKET_TIMEZONE,
        "timezone_abbreviation": tz_abbr,
        "currency": payload.get("currency", ""),
        "exchange": payload.get("exchange", ""),
        "change": format_signed_decimal(change, 2) if change is not None else "",
        "change_percent": format_signed_percent(change_percent) if change_percent is not None else "",
    }
    return result

def fetch_index_yahoo(entry: dict[str, str]) -> dict:
    name = entry.get("name") or entry.get("symbol") or "Index"
    symbol = canonical_index_symbol(entry.get("symbol", ""))
    if not symbol:
        raise ValueError("missing symbol")

    encoded = urllib.parse.quote(symbol, safe="")
    payload = None
    last_error = None

    # Use the 1-minute chart first. The old code read only regularMarketTime
    # from metadata, which can lag behind the last chart candle. Yes, the data
    # is still provider-delayed; at least we now display the freshest candle we
    # actually received instead of worshipping stale metadata.
    for interval in ("1m", "5m"):
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{encoded}?range=1d&interval={interval}"
        try:
            payload = json.loads(urlopen_text(url, timeout=12, max_bytes=700_000))
            chart = payload.get("chart", {}) if isinstance(payload, dict) else {}
            error = chart.get("error")
            if error:
                last_error = ValueError(error.get("description") or error.get("code") or "Yahoo chart error")
                payload = None
                continue
            break
        except Exception as exc:
            last_error = exc
            payload = None

    if payload is None:
        raise last_error or ValueError("Yahoo chart error")

    chart = payload.get("chart", {}) if isinstance(payload, dict) else {}
    result = chart.get("result") or []
    if not result:
        raise ValueError("empty Yahoo chart result")

    data = result[0]
    meta = data.get("meta", {}) if isinstance(data, dict) else {}

    latest_price, latest_timestamp = latest_chart_price_and_timestamp(data)
    price = latest_price if latest_price is not None else meta.get("regularMarketPrice")
    if price is None:
        price = meta.get("previousClose") or meta.get("chartPreviousClose")
    if price is None:
        raise ValueError("missing market price")

    prev = meta.get("previousClose") or meta.get("chartPreviousClose")
    change = None
    change_percent = None
    try:
        if prev is not None and float(prev) != 0:
            change = float(price) - float(prev)
            change_percent = (change / float(prev)) * 100
    except Exception:
        change = None
        change_percent = None

    timestamp_for_display = latest_timestamp or meta.get("regularMarketTime")
    exchange_tz = meta.get("exchangeTimezoneName")
    date_value, time_value, tz_abbr = format_market_timestamp(timestamp_for_display, exchange_tz)
    local_date_value = local_market_date(timestamp_for_display)
    local_timezone_value = market_timezone_matches_local(timestamp_for_display, exchange_tz)
    if not tz_abbr:
        tz_abbr = str(meta.get("exchangeTimezoneShortName", "") or "").strip()

    display = clean(str(entry.get("display", "") or entry.get("wkn", "") or entry.get("isin", "")), 80)

    return {
        "name": name,
        "symbol": symbol,
        "display": display,
        "display_name": name,
        "value": format_decimal(price, 2),
        "raw_value": str(price),
        "date": date_value,
        "time": time_value,
        "local_date": local_date_value or date_value,
        "local_timezone": local_timezone_value,
        "timezone": exchange_tz or "",
        "timezone_abbreviation": tz_abbr,
        "currency": meta.get("currency", ""),
        "exchange": meta.get("fullExchangeName") or meta.get("exchangeName") or "",
        "change": format_signed_decimal(change, 2) if change is not None else "",
        "change_percent": format_signed_percent(change_percent) if change_percent is not None else "",
    }

def fetch_index_finnhub(entry: dict[str, str], api_key: str) -> dict:
    name = entry.get("name") or entry.get("symbol") or "Instrument"
    symbol = canonical_index_symbol(entry.get("symbol", ""))
    display = clean(str(entry.get("display", "") or entry.get("wkn", "") or entry.get("isin", "")), 80)
    key = str(api_key or "").strip()
    if not key:
        raise ValueError("missing Finnhub API key")
    if not symbol:
        raise ValueError("missing symbol")

    encoded_symbol = urllib.parse.quote(symbol, safe="")
    url = f"https://finnhub.io/api/v1/quote?symbol={encoded_symbol}"
    payload = json.loads(urlopen_text(
        url,
        timeout=12,
        max_bytes=200_000,
        headers={"X-Finnhub-Token": key},
    ))

    if not isinstance(payload, dict):
        raise ValueError("invalid Finnhub response")
    price = payload.get("c")
    if price is None or float(price) <= 0:
        raise ValueError("missing Finnhub price")

    change = payload.get("d")
    change_percent = payload.get("dp")
    timestamp_value = payload.get("t")
    date_value, time_value, tz_abbr = format_market_timestamp(timestamp_value, MARKET_TIMEZONE)
    local_date_value = local_market_date(timestamp_value)
    local_timezone_value = market_timezone_matches_local(timestamp_value, MARKET_TIMEZONE)

    return {
        "name": name,
        "symbol": symbol,
        "display": display,
        "display_name": name,
        "value": format_decimal(price, 2),
        "raw_value": str(price),
        "date": date_value,
        "time": time_value,
        "local_date": local_date_value or date_value,
        "local_timezone": local_timezone_value,
        "timezone": MARKET_TIMEZONE,
        "timezone_abbreviation": tz_abbr,
        "change": format_signed_decimal(change, 2) if change is not None else "",
        "change_percent": format_signed_percent(change_percent) if change_percent is not None else "",
    }

def fetch_indices_stooq(indices: list[dict[str, str]]) -> dict:
    symbols = [stooq_index_symbol(entry["symbol"]) for entry in indices]
    if not symbols:
        return {"items": [], "source": "Stooq fallback"}

    query = ",".join(urllib.parse.quote(symbol, safe="") for symbol in symbols)
    url = f"https://stooq.com/q/l/?s={query}&f=sd2t2ohlcv&h&e=csv"
    raw = urlopen_text(url, timeout=12, max_bytes=200_000)
    rows = list(csv.reader(io.StringIO(raw)))

    by_symbol = {stooq_index_symbol(entry["symbol"]).lower(): entry for entry in indices}
    items = []

    for row in rows:
        if len(row) < 7:
            continue
        symbol = row[0].strip()
        if not symbol or symbol.lower() == "symbol":
            continue

        entry = by_symbol.get(symbol.lower())
        if not entry:
            continue
        date = row[1].strip() if len(row) > 1 else ""
        time_value = row[2].strip() if len(row) > 2 else ""
        price = row[6].strip() if len(row) > 6 else ""
        if not price or price.upper() == "N/D":
            continue

        items.append({
            "name": entry["name"],
            "symbol": canonical_index_symbol(entry["symbol"]),
            "value": format_decimal(price, 2),
            "raw_value": price,
            "date": date,
            "time": time_value,
            "local_date": date,
        })

    return {"items": items, "source": "Stooq fallback"}

def fetch_indices_stooq_listing(indices: list[dict[str, str]]) -> dict:
    # WARNING: This function scrapes Stooq's index-listing HTML page with a
    # regex.  It is a last-resort fallback and will break silently if Stooq
    # changes their page layout.  A failed match simply returns no items, so
    # the caller falls through gracefully, but do not rely on this path as
    # the primary source.  If it starts returning nothing, check stooq.com/t/
    # and update the regex pattern accordingly.
    if not indices:
        return {"items": [], "source": "Stooq listing fallback"}

    raw = urlopen_text("https://stooq.com/t/", timeout=12, max_bytes=1_000_000)
    plain = html.unescape(re.sub(r"<[^>]+>", " ", raw))
    plain = re.sub(r"\s+", " ", plain)

    items = []

    for entry in indices:
        stooq_symbol = stooq_index_symbol(entry.get("symbol", ""))
        if not stooq_symbol:
            continue

        # Anchor on whitespace boundaries so e.g. ^DJI does not match a row
        # for ^DJIA. The literal symbol must be preceded and followed by
        # whitespace (or string start), not just be a substring of a longer
        # ticker on the same line.
        pattern = re.compile(
            r"(?:^|\s)" + re.escape(stooq_symbol) + r"(?=\s)"
            + r"\s+(.+?)\s+([0-9][0-9,]*(?:\.[0-9]+)?)\s+([+-]?[0-9]+(?:\.[0-9]+)?%)\s+([+-]?[0-9]+(?:\.[0-9]+)?)\s+([A-Z][a-z]+\s+\d+|\d{1,2}:\d{2})"
        )
        match = pattern.search(plain)
        if not match:
            continue

        _stooq_name, price, pct, change, date_value = match.groups()
        clean_percent = pct.replace("%", " %")

        items.append({
            "name": entry["name"],
            "symbol": canonical_index_symbol(entry["symbol"]),
            "value": format_decimal(price.replace(",", ""), 2),
            "raw_value": price.replace(",", ""),
            "date": date_value,
            "time": "",
            "local_date": date_value if re.match(r"^\d{4}-\d{2}-\d{2}$", date_value) else "",
            "change": format_signed_decimal(change, 2),
            "change_percent": clean_percent if clean_percent.startswith(("+", "-")) else ("+" + clean_percent),
        })

    return {"items": items, "source": "Stooq listing fallback"}

def fetch_instruments(
    entries: list[dict[str, str]],
    twelve_data_api_key: str = "",
    finnhub_api_key: str = "",
    provider_mode: str = "auto",
    kind: str = "index",
) -> dict:
    if not entries:
        return {"items": [], "source": "Yahoo Finance"}

    items = []
    missing = []
    errors = []
    source_parts = []
    disabled_providers: set[str] = set()
    api_key = str(twelve_data_api_key or "").strip()
    finnhub_key = str(finnhub_api_key or "").strip()
    mode = normalize_provider_mode(provider_mode)

    def remember_source(label: str) -> None:
        if label and label not in source_parts:
            source_parts.append(label)

    def should_disable_provider(provider: str, exc: Exception) -> bool:
        """Disable keyed providers for this refresh after clear key/quota failures.

        Unsupported individual symbols should still fall through per symbol;
        invalid credentials or quota exhaustion should not waste one request per
        configured instrument. Because apparently API providers also enjoy
        making users debug silence with a stopwatch.
        """
        if provider not in ("twelve", "finnhub"):
            return False
        msg = str(exc or "").lower()
        authish = ("api" in msg and ("key" in msg or "token" in msg)) or "unauthorized" in msg or "forbidden" in msg
        quotish = "quota" in msg or "credit" in msg or "rate limit" in msg or "too many" in msg or "429" in msg
        return authish or quotish or "401" in msg or "403" in msg

    def provider_order() -> list[str]:
        if mode == "yahoo":
            order = ["yahoo"]
            if api_key:
                order.append("twelve")
            if finnhub_key:
                order.append("finnhub")
            return order
        if mode == "twelve":
            order = ["twelve"] if api_key else []
            if finnhub_key:
                order.append("finnhub")
            order.append("yahoo")
            return order
        if mode == "finnhub":
            order = ["finnhub"] if finnhub_key else []
            if api_key:
                order.append("twelve")
            order.append("yahoo")
            return order
        # Auto: stocks can use the user's keyed APIs first. Default indices stay
        # on Yahoo first because index symbols vary wildly across finance APIs,
        # because apparently standards were too cheap to adopt.
        if kind == "stock":
            order = []
            if api_key:
                order.append("twelve")
            if finnhub_key:
                order.append("finnhub")
            order.append("yahoo")
            return order
        order = ["yahoo"]
        if api_key:
            order.append("twelve")
        if finnhub_key:
            order.append("finnhub")
        return order

    for entry in entries:
        label = entry.get("name") or entry.get("symbol") or ("Aktie" if kind == "stock" else "Index")
        provider_errors = []
        fetched = None

        for provider in provider_order():
            if provider in disabled_providers:
                continue
            try:
                if provider == "twelve":
                    fetched = fetch_index_twelve_data(entry, api_key)
                    fetched["source"] = "Twelve Data"
                    remember_source("Twelve Data")
                elif provider == "finnhub":
                    fetched = fetch_index_finnhub(entry, finnhub_key)
                    fetched["source"] = "Finnhub"
                    remember_source("Finnhub")
                else:
                    fetched = fetch_index_yahoo(entry)
                    fetched["source"] = "Yahoo Finance"
                    remember_source("Yahoo Finance")
                break
            except Exception as exc:
                provider_errors.append(f"{provider}: {type(exc).__name__}")
                if should_disable_provider(provider, exc):
                    disabled_providers.add(provider)

        if fetched:
            items.append(fetched)
        else:
            errors.append(f"{label}: " + "; ".join(provider_errors))
            missing.append(entry)

    # Stooq is only useful as an index fallback. Do not ask it for random stocks;
    # that way lies CSV-shaped sadness.
    if missing and kind == "index":
        still_missing = list(missing)
        try:
            fallback = fetch_indices_stooq(still_missing)
            if fallback.get("items"):
                for item in fallback["items"]:
                    item["source"] = "Stooq fallback"
                items.extend(fallback["items"])
                remember_source("Stooq fallback")
                fetched_symbols = {item.get("symbol") for item in fallback.get("items", [])}
                still_missing = [entry for entry in still_missing if canonical_index_symbol(entry.get("symbol", "")) not in fetched_symbols]
        except Exception as exc:
            errors.append(f"Stooq CSV fallback: {type(exc).__name__}: {str(exc)[:140]}")

        if still_missing:
            try:
                listing = fetch_indices_stooq_listing(still_missing)
                if listing.get("items"):
                    for item in listing["items"]:
                        item["source"] = "Stooq listing fallback"
                    items.extend(listing["items"])
                    remember_source("Stooq listing fallback")
                    fetched_symbols = {item.get("symbol") for item in listing.get("items", [])}
                    still_missing = [entry for entry in still_missing if canonical_index_symbol(entry.get("symbol", "")) not in fetched_symbols]
            except Exception as exc:
                errors.append(f"Stooq listing fallback: {type(exc).__name__}: {str(exc)[:140]}")

        if not still_missing:
            errors = []

    source = " / ".join(source_parts) if source_parts else "Yahoo Finance"
    return {"items": items, "source": source, "errors": errors}

def fetch_indices(indices: list[dict[str, str]], twelve_data_api_key: str = "", finnhub_api_key: str = "", provider_mode: str = "auto") -> dict:
    return fetch_instruments(indices, twelve_data_api_key, finnhub_api_key, provider_mode, "index")

def fetch_stocks(stocks: list[dict[str, str]], twelve_data_api_key: str = "", finnhub_api_key: str = "", provider_mode: str = "auto") -> dict:
    return fetch_instruments(stocks, twelve_data_api_key, finnhub_api_key, provider_mode, "stock")

def fetch_markets(old: dict, config: dict) -> dict:
    old_markets = old.get("markets", {}) if isinstance(old.get("markets", {}), dict) else {}
    market_config = config.get("markets", {}) if isinstance(config.get("markets", {}), dict) else {}
    english = is_english(config)
    exchange_label = "Exchange rates" if english else "Wechselkurse"
    indices_label = "Indices" if english else "Indizes"
    stocks_label = "Stocks" if english else "Aktien"
    stale_text = "cached data used" if english else "alte Cache-Daten verwendet"
    frankfurter_source = "Frankfurter / ECB" if english else "Frankfurter / EZB"

    show_currencies = config_bool(market_config.get("show_currencies"), True)
    show_indices = config_bool(market_config.get("show_indices"), True)
    show_stocks = config_bool(market_config.get("show_stocks"), True)

    currencies = normalize_currency_list(market_config.get("currencies", DEFAULT_CONFIG["markets"]["currencies"]))
    indices = normalize_indices(market_config.get("indices", DEFAULT_CONFIG["markets"]["indices"]))
    stocks = normalize_stocks(market_config.get("stocks", DEFAULT_CONFIG["markets"].get("stocks", [])))
    twelve_data_api_key = str(market_config.get("twelve_data_api_key", "") or "").strip()
    finnhub_api_key = str(market_config.get("finnhub_api_key", "") or "").strip()
    provider_mode = normalize_provider_mode(market_config.get("provider_mode", "auto"))

    errors = []

    if show_currencies and currencies:
        try:
            exchange = fetch_exchange_rates(currencies)
            exchange["source"] = frankfurter_source
            cached_exchange = cached_exchange_for(old_markets.get("exchange", {}), currencies, english)
            if merge_cached_exchange(exchange, cached_exchange):
                errors.append(f"{exchange_label}: {stale_text}")
        except Exception as exc:
            exchange = cached_exchange_for(old_markets.get("exchange", {}), currencies, english)
            errors.append(f"{exchange_label}: {type(exc).__name__}: {str(exc)[:140]}")
            if exchange.get("items"):
                errors.append(f"{exchange_label}: {stale_text}")
    else:
        exchange = {"items": [], "source": frankfurter_source, "date": "", "previous_date": ""}

    if show_indices and indices:
        try:
            index_data = fetch_indices(indices, twelve_data_api_key, finnhub_api_key, provider_mode)
            if index_data.get("errors"):
                errors.extend([f"{indices_label}: {err}" for err in index_data.get("errors", [])])
            cached = cached_instruments_for(old_markets.get("indices", {}), indices, "index")
            if not index_data.get("items"):
                if cached.get("items"):
                    index_data = cached
                    errors.append(f"{indices_label}: {stale_text}")
            elif merge_cached_instruments(index_data, cached, "index"):
                errors.append(f"{indices_label}: {stale_text}")
        except Exception as exc:
            index_data = cached_instruments_for(old_markets.get("indices", {}), indices, "index")
            errors.append(f"{indices_label}: {type(exc).__name__}: {str(exc)[:140]}")
            if index_data.get("items"):
                errors.append(f"{indices_label}: {stale_text}")
    else:
        index_data = {"items": [], "source": "Yahoo Finance"}

    if show_stocks and stocks:
        try:
            stock_data = fetch_stocks(stocks, twelve_data_api_key, finnhub_api_key, provider_mode)
            if stock_data.get("errors"):
                errors.extend([f"{stocks_label}: {err}" for err in stock_data.get("errors", [])])
            cached = cached_instruments_for(old_markets.get("stocks", {}), stocks, "stock")
            if not stock_data.get("items"):
                if cached.get("items"):
                    stock_data = cached
                    errors.append(f"{stocks_label}: {stale_text}")
            elif merge_cached_instruments(stock_data, cached, "stock"):
                errors.append(f"{stocks_label}: {stale_text}")
        except Exception as exc:
            stock_data = cached_instruments_for(old_markets.get("stocks", {}), stocks, "stock")
            errors.append(f"{stocks_label}: {type(exc).__name__}: {str(exc)[:140]}")
            if stock_data.get("items"):
                errors.append(f"{stocks_label}: {stale_text}")
    else:
        stock_data = {"items": [], "source": "Yahoo Finance"}

    return {
        "updated": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        "exchange": exchange,
        "indices": index_data,
        "stocks": stock_data,
        "show_currencies": show_currencies,
        "show_indices": show_indices,
        "show_stocks": show_stocks,
        "errors": errors,
    }


def resolve_command(command: str) -> str | None:
    """Return an absolute executable path using the user's PATH first and the
    helper's sanitized PATH second.  This keeps the tool-detection checks and
    subprocess execution in sync under systemd user services.
    """
    found = shutil.which(command)
    if found:
        return found
    return shutil.which(command, path=SAFE_SUBPROCESS_PATH)


def run_process(args: list[str], timeout: float = 3.0, env: dict | None = None) -> subprocess.CompletedProcess | None:
    if not args:
        return None
    exe = resolve_command(args[0])
    if not exe:
        return None
    try:
        return subprocess.run(
            [exe] + list(args[1:]),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
            env=env or SAFE_SUBPROCESS_ENV,
        )
    except Exception:
        return None


def run_command(args: list[str], timeout: float = 3.0) -> tuple[bool, str]:
    proc = run_process(args, timeout=timeout)
    if proc is None:
        return False, f"{args[0] if args else 'command'} not found"

    out = (proc.stdout or "").strip()
    err = (proc.stderr or "").strip()
    return proc.returncode == 0, out or err


def format_duration(seconds: float, english: bool = False) -> str:
    try:
        seconds = max(0, int(seconds))
    except Exception:
        seconds = 0
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, _ = divmod(rem, 60)
    if days:
        return f"{days}d {hours}h" if english else f"{days} T {hours} h"
    if hours:
        return f"{hours}h {minutes}m" if english else f"{hours} h {minutes} min"
    return f"{minutes}m" if english else f"{minutes} min"


def format_boot_time(english: bool = False) -> tuple[str, str]:
    try:
        text = Path("/proc/stat").read_text(encoding="utf-8", errors="replace")
        match = re.search(r"^btime\s+(\d+)", text, re.M)
        if not match:
            raise ValueError("btime not found")
        ts = int(match.group(1))
        boot = datetime.fromtimestamp(ts)
        since = format_duration(time.time() - ts, english)
        return boot.strftime("%d.%m.%Y %H:%M"), since
    except Exception:
        return "--", "--"


def _format_session_type(value: str) -> str:
    value = (value or "").strip().lower()
    if value == "wayland":
        return "Wayland"
    if value in ("x11", "xorg"):
        return "X11"
    return value.strip() if value else ""


def _loginctl_session_ids() -> list[str]:
    ids: list[str] = []
    current = (os.environ.get("XDG_SESSION_ID") or "").strip()
    if current:
        ids.append(current)

    if not shutil.which("loginctl"):
        return ids

    ok, out = run_command(["loginctl", "list-sessions", "--no-legend"], timeout=2.5)
    if not ok or not out:
        return ids

    uid = str(os.getuid())
    user = getpass.getuser()
    for line in out.splitlines():
        parts = line.split()
        if not parts:
            continue
        session_id = parts[0]
        session_uid = parts[1] if len(parts) > 1 else ""
        session_user = parts[2] if len(parts) > 2 else ""
        if session_id and (session_uid == uid or session_user == user) and session_id not in ids:
            ids.append(session_id)
    return ids


def _loginctl_session_properties(session_id: str) -> dict[str, str]:
    if not session_id or not shutil.which("loginctl"):
        return {}
    ok, out = run_command([
        "loginctl",
        "show-session",
        session_id,
        "-p", "Type",
        "-p", "Desktop",
        "-p", "Class",
        "-p", "State",
        "-p", "Active",
    ], timeout=2.5)
    if not ok or not out:
        return {}
    props: dict[str, str] = {}
    for line in out.splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        props[key.strip()] = value.strip()
    return props


def _graphical_login_sessions() -> list[dict[str, str]]:
    sessions: list[dict[str, str]] = []
    for session_id in _loginctl_session_ids():
        props = _loginctl_session_properties(session_id)
        if not props:
            continue
        props["Id"] = session_id
        session_type = (props.get("Type") or "").strip().lower()
        session_class = (props.get("Class") or "").strip().lower()
        desktop = (props.get("Desktop") or "").strip().lower()
        if session_type in ("wayland", "x11", "xorg") or desktop or session_class == "user":
            sessions.append(props)

    def score(props: dict[str, str]) -> tuple[int, int, int, int]:
        active = 1 if (props.get("Active") or "").lower() == "yes" else 0
        state = 1 if (props.get("State") or "").lower() in ("active", "online") else 0
        graphical = 1 if (props.get("Type") or "").lower() in ("wayland", "x11", "xorg") else 0
        kde = 1 if (props.get("Desktop") or "").lower() in ("kde", "plasma") else 0
        return (active, state, graphical, kde)

    return sorted(sessions, key=score, reverse=True)


def current_session_type() -> str:
    session = _format_session_type(os.environ.get("XDG_SESSION_TYPE") or "")
    if session:
        return session
    if os.environ.get("WAYLAND_DISPLAY"):
        return "Wayland"
    if os.environ.get("DISPLAY"):
        return "X11"

    for props in _graphical_login_sessions():
        session = _format_session_type(props.get("Type") or "")
        if session:
            return session

    runtime_dir = Path(os.environ.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}")
    try:
        if any(runtime_dir.glob("wayland-*")):
            return "Wayland"
    except Exception:
        pass
    try:
        if Path("/tmp/.X11-unix").exists() and any(Path("/tmp/.X11-unix").iterdir()):
            return "X11"
    except Exception:
        pass
    return "--"


def _package_version(package_names: list[str]) -> str:
    if shutil.which("pacman"):
        for package in package_names:
            ok, out = run_command(["pacman", "-Q", package], timeout=2.5)
            if ok and out:
                parts = out.split()
                if len(parts) >= 2:
                    return parts[1]
    if shutil.which("dpkg-query"):
        for package in package_names:
            ok, out = run_command(["dpkg-query", "-W", "-f=${Version}", package], timeout=2.5)
            if ok and out and "no packages found" not in out.lower():
                return out.splitlines()[0].strip()
    if shutil.which("rpm"):
        for package in package_names:
            ok, out = run_command(["rpm", "-q", "--qf", "%{VERSION}", package], timeout=2.5)
            if ok and out and "not installed" not in out.lower():
                return out.splitlines()[0].strip()
    return ""


def desktop_version() -> str:
    desktop = (os.environ.get("XDG_CURRENT_DESKTOP") or os.environ.get("DESKTOP_SESSION") or "").strip()
    if not desktop:
        for props in _graphical_login_sessions():
            desktop = (props.get("Desktop") or "").strip()
            if desktop:
                break

    desktop_norm = desktop.replace(":", "/").strip()
    parts: list[str] = []

    ok, out = run_command(["plasmashell", "--version"], timeout=3)
    if ok and out:
        parts.append(out.replace("plasmashell", "Plasma").strip())

    if not parts:
        version = _package_version(["plasma-workspace", "plasma6-workspace"])
        if version:
            parts.append(f"KDE Plasma {version}")

    ok, out = run_command(["gnome-shell", "--version"], timeout=3)
    if ok and out and not parts:
        parts.append(out.strip())

    if not parts:
        version = _package_version(["gnome-shell"])
        if version:
            parts.append(f"GNOME Shell {version}")

    if not parts and shutil.which("pgrep"):
        ok, _ = run_command(["pgrep", "-x", "plasmashell"], timeout=2)
        if ok:
            parts.append("KDE Plasma")
        else:
            ok, _ = run_command(["pgrep", "-x", "gnome-shell"], timeout=2)
            if ok:
                parts.append("GNOME Shell")

    if desktop_norm:
        canonical = desktop_norm.replace("KDE", "KDE Plasma") if desktop_norm.upper() == "KDE" else desktop_norm
        if not any(canonical.lower() in p.lower() or desktop_norm.lower() in p.lower() for p in parts):
            parts.append(canonical)

    return " · ".join(parts) if parts else "--"


def clean_hardware_name(value: str) -> str:
    value = re.sub(r"\s*\[[0-9a-fA-F:.]+\]", "", value or "")
    value = re.sub(r"\s+", " ", value).strip()
    if value.lower() in ("unknown", "none", "n/a"):
        return "--"
    value = value.replace("Corporation ", "")
    value = value.replace("Advanced Micro Devices, Inc. [AMD/ATI] ", "AMD ")
    value = value.replace("NVIDIA Corporation ", "NVIDIA ")
    value = value.replace("Intel Corporation ", "Intel ")
    return value or "--"


def graphics_info() -> tuple[str, str]:
    driver = ""
    models: list[str] = []

    if shutil.which("nvidia-smi"):
        ok, out = run_command([
            "nvidia-smi",
            "--query-gpu=name,driver_version",
            "--format=csv,noheader",
        ], timeout=4)
        if ok and out:
            for line in out.splitlines():
                parts = [part.strip() for part in line.split(",")]
                if len(parts) >= 2:
                    if not driver:
                        driver = f"NVIDIA {parts[1]}"
                    if parts[0] and parts[0] not in models:
                        models.append(clean_hardware_name(parts[0]))
                elif line.strip() and line.strip() not in models:
                    models.append(clean_hardware_name(line.strip()))

    proc_version = Path("/proc/driver/nvidia/version")
    if not driver and proc_version.exists():
        text = proc_version.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"Kernel Module\s+([0-9.]+)", text)
        driver = f"NVIDIA {match.group(1)}" if match else "NVIDIA"

    if shutil.which("lspci"):
        ok, out = run_command(["lspci", "-nnk"], timeout=4)
        if ok and out:
            blocks = re.split(r"\n(?=\S)", out)
            pci_drivers: list[str] = []
            for block in blocks:
                if re.search(r"VGA compatible controller|3D controller|Display controller", block, re.I):
                    first = block.splitlines()[0]
                    first = re.sub(r"^[0-9a-f:.]+\s+", "", first, flags=re.I)
                    first = clean_hardware_name(first)
                    if first and first != "--" and first not in models:
                        models.append(first)
                    for line in block.splitlines()[1:]:
                        m = re.search(r"Kernel driver in use:\s*(.+)", line)
                        if m:
                            drv = m.group(1).strip()
                            if drv and drv not in pci_drivers:
                                pci_drivers.append(drv)
                            break
            if not driver and pci_drivers:
                driver = " / ".join(pci_drivers[:2])

    return driver or "--", " / ".join(models[:2]) if models else "--"



def cpu_model() -> str:
    cpuinfo = Path("/proc/cpuinfo")
    if cpuinfo.exists():
        text = cpuinfo.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"^model name\s*:\s*(.+)$", text, re.M)
        if match:
            return clean_hardware_name(match.group(1))
        match = re.search(r"^Hardware\s*:\s*(.+)$", text, re.M)
        if match:
            return clean_hardware_name(match.group(1))
    if shutil.which("lscpu"):
        ok, out = run_command(["lscpu"], timeout=3)
        if ok and out:
            match = re.search(r"^Model name:\s*(.+)$", out, re.M)
            if match:
                return clean_hardware_name(match.group(1))
    return "--"


def memory_total() -> str:
    meminfo = Path("/proc/meminfo")
    if meminfo.exists():
        text = meminfo.read_text(encoding="utf-8", errors="replace")
        match = re.search(r"^MemTotal:\s+(\d+)\s+kB", text, re.M)
        if match:
            gib = int(match.group(1)) / 1024 / 1024
            if gib >= 9.95:
                return f"{gib:.0f} GiB"
            return f"{gib:.1f} GiB"
    return "--"


def _strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text or "")


def _nonempty_lines(text: str) -> list[str]:
    return [line.strip() for line in _strip_ansi(text).splitlines() if line.strip()]

def _count_pkcon_updates() -> tuple[int, str] | None:
    """Use PackageKit as a cross-distro fallback.

    KDE Discover commonly talks to PackageKit, so this catches many systems
    where native package-manager CLIs are unavailable, sandboxed, or stale.
    We parse only package rows and ignore progress/status chatter.
    """
    proc = run_process(["pkcon", "get-updates"], timeout=45, env={**SAFE_SUBPROCESS_ENV, "LC_ALL": "C", "LANG": "C"})
    if proc is None:
        return None
    text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    lines = _nonempty_lines(text)
    count = 0
    unrecognized_payload = 0
    status_prefixes = (
        "getting", "loading", "querying", "refreshing", "finished", "waiting", "starting",
        "available updates", "there are no updates", "no packages require updating",
        "transaction", "percentage", "status",
    )
    for line in lines:
        low = line.lower()
        if not line or low.startswith(status_prefixes):
            continue
        # PackageKit rows normally contain package IDs like name;version;arch;repo
        # and often start with an update severity/status word.
        if ";" in line and not low.startswith(("transaction", "percentage", "status")):
            count += 1
            continue
        if re.match(r"^(low|normal|important|security|bugfix|enhancement|blocked)\s+\S+;", line, re.I):
            count += 1
            continue
        # A non-empty, non-status line that we did not match. PackageKit
        # output varies across distros; rather than report "0 updates" when
        # we silently skipped real package rows, give up and let the caller
        # treat the result as "unknown".
        unrecognized_payload += 1
    if count:
        return count, "PackageKit"
    if proc.returncode == 0 and unrecognized_payload == 0:
        return 0, "PackageKit"
    return None


def _count_flatpak_updates() -> tuple[int, str] | None:
    # Flatpak is not a system package manager, but KDE Discover often shows
    # Flatpak updates next to system updates.  Use it only as an additive
    # optional source when available and fast enough.
    proc = run_process(["flatpak", "remote-ls", "--updates"], timeout=20, env={**SAFE_SUBPROCESS_ENV, "LC_ALL": "C", "LANG": "C"})
    if proc is None or proc.returncode != 0:
        return None
    lines = _nonempty_lines(proc.stdout or "")
    # Header line usually contains Application ID / Version / Branch.
    data_lines = [line for line in lines if not line.lower().startswith(("application id", "ref", "name"))]
    return len(data_lines), "flatpak"


def _count_pacman_updates(checkupdates_failed: bool = False) -> tuple[int, str] | None:
    # Arch, CachyOS, EndeavourOS, Manjaro and related systems.
    checkupdates_path = resolve_command("checkupdates")
    if checkupdates_path:
        # Use a dedicated cache DB so checkupdates does not touch the real
        # pacman sync database.  This is the official pacman-contrib pattern.
        db_path = OUT_DIR / "checkupdates-db"
        db_path.mkdir(parents=True, exist_ok=True)
        env = {
            **SAFE_SUBPROCESS_ENV,
            "LC_ALL": "C",
            "LANG": "C",
            "CHECKUPDATES_DB": str(db_path),
        }
        proc = run_process(["checkupdates"], timeout=55, env=env)
        if proc is not None:
            lines = _nonempty_lines(proc.stdout or "")
            if lines:
                return len(lines), "checkupdates"
            # pacman-contrib uses 2 for "no updates" on several versions.
            if proc.returncode in (0, 2):
                return 0, "checkupdates"
            checkupdates_failed = True

    # Fallback: local pacman database.  This can be stale, but it is still a
    # useful signal and avoids showing "--" when checkupdates fails under a
    # user systemd service.  If it reports real packages, trust the count.
    proc = run_process(["pacman", "-Qu"], timeout=15, env={**SAFE_SUBPROCESS_ENV, "LC_ALL": "C", "LANG": "C"})
    if proc is not None and proc.returncode in (0, 1):
        lines = _nonempty_lines(proc.stdout or "")
        if lines:
            return len(lines), "pacman -Qu"
        if not checkupdates_failed:
            return 0, "pacman -Qu"

    # AUR/helper fallbacks.  These are intentionally after pacman/checkupdates,
    # because users usually expect the main number to reflect regular package
    # updates first.  If only an AUR helper knows about updates, showing that
    # count is still more useful than "--".
    for helper in ("paru", "yay"):
        proc = run_process([helper, "-Qua"], timeout=35, env={**SAFE_SUBPROCESS_ENV, "LC_ALL": "C", "LANG": "C"})
        if proc is not None and proc.returncode in (0, 1):
            lines = _nonempty_lines(proc.stdout or "")
            if lines:
                return len(lines), helper
    return None


def _count_apt_updates() -> tuple[int, str] | None:
    # Debian, Ubuntu, Kubuntu, KDE neon and derivatives.  `apt-get -s upgrade`
    # is more machine-readable than localized `apt list --upgradable` output.
    env = {**SAFE_SUBPROCESS_ENV, "LC_ALL": "C", "LANG": "C"}
    proc = run_process(["apt-get", "-s", "upgrade"], timeout=30, env=env)
    if proc is not None and proc.returncode == 0:
        lines = [line for line in _nonempty_lines(proc.stdout or "") if line.startswith("Inst ")]
        return len(lines), "apt-get"

    proc = run_process(["apt", "list", "--upgradable"], timeout=25, env=env)
    if proc is not None and proc.returncode == 0:
        lines = [line for line in _nonempty_lines(proc.stdout or "") if "/" in line and "upgradable" in line.lower()]
        return len(lines), "apt"
    return None


def _count_dnf_updates() -> tuple[int, str] | None:
    env = {**SAFE_SUBPROCESS_ENV, "LC_ALL": "C", "LANG": "C"}
    # Fedora 41+ / dnf5.  Exit code 100 means updates available.
    for args, source in ((["dnf5", "-q", "check-upgrade"], "dnf5"), (["dnf", "-q", "check-update"], "dnf")):
        proc = run_process(args, timeout=45, env=env)
        if proc is None or proc.returncode not in (0, 100):
            continue
        lines = []
        for line in _nonempty_lines(proc.stdout or ""):
            low = line.lower()
            if low.startswith(("last metadata", "metadata", "obsoleting", "security:")):
                continue
            parts = line.split()
            # dnf rows usually have: name.arch version repo. Match any short
            # arch suffix (alphanumeric, common values include noarch, x86_64,
            # aarch64, i686, armv7hl, ppc64le, s390x, riscv64, src). The
            # previous hard-coded list silently produced "0 updates" on every
            # other architecture.
            if len(parts) >= 3 and re.search(r"\.[a-z0-9_]{2,12}$", parts[0]):
                lines.append(line)
        return len(lines), source
    return None


def _count_zypper_updates() -> tuple[int, str] | None:
    # openSUSE Tumbleweed / Leap.  Use the table output and count package rows.
    env = {**SAFE_SUBPROCESS_ENV, "LC_ALL": "C", "LANG": "C"}
    proc = run_process(["zypper", "--non-interactive", "-q", "list-updates"], timeout=35, env=env)
    if proc is not None and proc.returncode == 0:
        lines = []
        for line in _nonempty_lines(proc.stdout or ""):
            if re.match(r"^v\s*\|", line) or re.match(r"^package\s*\|", line, re.I):
                lines.append(line)
        return len(lines), "zypper"
    return None


def updates_available() -> tuple[str, str]:
    """Return the number of available updates and the source used.

    The detection is deliberately multi-layered.  Different KDE Plasma distros
    expose update information through different tools: Arch-like systems prefer
    checkupdates/pacman, Debian-like systems use apt, Fedora uses dnf/dnf5,
    openSUSE uses zypper, and KDE Discover often uses PackageKit.  We try the
    native package manager first, then PackageKit as a broad desktop fallback.
    """
    counters: list[tuple[int, str]] = []

    # Native package managers.  These are cheap enough and most precise for the
    # user's base system.  Each helper returns None when the tool is absent or
    # unusable, and (0, source) only when it could confidently check.
    for checker in (_count_pacman_updates, _count_apt_updates, _count_dnf_updates, _count_zypper_updates):
        try:
            result = checker()
        except Exception:
            result = None
        if result is not None:
            count, source = result
            # If a native tool found updates, return immediately.  If it found
            # zero, keep it as a fallback but still let PackageKit potentially
            # report updates known to KDE Discover.
            if count > 0:
                flatpak = _count_flatpak_updates()
                if flatpak and flatpak[0] > 0:
                    return str(count + flatpak[0]), f"{source}+flatpak"
                return str(count), source
            counters.append((count, source))

    # Desktop-level fallback used by KDE Discover on many distributions.
    try:
        pk = _count_pkcon_updates()
    except Exception:
        pk = None
    if pk is not None:
        count, source = pk
        if count > 0:
            flatpak = _count_flatpak_updates()
            if flatpak and flatpak[0] > 0:
                return str(count + flatpak[0]), f"{source}+flatpak"
            return str(count), source
        counters.append((count, source))

    # Flatpak-only fallback.  This keeps the field useful on machines where
    # Discover mainly manages Flatpak apps.
    try:
        flatpak = _count_flatpak_updates()
    except Exception:
        flatpak = None
    if flatpak is not None and flatpak[0] > 0:
        return str(flatpak[0]), flatpak[1]

    # If any tool confidently checked and found zero, show 0.  Otherwise the
    # update state is genuinely unknown.
    if counters:
        return "0", "+".join(source for _, source in counters[:2])
    return "--", ""

def _shorten_items(values: list[str], limit: int = 3) -> str:
    cleaned: list[str] = []
    for value in values:
        label = re.sub(r"\s+", " ", str(value or "").strip())
        if label and label not in cleaned:
            cleaned.append(label)
    if not cleaned:
        return ""
    if len(cleaned) > limit:
        return ", ".join(cleaned[:limit]) + f" +{len(cleaned) - limit}"
    return ", ".join(cleaned)


def _vpn_like_interface(name: str) -> bool:
    n = str(name or "").strip().lower()
    if not n:
        return False
    prefixes = (
        "wg", "tun", "tap", "ppp", "ipsec", "cscotun",
        "tailscale", "zt", "zerotier", "nordlynx", "proton",
        "mullvad", "mlvd", "warp", "utun", "vpn",
    )
    return n.startswith(prefixes) or "wireguard" in n or "vpn" in n


def active_interface_names() -> list[str]:
    names: list[str] = []
    if not shutil.which("ip"):
        return names
    ok, out = run_command(["ip", "-o", "link", "show", "up"], timeout=3)
    if not ok or not out:
        return names
    for line in out.splitlines():
        # Example: 3: wlp4s0: <BROADCAST,MULTICAST,UP,...
        m = re.match(r"\d+:\s+([^:@]+)", line.strip())
        if m:
            name = m.group(1).strip()
            if name and name not in names:
                names.append(name)
    return names


def default_route_interfaces() -> list[str]:
    names: list[str] = []
    if not shutil.which("ip"):
        return names
    ok, out = run_command(["ip", "-o", "route", "show", "default"], timeout=3)
    if not ok or not out:
        return names
    for line in out.splitlines():
        m = re.search(r"\bdev\s+(\S+)", line)
        if m:
            name = m.group(1).strip()
            if name and name not in names:
                names.append(name)
    return names


def nmcli_vpn_connections() -> list[str]:
    names: list[str] = []
    if not shutil.which("nmcli"):
        return names
    ok, out = run_command(["nmcli", "-t", "-f", "NAME,TYPE,DEVICE", "connection", "show", "--active"], timeout=4)
    if not ok or not out:
        return names
    for raw in out.splitlines():
        parts = raw.split(":")
        if len(parts) < 2:
            continue
        conn_name = parts[0].replace("\\:", ":").strip()
        conn_type = parts[1].strip().lower()
        device = parts[2].strip() if len(parts) > 2 else ""
        if conn_type in ("vpn", "wireguard") or _vpn_like_interface(device) or _vpn_like_interface(conn_name):
            label = conn_name or device
            if label and label not in names:
                names.append(label)
    return names


def provider_vpn_status() -> list[str]:
    names: list[str] = []

    def add(label: str) -> None:
        if label and label not in names:
            names.append(label)

    if shutil.which("mullvad"):
        ok, out = run_command(["mullvad", "status"], timeout=3)
        if ok and re.search(r"\bconnected\b", out, re.I):
            add("Mullvad")

    if shutil.which("warp-cli"):
        ok, out = run_command(["warp-cli", "status"], timeout=3)
        if ok and re.search(r"\bconnected\b", out, re.I):
            add("Cloudflare WARP")

    if shutil.which("tailscale"):
        ok, out = run_command(["tailscale", "status", "--json"], timeout=4)
        if ok:
            try:
                data = json.loads(out)
                if isinstance(data, dict) and data.get("BackendState") == "Running":
                    add("Tailscale")
            except Exception:
                if re.search(r"\bactive|running\b", out, re.I):
                    add("Tailscale")

    if shutil.which("nordvpn"):
        ok, out = run_command(["nordvpn", "status"], timeout=3)
        if ok and re.search(r"Status:\s*Connected", out, re.I):
            add("NordVPN")

    return names


_VPN_NAME_CACHE: list[str] | None = None


def detected_vpn_names() -> list[str]:
    """Names of VPN tunnels that currently look active.

    Cached for the lifetime of the process: a single cache run asks at most
    once, and the answer cannot meaningfully change mid-refresh.
    """
    global _VPN_NAME_CACHE
    if _VPN_NAME_CACHE is not None:
        return _VPN_NAME_CACHE

    names: list[str] = []
    try:
        for value in provider_vpn_status() + nmcli_vpn_connections():
            if value and value not in names:
                names.append(value)
        if not names:
            for iface in default_route_interfaces():
                if _vpn_like_interface(iface) and iface not in names:
                    names.append(iface)
    except Exception:
        names = []

    _VPN_NAME_CACHE = names
    return names


def vpn_status_item(manual_label: str, english: bool = False) -> dict[str, str]:
    manual = re.sub(r"\s+", " ", str(manual_label or "").strip())[:40]

    detected: list[str] = []
    detected.extend(provider_vpn_status())
    detected.extend(nmcli_vpn_connections())

    default_vpn = [iface for iface in default_route_interfaces() if _vpn_like_interface(iface)]
    active_vpn = [iface for iface in active_interface_names() if _vpn_like_interface(iface)]
    detected.extend(default_vpn)
    detected.extend(active_vpn)

    detail = _shorten_items(detected)
    if detail:
        value = ("ON" if english else "AN") + f" · {detail}"
        return {"key": "vpn", "label": "VPN", "value": value, "state": "active"}

    if manual:
        value = ("manual" if english else "manuell") + f" · {manual}"
        return {"key": "vpn", "label": "VPN", "value": value, "state": "manual"}

    return {"key": "vpn", "label": "VPN", "value": ("OFF / not detected" if english else "AUS / nicht erkannt"), "state": "unknown"}

def local_network_info() -> list[dict[str, str]]:
    items: list[dict[str, str]] = []

    hostname = platform.node() or ""
    if hostname:
        items.append({"key": "hostname", "label": "Host", "value": hostname})

    iface = ""
    gateway = ""
    ok, out = run_command(["ip", "route", "show", "default"], timeout=3) if shutil.which("ip") else (False, "")
    if ok and out:
        line = out.splitlines()[0]
        m = re.search(r"\bdev\s+(\S+)", line)
        if m:
            iface = m.group(1)
        m = re.search(r"\bvia\s+((?:\d{1,3}\.){3}\d{1,3})", line)
        if m:
            gateway = m.group(1)

    if iface:
        items.append({"key": "interface", "label": "Interface", "value": iface})

    local_ip = ""
    if shutil.which("ip"):
        if iface:
            ok, out = run_command(["ip", "-o", "-4", "addr", "show", "dev", iface, "scope", "global"], timeout=3)
        else:
            ok, out = run_command(["ip", "-o", "-4", "addr", "show", "scope", "global"], timeout=3)
        if ok and out:
            m = re.search(r"\binet\s+((?:\d{1,3}\.){3}\d{1,3})/", out)
            if m:
                local_ip = m.group(1)
    if local_ip:
        items.append({"key": "lan_ip", "label": "LAN IP", "value": local_ip})

    if gateway:
        items.append({"key": "gateway", "label": "Gateway", "value": gateway})

    dns_values: list[str] = []
    if shutil.which("resolvectl"):
        ok, out = run_command(["resolvectl", "dns"], timeout=3)
        if ok and out:
            for ip in re.findall(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", out):
                if ip not in dns_values:
                    dns_values.append(ip)
    if not dns_values:
        resolv = Path("/etc/resolv.conf")
        if resolv.exists():
            for line in resolv.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if line.startswith("nameserver"):
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] not in dns_values:
                        dns_values.append(parts[1])
    if dns_values:
        items.append({"key": "dns", "label": "DNS", "value": ", ".join(dns_values[:3])})

    return items


def public_network_info() -> list[dict[str, str]]:
    # Optional privacy-sensitive lookup. Only called when explicitly enabled.
    try:
        req = urllib.request.Request(
            "https://ipinfo.io/json",
            headers={"User-Agent": UA, "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            # ipinfo normally returns only a few hundred bytes. Keep the same
            # defensive bounded-read rule used by the other HTTP helpers so an
            # unexpected upstream response cannot consume unbounded memory.
            raw = resp.read(200_001)
            if len(raw) > 200_000:
                return []
            data = json.loads(raw.decode("utf-8", errors="replace"))
        if not isinstance(data, dict):
            return []
        out: list[dict[str, str]] = []
        ip = str(data.get("ip") or "").strip()
        org = str(data.get("org") or "").strip()
        city = str(data.get("city") or "").strip()
        country = str(data.get("country") or "").strip()
        if ip:
            out.append({"key": "public_ip", "label": "Public IP", "value": ip})
        if org:
            org = re.sub(r"^AS\d+\s+", "", org).strip()
            out.append({"key": "isp", "label": "ISP", "value": org[:80]})
        loc = ", ".join([x for x in [city, country] if x])
        if loc:
            out.append({"key": "public_location", "label": "WAN-Ort", "value": loc})
        return out
    except Exception:
        return []


def fetch_system_info(old: dict, config: dict) -> dict:
    english = is_english(config)
    cfg = config.get("system", {}) if isinstance(config.get("system", {}), dict) else {}
    show_info = config_bool(cfg.get("show_info"), True)
    show_network = config_bool(cfg.get("show_network"), True)
    show_public_network = config_bool(cfg.get("show_public_network"), False)
    show_vpn = config_bool(cfg.get("show_vpn"), True)
    vpn_label = str(cfg.get("vpn_label", "") or "").strip()
    show_updates = config_bool(cfg.get("show_updates"), True)
    labels = {
        "kernel": "Kernel",
        "graphics_driver": "GPU driver" if english else "GPU-Treiber",
        "graphics_model": "GPU" if english else "Grafikkarte",
        "cpu": "CPU",
        "memory": "Memory" if english else "RAM",
        "desktop": "Desktop",
        "session": "Session" if english else "Sitzung",
        "boot": "Boot" if english else "Start",
        "uptime": "Uptime" if english else "Laufzeit",
        "updates": "Updates",
        "hostname": "Host",
        "interface": "Interface",
        "lan_ip": "LAN IP",
        "gateway": "Gateway",
        "dns": "DNS",
        "public_ip": "Public IP" if english else "Öffentliche IP",
        "isp": "ISP",
        "public_location": "WAN location" if english else "WAN-Ort",
        "vpn": "VPN",
    }

    boot_time, uptime = format_boot_time(english)
    gpu_driver, gpu_model = graphics_info()
    items: list[dict[str, str]] = []

    if show_info:
        items.extend([
            {"key": "kernel", "label": labels["kernel"], "value": platform.uname().release or "--"},
            {"key": "graphics_driver", "label": labels["graphics_driver"], "value": gpu_driver},
            {"key": "graphics_model", "label": labels["graphics_model"], "value": gpu_model},
            {"key": "cpu", "label": labels["cpu"], "value": cpu_model()},
            {"key": "memory", "label": labels["memory"], "value": memory_total()},
            {"key": "desktop", "label": labels["desktop"], "value": desktop_version()},
            {"key": "session", "label": labels["session"], "value": current_session_type()},
            {"key": "boot", "label": labels["boot"], "value": boot_time},
            {"key": "uptime", "label": labels["uptime"], "value": uptime},
        ])

    if show_network:
        for item in local_network_info():
            key = item.get("key", "")
            if key in labels:
                item["label"] = labels[key]
            items.append(item)

    if show_public_network:
        for item in public_network_info():
            key = item.get("key", "")
            if key in labels:
                item["label"] = labels[key]
            items.append(item)

    if show_vpn:
        item = vpn_status_item(vpn_label, english)
        key = item.get("key", "")
        if key in labels:
            item["label"] = labels[key]
        items.append(item)

    if show_updates:
        updates, source = updates_available()
        item = {"key": "updates", "label": labels["updates"], "value": updates}
        if source:
            item["source"] = source
        items.append(item)

    return {
        "updated": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        "items": items,
        "errors": [],
        "enabled": True,
    }

def load_old() -> dict:
    if not CACHE.exists():
        return {"feeds": []}

    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except Exception:
        return {"feeds": []}

def old_items(old: dict, feed_name: str, feed_url: str = "") -> list[dict[str, str]]:
    """Previously cached headlines for one feed.

    Matching on the display name alone was wrong: two feeds may share a name,
    and editing an existing feed's URL would make the old source's headlines
    reappear under the new one. An exact (name, url) match wins; a name-only
    match is accepted solely when no URL was recorded, which is the case for
    caches written before v2.1.1.
    """
    url = str(feed_url or "").strip()
    fallback: list | None = None
    for feed in old.get("feeds", []):
        if not isinstance(feed, dict) or feed.get("name") != feed_name:
            continue
        stored_url = str(feed.get("url", "") or "").strip()
        if url and stored_url == url:
            return feed.get("items", [])
        if not stored_url and fallback is None:
            fallback = feed.get("items", [])
    return fallback if fallback is not None else []

def block_enabled(config: dict, key: str) -> bool:
    blocks = config.get("blocks", {})
    if not isinstance(blocks, dict):
        return True
    return blocks.get(key, True) is not False

def empty_block(name: str) -> dict:
    return {
        "updated": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        "items": [],
        "errors": [],
        "enabled": False,
        "location": name,
    }

def existing_block(old: dict, key: str, name: str) -> dict:
    block = old.get(key) if isinstance(old, dict) else None
    if isinstance(block, dict):
        return block
    return empty_block(name)

def build_cache(config: dict | None = None) -> dict:
    if config is None:
        ensure_config()
        config = load_config()
    old = load_old()
    plan = refresh_plan(config, old)
    forced_blocks = forced_refresh_blocks()
    refresh_main = bool(plan.get("main"))
    refresh_system = bool(plan.get("system"))
    refresh_weather = refresh_main or "weather" in forced_blocks
    refresh_markets = refresh_main or "markets" in forced_blocks
    refresh_news = refresh_main or "news" in forced_blocks
    refresh_system_block = refresh_system or "system" in forced_blocks
    now_ts = float(plan.get("now", time.time()))

    feeds = old.get("feeds", []) if isinstance(old.get("feeds", []), list) else []
    errors = old.get("errors", []) if isinstance(old.get("errors", []), list) else []

    news_status = old.get("news_status", {}) if isinstance(old.get("news_status", {}), dict) else {}

    if block_enabled(config, "news") and refresh_news:
        feeds, errors, news_status = fetch_all_feeds(config, old, ui_language(config))
    elif not block_enabled(config, "news"):
        feeds = []
        errors = []
        news_status = {}

    data = {
        "updated": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        "language": ui_language(config),
        "nina": fetch_nina(old, config) if block_enabled(config, "nina") and refresh_main else (existing_block(old, "nina", "Warnmeldungen") if block_enabled(config, "nina") else empty_block("Warnmeldungen")),
        "weather": fetch_weather(old, config) if block_enabled(config, "weather") and refresh_weather else (existing_block(old, "weather", "Wetter") if block_enabled(config, "weather") else empty_block("Wetter")),
        "prayer": fetch_prayer(old, config) if block_enabled(config, "prayer") and refresh_main else (existing_block(old, "prayer", "Islamische Gebetszeiten") if block_enabled(config, "prayer") else empty_block("Islamische Gebetszeiten")),
        "markets": fetch_markets(old, config) if block_enabled(config, "markets") and refresh_markets else (existing_block(old, "markets", "Märkte") if block_enabled(config, "markets") else empty_block("Märkte")),
        "system": fetch_system_info(old, config) if block_enabled(config, "system") and refresh_system_block else (existing_block(old, "system", "System") if block_enabled(config, "system") else empty_block("System")),
        "feeds": feeds,
        "errors": errors,
        "news_status": news_status,
        "blocks": {
            "weather": block_enabled(config, "weather"),
            "prayer": block_enabled(config, "prayer"),
            "nina": block_enabled(config, "nina"),
            "markets": block_enabled(config, "markets"),
            "system": block_enabled(config, "system"),
            "news": block_enabled(config, "news"),
        },
        "_refresh": {
            "main": now_ts if refresh_main else (old.get("_refresh", {}) or {}).get("main", cache_timestamp_fallback()),
            "system": now_ts if refresh_system_block else (old.get("_refresh", {}) or {}).get("system", cache_timestamp_fallback()),
            "version": "2.1.7",
            "main_interval_minutes": clamp_int(config.get("fetch_interval_minutes", 10), 10, 1, 1440),
            "system_interval_minutes": clamp_int(config.get("system_interval_minutes", 3), 3, 1, 1440),
        },
    }

    tmp = CACHE.with_name(f"{CACHE.name}.tmp.{os.getpid()}.{time.time_ns()}")
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        _restrict(tmp, 0o600)
        tmp.replace(CACHE)
    except BaseException:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass
        except Exception:
            pass
        raise

    return data


def acquire_cache_lock():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    lock_path = OUT_DIR / ".refresh.lock"
    handle = lock_path.open("w", encoding="utf-8")
    _restrict(lock_path, 0o600)
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    handle.write(f"{os.getpid()}\n")
    handle.flush()
    return handle

if __name__ == "__main__":
    lock_handle = acquire_cache_lock()
    if lock_handle is None:
        # Another cache process (usually the systemd timer) is mid-refresh.
        raise SystemExit(EXIT_LOCK_BUSY)
    try:
        ensure_config()
        config = load_config()

        if cache_is_fresh(config):
            raise SystemExit(0)

        build_cache(config)
    finally:
        lock_handle.close()
