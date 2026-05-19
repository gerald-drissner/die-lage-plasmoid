#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone, timedelta
try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None
import copy
import csv
import fcntl
import getpass
import html
import os
import io
import json
import platform
import shutil
import subprocess
import re
import sys
import time
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

CONFIG = BASE_CONFIG_DIR / "config.json"
CACHE = OUT_DIR / "rss.json"

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
 'nina_codes': [{'source': 'nina', 'name': 'Berlin', 'code': '110000000000'}],
 'prayer': {'city': 'Berlin', 'country': 'Germany', 'method': 3},
 'markets': {'currencies': ['USD', 'GBP', 'CHF'],
             'indices': [{'name': 'Dow Jones', 'symbol': '^DJI'},
                         {'name': 'DAX', 'symbol': '^GDAXI'},
                         {'name': 'Nikkei 225', 'symbol': '^N225'}],
             'twelve_data_api_key': '',
             'finnhub_api_key': '',
             'provider_mode': 'auto',
             'show_currencies': True,
             'show_indices': True,
             'show_stocks': True,
             'stocks': []},
 'fetch_interval_minutes': 10,
 'local_server_port': 8765,
 'boot_refresh_enabled': True,
 'boot_refresh_delay_seconds': 120,
 'system': {'show_info': True,
            'show_network': True,
            'show_public_network': False,
            'show_vpn': True,
            'vpn_label': '',
            'show_updates': True},
 'ui': {'font_size': 16,
        'highlight_color': '',
        'desktop_background_mode': 'default',
        'desktop_background_color': '',
        'news_font_family': '',
        'news_font_size': 16,
        'news_font_size_offset': 0,
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
 'blocks': {'weather': True, 'prayer': True, 'nina': True, 'markets': True, 'system': True, 'news': True},
 'block_order': ['nina', 'weather', 'prayer', 'system', 'markets', 'news'],
 'collapsed_blocks': {'nina': False,
                      'weather': False,
                      'prayer': False,
                      'markets': False,
                      'news': False,
                      'system': False}}

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

UA = "DieLage/2.0.11 (+https://github.com/gerald-drissner/die-lage-plasmoid)"
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

def ui_language(config: dict) -> str:
    ui = config.get("ui", {}) if isinstance(config.get("ui", {}), dict) else {}
    lang = str(ui.get("language", "de") or "de").strip().lower()
    return "en" if lang.startswith("en") else "de"

def is_english(config: dict) -> bool:
    return ui_language(config) == "en"

def atomic_write_json(path: Path, data: dict) -> None:
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

def cache_is_fresh(config: dict) -> bool:
    if "--force" in sys.argv:
        return False

    if not CACHE.exists():
        return False

    minutes = clamp_int(config.get("fetch_interval_minutes", 10), 10, 1, 1440)

    try:
        age = time.time() - CACHE.stat().st_mtime
    except Exception:
        return False

    return age < minutes * 60

def load_config() -> dict:
    ensure_config()
    try:
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("config is not a JSON object")
    except Exception:
        data = {}

    data.setdefault("feeds", copy.deepcopy(DEFAULT_CONFIG["feeds"]))
    data.setdefault("weather_locations", copy.deepcopy(DEFAULT_CONFIG["weather_locations"]))
    data.setdefault("nina_codes", copy.deepcopy(DEFAULT_CONFIG["nina_codes"]))
    data.setdefault("prayer", copy.deepcopy(DEFAULT_CONFIG["prayer"]))
    data.setdefault("system", copy.deepcopy(DEFAULT_CONFIG["system"]))
    data.setdefault("fetch_interval_minutes", DEFAULT_CONFIG["fetch_interval_minutes"])
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

def first_child_text(item: ET.Element, wanted: str) -> str:
    wanted = wanted.lower()
    for child in list(item):
        if local_name(str(child.tag)) == wanted and child.text:
            return clean(child.text)
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

def urlopen_text(url: str, timeout: int = 15, max_bytes: int = 1_500_000, retries: int = 1, headers: dict[str, str] | None = None) -> str:
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
    }
    if headers:
        request_headers.update({str(k): str(v) for k, v in headers.items() if v is not None})

    req = urllib.request.Request(
        url,
        headers=request_headers,
    )

    last_exc = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read(max_bytes)
                charset = response.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, "replace")
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if 400 <= exc.code < 500:
                raise
        except Exception as exc:
            last_exc = exc

        if attempt < retries:
            time.sleep(2)

    if last_exc:
        raise last_exc
    raise RuntimeError("request failed")

