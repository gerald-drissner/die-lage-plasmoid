#!/usr/bin/env python3
"""Behavioural regression tests for Die Lage.

Every test here corresponds to a bug that shipped at least once. The release
check runs this file; a green run means these specific failures cannot come
back silently. Requires no network: an in-process HTTP server stands in for
the publishers.
"""
from __future__ import annotations

import gzip
import importlib.util
import inspect
import json
import os
import pathlib
import shutil
import socket
import ssl
import sys
import tempfile
import threading
import time
import urllib.error
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path(__file__).resolve().parent.parent
FAILURES: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"    ok   {name}")
    else:
        print(f"    FAIL {name} {detail}")
        FAILURES.append(name)


def load_cache_module(home: pathlib.Path, argv: list[str] | None = None):
    os.environ["HOME"] = str(home)
    (home / ".config/die-lage").mkdir(parents=True, exist_ok=True)
    (home / ".cache/die-lage").mkdir(parents=True, exist_ok=True)
    shutil.copy(ROOT / "files/config/default-config.json", home / ".config/die-lage/default-config.json")
    sys.argv = argv or ["dielage-cache.py"]
    spec = importlib.util.spec_from_file_location("dlc_test", ROOT / "files/bin/dielage-cache.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FEED = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>T</title>
<item><title>Erste Meldung</title><link>https://e.org/1</link><guid>g1</guid>
<pubDate>Wed, 27 Aug 2026 09:14:00 +0200</pubDate></item>
</channel></rss>"""

ATOM = b"""<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>A</title>
<entry><title>Atom Eintrag</title><link href="https://a.org/1"/><id>a1</id>
<updated>2026-08-27T07:00:00Z</updated></entry></feed>"""

LATIN = ('<?xml version="1.0" encoding="ISO-8859-1"?><rss version="2.0"><channel>'
         '<item><title>Gr\u00fc\u00dfe aus M\u00fcnchen</title><link>http://x/1</link></item>'
         '</channel></rss>').encode("iso-8859-1")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body=b"", headers=None):
        self.send_response(code)
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if body:
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                # Oversize/bomb tests deliberately make the client stop reading
                # early; a reset is the expected server-side consequence.
                pass

    def do_GET(self):
        if self.path == "/gzip":
            self._send(200, gzip.compress(FEED), {"Content-Encoding": "gzip", "ETag": '"v1"'})
        elif self.path == "/cond":
            if self.headers.get("If-None-Match") == '"v1"':
                self._send(304)
            else:
                self._send(200, FEED, {"ETag": '"v1"'})
        elif self.path == "/atom":
            self._send(200, ATOM)
        elif self.path == "/latin":
            self._send(200, LATIN, {"Content-Type": "text/xml"})
        elif self.path == "/403":
            self._send(403)
        elif self.path == "/429":
            self._send(429)
        elif self.path == "/big":
            self._send(200, b"x" * 3_000_000)
        elif self.path == "/bomb":
            self._send(200, gzip.compress(b"A" * 60_000_000), {"Content-Encoding": "gzip"})
        else:
            self._send(404)


def main() -> int:
    home = pathlib.Path(tempfile.mkdtemp())
    m = load_cache_module(home)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    base = f"http://127.0.0.1:{server.server_address[1]}"
    threading.Thread(target=server.serve_forever, daemon=True).start()

    print("  [language selection]")
    saved_locale = {k: os.environ.get(k) for k in ("LC_ALL", "LC_MESSAGES", "LANG")}
    try:
        os.environ.pop("LC_ALL", None)
        os.environ.pop("LC_MESSAGES", None)
        os.environ["LANG"] = "de_DE.UTF-8"
        check("automatic language follows German locale", m.ui_language({"ui": {"language": "auto"}}) == "de")
        os.environ["LANG"] = "en_US.UTF-8"
        check("automatic language falls back to English for non-German locale", m.ui_language({"ui": {"language": "auto"}}) == "en")
        check("manual German overrides system locale", m.ui_language({"ui": {"language": "de"}}) == "de")
        check("manual English overrides system locale", m.ui_language({"ui": {"language": "en"}}) == "en")
    finally:
        for key, value in saved_locale.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    print("  [transport]")
    items, meta = m.fetch_feed(base + "/gzip", 5)
    check("gzip response decoded", items and items[0]["title"] == "Erste Meldung")
    check("pubDate parsed to epoch", items[0].get("published") == 1787814840)
    check("guid captured as id", items[0].get("id") == "g1")

    _, meta = m.fetch_feed(base + "/cond", 5)
    try:
        m.fetch_feed(base + "/cond", 5, etag=meta["etag"])
        check("conditional GET yields NotModified", False)
    except m.NotModified:
        check("conditional GET yields NotModified", True)

    check("atom feed parsed", m.fetch_feed(base + "/atom", 5)[0][0]["title"] == "Atom Eintrag")
    check("charset sniffed from XML declaration",
          m.fetch_feed(base + "/latin", 5)[0][0]["title"] == "Gr\u00fc\u00dfe aus M\u00fcnchen")

    try:
        m.urlopen_full(base + "/big", max_bytes=1_000_000, retries=0)
        check("oversized body rejected", False)
    except m.OversizeResponse:
        check("oversized body rejected", True)

    try:
        m.urlopen_full(base + "/bomb", max_bytes=1_500_000, retries=0)
        check("decompression bomb rejected", False)
    except m.OversizeResponse:
        check("decompression bomb rejected", True)

    print("  [error classification]")
    for code, kind in ((403, "blocked"), (429, "rate_limited"), (451, "geo_blocked"),
                       (404, "not_found"), (503, "server_error")):
        got = m.classify_error(urllib.error.HTTPError("u", code, "", {}, None))["kind"]
        check(f"HTTP {code} -> {kind}", got == kind, f"got {got}")
    for exc, kind in ((urllib.error.URLError(socket.gaierror(-2, "Name or service not known")), "dns"),
                      (urllib.error.URLError(ssl.SSLCertVerificationError("bad")), "tls"),
                      (ConnectionError("Network is unreachable"), "offline"),
                      (TimeoutError("timed out"), "timeout")):
        got = m.classify_error(exc)["kind"]
        check(f"{type(exc).__name__} -> {kind}", got == kind, f"got {got}")
    check("no cause falls back to 'unknown' text",
          all(de and en for de, en in m.ERROR_TEXTS.values()))

    print("  [news status]")
    m._VPN_NAME_CACHE = ["Mullvad"]
    minority = m.build_news_status(0, ["blocked", "blocked", "dns", "dns", "dns"], "de")
    check("2 of 5 filtered is NOT called a majority", "Exit-Adresse" not in minority["hint"])
    majority = m.build_news_status(0, ["blocked", "blocked", "blocked", "dns"], "de")
    check("3 of 4 filtered names the exit address", "Exit-Adresse" in majority["hint"])
    check("VPN wording stays conditional", "Falls" in majority["hint"])
    check("healthy fetch produces no summary", m.build_news_status(5, [], "de")["summary"] == "")

    print("  [feed bookkeeping]")
    old = {"feeds": [{"name": "F", "url": "https://alt/rss", "items": [{"title": "alt"}]}]}
    check("changed URL does not inherit old headlines", m.old_items(old, "F", "https://neu/rss") == [])
    check("same URL still reuses headlines", m.old_items(old, "F", "https://alt/rss") != [])
    for argv, want in ((["x", "--force"], True), (["x", "--block", "news"], True),
                       (["x", "--block=news"], True), (["x"], False)):
        sys.argv = argv
        check(f"manual_refresh({argv[1:]}) == {want}", m.manual_refresh() == want)
    sys.argv = ["x"]
    check("lock conflict uses a distinct exit code", m.EXIT_LOCK_BUSY == 75)

    print("  [weather cache identity]")
    old_weather = {"weather": {"items": [{"name": "Berlin", "latitude": 52.52, "longitude": 13.405,
                                            "temperature": 12, "last_ok": int(time.time()) - 600}]}}
    original_weather_one = m.fetch_weather_one
    m.fetch_weather_one = lambda *a, **k: (_ for _ in ()).throw(ConnectionError("down"))
    same_cfg = {"ui": {"language": "de"}, "weather_locations": [
        {"name": "Berlin", "lat": 52.52, "lon": 13.405}]}
    moved_cfg = {"ui": {"language": "de"}, "weather_locations": [
        {"name": "Berlin", "lat": 30.0444, "lon": 31.2357}]}
    same_weather = m.fetch_weather(old_weather, same_cfg)
    moved_weather = m.fetch_weather(old_weather, moved_cfg)
    check("same name + same coordinates reuses cached weather",
          len(same_weather["items"]) == 1 and same_weather["items"][0].get("stale") is True)
    check("same name + changed coordinates never inherits old weather", moved_weather["items"] == [])
    legacy_weather = {"weather": {"items": [{"name": "Berlin", "temperature": 12}]}}
    check("legacy name-only cache is not reused unsafely",
          m.fetch_weather(legacy_weather, same_cfg)["items"] == [])
    m.fetch_weather_one = original_weather_one

    print("  [parallel worker fail-closed paths]")
    feed_src = inspect.getsource(m.fetch_all_feeds)
    weather_src = inspect.getsource(m.fetch_weather)
    check("unexpected feed worker errors cannot silently drop a configured feed",
          "futures = {" in feed_src and "results[original_index]" in feed_src and
          "except Exception:\n                    continue" not in feed_src)
    check("unexpected weather worker errors cannot silently drop a configured place",
          "futures = {" in weather_src and "weather_failure_payload(entry, exc)" in weather_src and
          "except Exception:\n                    continue" not in weather_src)

    print("  [market partial-cache continuity]")
    old_exchange = {"items": [
        {"base": "EUR", "target": "USD", "value": "1.1"},
        {"base": "USD", "target": "EUR", "value": "0.9"},
        {"base": "EUR", "target": "GBP", "value": "0.8"},
        {"base": "GBP", "target": "EUR", "value": "1.2"},
    ]}
    cached_fx = m.cached_exchange_for(old_exchange, ["USD", "GBP"], english=True)
    fresh_fx = {"items": [{"base": "EUR", "target": "USD", "value": "1.2"}]}
    added_fx = m.merge_cached_exchange(fresh_fx, cached_fx)
    check("partial FX response is supplemented from exact configured cache",
          added_fx == 3 and len(fresh_fx["items"]) == 4 and
          all(x.get("stale") is True for x in fresh_fx["items"][1:]))

    old_indices = {"items": [
        {"name": "DAX", "symbol": "^GDAXI", "value": "26000"},
        {"name": "Nikkei", "symbol": "^N225", "value": "66000"},
        {"name": "Removed", "symbol": "^DJI", "value": "53000"},
    ]}
    configured_indices = [{"name": "DAX", "symbol": "^GDAXI"}, {"name": "Nikkei 225", "symbol": "^N225"}]
    cached_idx = m.cached_instruments_for(old_indices, configured_indices, "index")
    fresh_idx = {"items": [{"name": "DAX", "symbol": "^GDAXI", "value": "26500"}]}
    added_idx = m.merge_cached_instruments(fresh_idx, cached_idx, "index")
    check("partial index response keeps only configured missing symbols from cache",
          added_idx == 1 and [x.get("symbol") for x in fresh_idx["items"]] == ["^GDAXI", "^N225"] and
          fresh_idx["items"][1].get("stale") is True)

    print("  [optional OpenWeather provider]")
    original_urlopen_text = m.urlopen_text
    now_epoch = 1787913240
    sample_current = {
        "dt": now_epoch, "timezone": 7200,
        "main": {"temp": 24.5, "humidity": 55, "feels_like": 25.1},
        "wind": {"speed": 3.0, "gust": 5.0},
        "weather": [{"description": "teilweise bewölkt"}],
        "sys": {"sunrise": now_epoch - 5 * 3600, "sunset": now_epoch + 8 * 3600},
    }
    sample_forecast = {
        "city": {"timezone": 7200},
        "list": [
            {"dt": now_epoch + 3600, "rain": {"3h": 1.2}},
            {"dt": now_epoch + 4 * 3600, "rain": {"3h": 0.5}},
        ],
    }
    seen_urls = []
    def fake_openweather(url, timeout=12, **kwargs):
        seen_urls.append(url)
        return json.dumps(sample_forecast if "/forecast?" in url else sample_current)
    m.urlopen_text = fake_openweather
    ow = m.fetch_weather_one("Berlin", 52.52, 13.405, "de", {"openweather_api_key": "secret"})
    check("OpenWeather key switches provider", ow.get("provider") == "openweather")
    check("OpenWeather uses current and 5-day forecast endpoints",
          any("api.openweathermap.org/data/2.5/weather?" in u for u in seen_urls) and
          any("api.openweathermap.org/data/2.5/forecast?" in u for u in seen_urls))
    check("OpenWeather values map to existing weather schema",
          ow.get("temperature") == 24.5 and abs(float(ow.get("wind_speed")) - 10.8) < 0.01 and
          "Regenprognose 1.7 mm" in ow.get("details", ""))
    m.urlopen_text = original_urlopen_text

    # A provider switch must not inherit cached values from the other source.
    m.fetch_weather_one = lambda *a, **k: (_ for _ in ()).throw(ConnectionError("down"))
    provider_cfg = {"ui": {"language": "de"}, "weather": {"openweather_api_key": "secret"},
                    "weather_locations": [{"name": "Berlin", "lat": 52.52, "lon": 13.405}]}
    check("provider switch does not reuse Open-Meteo cache", m.fetch_weather(old_weather, provider_cfg)["items"] == [])
    openweather_cache = {"weather": {"items": [{"name": "Berlin", "latitude": 52.52, "longitude": 13.405,
                                                   "provider": "openweather", "temperature": 24,
                                                   "last_ok": int(time.time()) - 7200}]}}
    check("same OpenWeather provider can reuse its own stale cache",
          len(m.fetch_weather(openweather_cache, provider_cfg)["items"]) == 1)
    m.fetch_weather_one = original_weather_one

    print("  [warnings must never fake an all-clear]")
    cfg = {"ui": {"language": "de"}, "nina_codes": [
        {"source": "nina", "name": "Berlin", "code": "110000000000"},
        {"source": "geosphere", "name": "Bludenz", "lat": "47.15", "lon": "9.82"}]}
    bludenz_key = m.nina_source_key(cfg["nina_codes"][1])
    old_nina = {"nina": {"sources": [{"key": bludenz_key, "label": "Bludenz", "ok": True,
                                      "last_ok": int(time.time()) - 5400,
                                      "items": [{"title": "Sturmwarnung", "details": "d", "severity": "moderate"}]}]}}
    m.fetch_warning_entry = lambda e, language="de": [] if e.get("name") == "Berlin" else (_ for _ in ()).throw(ConnectionError("down"))
    r = m.fetch_nina(old_nina, cfg)
    check("partial source failure marks block incomplete", r["complete"] is False)
    check("cached warning from failed source is retained", len(r["items"]) == 1)
    check("retained warning is flagged stale", r["items"][0].get("stale") is True)
    check("notice names the failed area", "Bludenz" in r["notice"])
    m.fetch_warning_entry = lambda e, language="de": []
    r2 = m.fetch_nina({}, cfg)
    check("all sources healthy still allows all-clear", r2["complete"] is True and r2["notice"] == "")

    print("  [stale marking]")
    check("prayer failure exposes stale flag",
          "stale" in m.fetch_prayer({"prayer": {"items": [{"name": "Fajr"}], "for_date": "2000-01-01"}},
                                    {"prayer": {"city": "", "country": ""}, "ui": {"language": "de"}}))

    print("  [permissions]")
    m.atomic_write_json(home / ".config/die-lage/config.json", {"markets": {"twelve_data_api_key": "k"}})
    mode = os.stat(home / ".config/die-lage/config.json").st_mode & 0o777
    check("config.json is not world-readable", mode == 0o600, f"mode {oct(mode)}")

    print("  [defaults]")
    canon = json.loads((ROOT / "files/config/default-config.json").read_text(encoding="utf-8"))
    spec = importlib.util.spec_from_file_location("dls_test", ROOT / "files/bin/dielage-server.py")
    srv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(srv)

    print("  [OpenWeather API-key check]")
    original_probe = srv._api_probe_json
    seen_probe_urls = []
    def fake_weather_probe(url, headers, max_bytes=300_000):
        seen_probe_urls.append(url)
        return {"main": {"temp": 19.5}, "name": "Berlin"}
    srv._api_probe_json = fake_weather_probe
    weather_check = srv.check_openweather_api("secret-key", 52.52, 13.405, "de")
    check("OpenWeather test accepts a working unsaved key",
          weather_check.get("ok") is True and "location" not in weather_check)
    check("OpenWeather test uses current-weather endpoint",
          any("api.openweathermap.org/data/2.5/weather?" in u and "appid=secret-key" in u for u in seen_probe_urls))
    check("OpenWeather test reports a missing key without network access",
          srv.check_openweather_api("", 52.52, 13.405).get("reason") == "missing")
    def unauthorized_probe(*a, **k):
        raise urllib.error.HTTPError("u", 401, "Unauthorized", {}, None)
    srv._api_probe_json = unauthorized_probe
    denied = srv.check_openweather_api("bad-key", 52.52, 13.405)
    check("OpenWeather HTTP 401 becomes invalid/inactive status",
          denied.get("ok") is False and denied.get("reason") == "unauthorized")
    def limited_probe(*a, **k):
        raise urllib.error.HTTPError("u", 429, "Too Many Requests", {}, None)
    srv._api_probe_json = limited_probe
    limited = srv.check_openweather_api("rate-key", 52.52, 13.405)
    check("OpenWeather HTTP 429 becomes rate-limit status",
          limited.get("ok") is False and limited.get("reason") == "rate_limited")
    srv._api_probe_json = original_probe

    server_cfg = home / ".config/die-lage/server-config.json"
    server_cfg.write_text("{}", encoding="utf-8")
    server_cfg.chmod(0o600)
    srv.atomic_write_json(server_cfg, {"markets": {"finnhub_api_key": "secret"}})
    server_mode = os.stat(server_cfg).st_mode & 0o777
    check("server config writer preserves 0600", server_mode == 0o600, f"mode {oct(server_mode)}")

    print("  [async refresh state]")
    original_run = srv.subprocess.run
    class Result:
        def __init__(self, returncode):
            self.returncode = returncode

    captured_refresh_args = []
    def run_refresh_with_code(code):
        def fake_run(args, *a, **k):
            captured_refresh_args.append(list(args))
            return Result(code)
        srv.subprocess.run = fake_run
        acquired = srv.REFRESH_LOCK.acquire(blocking=False)
        assert acquired, "test refresh lock unexpectedly busy"
        with srv.REFRESH_STATE_LOCK:
            srv.REFRESH_STATE.update({"running": True, "block": "news", "ok": True,
                                      "error": "", "already_running": False})
        srv._run_refresh_job("news")
        return srv._refresh_state_snapshot()

    failed_state = run_refresh_with_code(9)
    check("helper failure is retained in refresh status",
          failed_state["running"] is False and failed_state["ok"] is False and "9" in failed_state["error"])
    busy_state = run_refresh_with_code(srv.EXIT_LOCK_BUSY)
    check("external cache lock becomes already_running",
          busy_state["running"] is False and busy_state["already_running"] is True)
    check("block refresh invokes only the requested block without global --force",
          bool(captured_refresh_args) and captured_refresh_args[-1][-2:] == ["--block", "news"] and
          "--force" not in captured_refresh_args[-1])
    srv.subprocess.run = original_run

    acquired = srv.REFRESH_LOCK.acquire(blocking=False)
    assert acquired, "test refresh lock unexpectedly busy"
    try:
        duplicate = srv.start_refresh("weather")
    finally:
        srv.REFRESH_LOCK.release()
    check("second server refresh is rejected as already running",
          duplicate.get("started") is False and duplicate.get("already_running") is True)

    original_thread_start = srv.threading.Thread.start
    def fail_thread_start(self):
        raise RuntimeError("thread start failed")
    srv.threading.Thread.start = fail_thread_start
    start_failed = False
    try:
        try:
            srv.start_refresh("weather")
        except RuntimeError:
            start_failed = True
        lock_released = srv.REFRESH_LOCK.acquire(blocking=False)
        if lock_released:
            srv.REFRESH_LOCK.release()
        start_state = srv._refresh_state_snapshot()
    finally:
        srv.threading.Thread.start = original_thread_start
    check("thread-start failure releases refresh lock",
          start_failed and lock_released and start_state.get("running") is False and
          start_state.get("ok") is False and "could not start" in start_state.get("error", ""))

    print("  [QML async wiring]")
    qml = (ROOT / "files/plasmoid/contents/ui/main.qml").read_text(encoding="utf-8")
    check("QML has a single-flight refresh guard",
          "property bool refreshJobActive: false" in qml and
          "if (!root.canRefreshBlock(id) || root.refreshJobActive)" in qml and
          "if (root.refreshJobActive)" in qml)
    check("QML honours already_running status", "resp.already_running === true" in qml)
    check("QML honours failed background status", "resp.last_ok === false" in qml)
    check("cached warning marker is wired into delegate", "root.warningStaleText(n)" in qml)
    check("news source problem banner is collapsed behind a warning button",
          'id: newsStatusButton' in qml and
          'visible: Boolean(root.showNews && root.newsHasProblem() && root.newsStatusOpen)' in qml)
    check("headline age can be disabled in settings",
          'property bool showNewsAge: true' in qml and
          'visible: root.showNewsAge && text.length > 0' in qml and
          '"news_show_age": root.showNewsAge' in qml)
    check("headline age has a configurable continuous color scale",
          'property bool newsAgeColorEnabled: true' in qml and
          'property string newsAgeColorWindowMinutes: "120"' in qml and
          'function headlineAgeColor(entry)' in qml and
          'function headlineAgeOpacity(entry)' in qml and
          'color: root.headlineAgeColor(headline.entry)' in qml and
          '"news_age_color_minutes": root.newsAgeWindowMinutesValue()' in qml)
    check("headline age colors default to Plasma/widget theme colors",
          'root.newsAgeColorFromSetting(root.newsAgeRecentColor, root.appHighlightColor)' in qml and
          'root.newsAgeColorFromSetting(root.newsAgeOlderColor, Kirigami.Theme.textColor)' in qml)
    check("refresh controls keep a visible spinner while their job is active",
          qml.count('QQC2.BusyIndicator {') >= 5 and
          'running: topRefreshButton.busy' in qml and
          'running: weatherBlockRefreshButton.busy' in qml and
          'running: newsBlockRefreshButton.busy' in qml)
    check("OpenWeather key is wired through settings",
          'property string openWeatherApiKey: ""' in qml and
          '"openweather_api_key": String(root.openWeatherApiKey || "").trim()' in qml)
    check("OpenWeather key can be tested before saving",
          'function checkOpenWeatherApi()' in qml and
          'xhr.open("POST", root.baseUrl + "/check-weather-api")' in qml and
          'onClicked: root.checkOpenWeatherApi()' in qml)
    check("weather attribution is unobtrusive but remains visibly linked",
          'id: weatherSourceInfoButton' in qml and
          'id: weatherSourcePopup' in qml and
          "Weather data provided by OpenWeather" in qml and
          "https://openweathermap.org/" in qml and
          "Weather data by Open-Meteo.com" in qml and
          "https://open-meteo.com/" in qml and
          'opacity: 0.42' in qml)
    check("language selector offers automatic, German and English",
          'model: [root.t("languageAuto"), "Deutsch", "English"]' in qml and
          'function effectiveUiLanguage()' in qml)
    check("fresh-install language default is automatic", canon.get("ui", {}).get("language") == "auto")
    check("fresh-install news age scale defaults are sane",
          canon.get("ui", {}).get("news_age_color_enabled") is True and
          canon.get("ui", {}).get("news_age_color_minutes") == 120 and
          canon.get("ui", {}).get("news_age_recent_color") == "" and
          canon.get("ui", {}).get("news_age_older_color") == "")

    check("server fallback matches default-config.json", srv.DEFAULT_CONFIG == canon)
    check("cache fallback matches default-config.json", m.FALLBACK_DEFAULT_CONFIG == canon)

    print("  [corrupt config must never reset silently]")
    m.CONFIG.write_text("{broken", encoding="utf-8")
    try:
        m.load_config()
        cache_corrupt_rejected = False
    except RuntimeError:
        cache_corrupt_rejected = True
    check("cache helper rejects corrupt existing config", cache_corrupt_rejected)
    m.atomic_write_json(m.CONFIG, canon)

    srv.CONFIG_FILE.write_text("{broken", encoding="utf-8")
    try:
        srv.load_config_without_ensure()
        server_corrupt_rejected = False
    except RuntimeError:
        server_corrupt_rejected = True
    check("local server rejects corrupt existing config", server_corrupt_rejected)
    srv.atomic_write_json(srv.CONFIG_FILE, canon)

    repaired = srv.merge_config({})["block_order"]
    check("server rebuilds the canonical block order",
          repaired == canon["block_order"], f"got {repaired}")

    server.shutdown()
    shutil.rmtree(home, ignore_errors=True)

    print()
    if FAILURES:
        print(f"  {len(FAILURES)} regression test(s) failed:")
        for f in FAILURES:
            print("    -", f)
        return 1
    print("  all regression tests passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