def fetch_feed(url: str, limit: int) -> list[dict[str, str]]:
    data = urlopen_text(url)
    root = safe_xml_fromstring(data)

    entries = []
    for item in all_items(root):
        title = item_title(item)
        if not title:
            continue

        entries.append({
            "title": title,
            "link": item_link(item),
        })

        if len(entries) >= limit:
            break

    return entries

def fetch_weather_one(name: str, lat: float, lon: float, language: str = "de") -> dict[str, str]:
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
    snow_text = fmt_optional_nonzero_number(snow, " mm")
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
    }

def fetch_weather(old: dict, config: dict) -> dict:
    old_weather = old.get("weather", {})
    items = []
    errors = []

    language = ui_language(config)

    weather_entries = config.get("weather_locations", [])
    if not weather_entries:
        return {
            "updated": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            "items": [],
            "errors": [],
        }

    for entry in weather_entries:
        try:
            items.append(fetch_weather_one(entry["name"], float(entry["lat"]), float(entry["lon"]), language))
        except Exception as exc:
            errors.append(f"{entry.get('name', 'Ort')}: {type(exc).__name__}")

    if not items:
        items = old_weather.get("items", [])

    return {
        "updated": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        "items": items,
        "errors": errors,
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

def fmt_epoch(value) -> str:
    try:
        return datetime.fromtimestamp(int(value)).strftime("%Y-%m-%d %H:%M")
    except Exception:
        return ""

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

    items = []
    for warning in warnings:
        wprops = warning.get("properties", {}) if isinstance(warning, dict) else {}
        raw = wprops.get("rawinfo", {}) if isinstance(wprops.get("rawinfo"), dict) else {}
        warn_type = geosphere_type_name(wprops.get("warntypid") or raw.get("warntypid"), language)
        level = geosphere_level_name(wprops.get("warnstufeid") or raw.get("warnstufeid"), language)
        severity = geosphere_severity(wprops.get("warnstufeid") or raw.get("warnstufeid"))
        headline = raw.get("headline") or raw.get("event") or raw.get("title") or ""
        title = headline or (f"{level} {warn_type}" if level else warn_type)
        description = raw.get("description") or raw.get("text") or raw.get("kurztext") or raw.get("langtext") or ""
        start = fmt_epoch(raw.get("start") or wprops.get("start"))
        end = fmt_epoch(raw.get("end") or raw.get("expires") or wprops.get("end"))
        details = " · ".join(x for x in (label, "GeoSphere", location, level, warn_type, (("until " if language == "en" else "bis ") + end if end else "")) if x)
        candidate = {
            "title": clean(title, 220),
            "details": clean(details, 260),
            "severity": severity,
            "link": "https://warnungen.zamg.at/",
            "_filter_text": " ".join(str(x) for x in (title, description, details, location, level, warn_type, start, end) if x),
        }
        if warning_matches_filters(candidate, include, exclude):
            candidate.pop("_filter_text", None)
            items.append(candidate)
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

def fetch_nina(old: dict, config: dict) -> dict:
    old_nina = old.get("nina", {})
    errors = []
    all_items: list[dict[str, str]] = []
    locations: list[str] = []
    seen_keys: set[str] = set()

    language = ui_language(config)
    warning_entries = config.get("nina_codes", [])

    if not warning_entries:
        return {
            "location": "",
            "updated": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            "items": [],
            "errors": [],
        }

    for entry in warning_entries:
        label = str(entry.get("name", "Gebiet")).strip() or "Gebiet"

        try:
            items = fetch_warning_entry(entry, language)
            locations.append(label)
            for item in items:
                # Deduplicate broad warnings that appear for multiple configured areas.
                dedup_key = "|".join([
                    str(item.get("title", "")).strip(),
                    str(item.get("details", "")).strip(),
                    str(item.get("severity", "")).strip(),
                ])
                if dedup_key and dedup_key not in seen_keys:
                    seen_keys.add(dedup_key)
                    all_items.append(item)
        except Exception as exc:
            errors.append(f"{label}: {type(exc).__name__}: {str(exc)[:80]}")

    if locations:
        return {
            "location": ", ".join(locations),
            "updated": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            "items": all_items,
            "errors": errors,
        }

    return {
        "location": old_nina.get("location", "Gebiet"),
        "updated": old_nina.get("updated", ""),
        "items": old_nina.get("items", []),
        "errors": errors,
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
        }
    except Exception as exc:
        return {
            "location": old_prayer.get("location", f"{city}, {country}"),
            "method": old_prayer.get("method", method),
            "updated": old_prayer.get("updated", ""),
            "hijri": old_prayer.get("hijri", ""),
            "items": old_prayer.get("items", []),
            "errors": [type(exc).__name__],
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

def format_timestamp(ts, tz_name: str | None = None) -> tuple[str, str]:
    date_value, time_value, _tz_abbr = format_market_timestamp(ts, tz_name)
    return date_value, time_value

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

        pattern = re.compile(
            re.escape(stooq_symbol)
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
    old_markets = old.get("markets", {})
    market_config = config.get("markets", {}) if isinstance(config.get("markets", {}), dict) else {}

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
        except Exception as exc:
            exchange = old_markets.get("exchange", {"items": [], "source": "Frankfurter / EZB"})
            if not exchange.get("items"):
                exchange = {"items": [], "source": "Frankfurter / EZB"}
            errors.append(f"Wechselkurse: {type(exc).__name__}: {str(exc)[:140]}")
    else:
        exchange = {"items": [], "source": "Frankfurter / EZB", "date": "", "previous_date": ""}

    if show_indices and indices:
        try:
            index_data = fetch_indices(indices, twelve_data_api_key, finnhub_api_key, provider_mode)
            if index_data.get("errors"):
                errors.extend([f"Indizes: {err}" for err in index_data.get("errors", [])])
            if not index_data.get("items") and old_markets.get("indices", {}).get("items"):
                index_data = old_markets.get("indices", {"items": [], "source": "Yahoo Finance"})
                errors.append("Indizes: alte Cache-Daten verwendet")
        except Exception as exc:
            index_data = old_markets.get("indices", {"items": [], "source": "Yahoo Finance"})
            if not index_data.get("items"):
                index_data = {"items": [], "source": "Yahoo Finance"}
            errors.append(f"Indizes: {type(exc).__name__}: {str(exc)[:140]}")
    else:
        index_data = {"items": [], "source": "Yahoo Finance"}

    if show_stocks and stocks:
        try:
            stock_data = fetch_stocks(stocks, twelve_data_api_key, finnhub_api_key, provider_mode)
            if stock_data.get("errors"):
                errors.extend([f"Aktien: {err}" for err in stock_data.get("errors", [])])
            if not stock_data.get("items") and old_markets.get("stocks", {}).get("items"):
                stock_data = old_markets.get("stocks", {"items": [], "source": "Yahoo Finance"})
                errors.append("Aktien: alte Cache-Daten verwendet")
        except Exception as exc:
            stock_data = old_markets.get("stocks", {"items": [], "source": "Yahoo Finance"})
            if not stock_data.get("items"):
                stock_data = {"items": [], "source": "Yahoo Finance"}
            errors.append(f"Aktien: {type(exc).__name__}: {str(exc)[:140]}")
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


def updates_available() -> tuple[str, str]:
    """Return the number of package updates and the command used.

    On Arch/CachyOS, `checkupdates` is the reliable source because it refreshes
    a temporary sync database without touching the real pacman database.  The
    older `pacman -Qu` fallback can legitimately report 0 when the real sync DB
    is stale, so we only use that zero-count result when checkupdates is not
    installed at all.  This avoids showing a misleading 0 on systems where the
    update notifier knows about pending updates.
    """
    checkupdates_path = resolve_command("checkupdates")
    if checkupdates_path:
        env = {
            **SAFE_SUBPROCESS_ENV,
            "LC_ALL": "C",
            "LANG": "C",
            "CHECKUPDATES_DB": str(OUT_DIR / "checkupdates-db"),
        }
        proc = run_process(["checkupdates"], timeout=35, env=env)
        if proc is not None:
            lines = _nonempty_lines(proc.stdout or "")
            if lines:
                return str(len(lines)), "checkupdates"
            if proc.returncode in (0, 2):
                return "0", "checkupdates"

            # If checkupdates failed, do not silently turn that into a false
            # zero via pacman -Qu.  We still allow a non-zero pacman fallback
            # below, but otherwise report unknown.
            pacman_proc = run_process(["pacman", "-Qu"], timeout=12, env={**SAFE_SUBPROCESS_ENV, "LC_ALL": "C", "LANG": "C"})
            if pacman_proc is not None:
                pacman_lines = _nonempty_lines(pacman_proc.stdout or "")
                if pacman_lines:
                    return str(len(pacman_lines)), "pacman -Qu"
            return "--", "checkupdates failed"

    # Arch/CachyOS fallback when pacman-contrib/checkupdates is not installed.
    proc = run_process(["pacman", "-Qu"], timeout=12, env={**SAFE_SUBPROCESS_ENV, "LC_ALL": "C", "LANG": "C"})
    if proc is not None and proc.returncode in (0, 1):
        lines = _nonempty_lines(proc.stdout or "")
        return str(len(lines)), "pacman -Qu"

    # apt list --upgradable is localized. Force the C locale so the filter
    # word "upgradable" actually appears, otherwise a German Ubuntu shows 0.
    proc = run_process(["apt", "list", "--upgradable"], timeout=18, env={**SAFE_SUBPROCESS_ENV, "LC_ALL": "C", "LANG": "C"})
    if proc is not None and proc.returncode == 0:
        lines = [line for line in _nonempty_lines(proc.stdout or "") if "/" in line and "upgradable" in line]
        return str(len(lines)), "apt"

    # Fedora / RHEL / openSUSE-RPM family. dnf check-update exits 100 when
    # updates are available, 0 when none.  --cacheonly avoids heavy metadata
    # refreshes, so the result follows the locally cached metadata freshness.
    proc = run_process(["dnf", "-q", "--cacheonly", "check-update"], timeout=25, env={**SAFE_SUBPROCESS_ENV, "LC_ALL": "C", "LANG": "C"})
    if proc is not None and proc.returncode in (0, 100):
        lines = []
        for line in _nonempty_lines(proc.stdout or ""):
            if line.startswith(("Obsoleting", "Last metadata", "Security")):
                continue
            parts = line.split()
            if len(parts) >= 3 and "/" not in parts[0]:
                lines.append(line)
        return str(len(lines)), "dnf"

    # openSUSE / SUSE: zypper. `--non-interactive list-updates` returns status
    # 0 when nothing changes too, and the data rows start with "v |".
    proc = run_process(["zypper", "--non-interactive", "-q", "list-updates"], timeout=25, env={**SAFE_SUBPROCESS_ENV, "LC_ALL": "C", "LANG": "C"})
    if proc is not None and proc.returncode == 0:
        lines = [line for line in _nonempty_lines(proc.stdout or "") if line.startswith("v |") or line.startswith("v  |")]
        return str(len(lines)), "zypper"

    return "--", ""


def first_ipv4(value: str) -> str:
    match = re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", value or "")
    return match.group(0) if match else ""



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
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
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

def old_items(old: dict, feed_name: str) -> list[dict[str, str]]:
    for feed in old.get("feeds", []):
        if feed.get("name") == feed_name:
            return feed.get("items", [])
    return []

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

def build_cache(config: dict | None = None) -> dict:
    if config is None:
        ensure_config()
        config = load_config()
    old = load_old()

    feeds = []
    errors = []

    if block_enabled(config, "news"):
        for feed in config.get("feeds", []):
            name = feed.get("name", "Feed")
            url = feed.get("url", "")
            try:
                limit = int(feed.get("limit", 5) or 5)
            except Exception:
                limit = 5

            try:
                items = fetch_feed(url, limit)
                if not items:
                    raise RuntimeError("no items found")
            except Exception as exc:
                items = old_items(old, name)
                errors.append(f"{name}: {type(exc).__name__}")

            feeds.append({
                "name": name,
                "url": url,
                "items": items,
            })

    data = {
        "updated": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        "language": ui_language(config),
        "nina": fetch_nina(old, config) if block_enabled(config, "nina") else empty_block("Warnmeldungen"),
        "weather": fetch_weather(old, config) if block_enabled(config, "weather") else empty_block("Wetter"),
        "prayer": fetch_prayer(old, config) if block_enabled(config, "prayer") else empty_block("Islamische Gebetszeiten"),
        "markets": fetch_markets(old, config) if block_enabled(config, "markets") else empty_block("Märkte"),
        "system": fetch_system_info(old, config) if block_enabled(config, "system") else empty_block("System"),
        "feeds": feeds,
        "errors": errors,
        "blocks": {
            "weather": block_enabled(config, "weather"),
            "prayer": block_enabled(config, "prayer"),
            "nina": block_enabled(config, "nina"),
            "markets": block_enabled(config, "markets"),
            "system": block_enabled(config, "system"),
            "news": block_enabled(config, "news"),
        },
    }

    tmp = CACHE.with_name(f"{CACHE.name}.tmp.{os.getpid()}.{time.time_ns()}")
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
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
        raise SystemExit(0)
    try:
        ensure_config()
        config = load_config()

        if cache_is_fresh(config):
            raise SystemExit(0)

        build_cache(config)
    finally:
        lock_handle.close()
