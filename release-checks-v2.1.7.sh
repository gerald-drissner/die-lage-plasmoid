#!/usr/bin/env bash
# Pre-release checks for Die Lage v2.1.7.
# Run from the unpacked release folder. Exits non-zero on the first failure.

set -euo pipefail
cd -- "$(cd -- "$(dirname -- "$0")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1

VERSION="2.1.7"
fail() { echo "FAIL: $*" >&2; exit 1; }
ok()   { echo "  ok  $*"; }
CHECK_TMP="$(mktemp -d)"
cleanup() { rm -rf "$CHECK_TMP"; }
trap cleanup EXIT
IMPORT_HOME="$CHECK_TMP/import-home"
mkdir -p "$IMPORT_HOME"

echo "== Die Lage ${VERSION} release checks =="

echo "-- package cleanliness and syntax --"
if find . -type d -name __pycache__ -o -type f \( -name '*.pyc' -o -name '*.pyo' -o -name '*~' -o -name '*.swp' -o -name '.DS_Store' \) | grep -q .; then
    find . -type d -name __pycache__ -o -type f \( -name '*.pyc' -o -name '*.pyo' -o -name '*~' -o -name '*.swp' -o -name '.DS_Store' \) >&2
    fail "generated/editor artifacts are present in the release tree"
fi
ok "release tree contains no generated/editor artifacts"
python3 - <<'PY' || fail "Python syntax"
from pathlib import Path
for name in ("files/bin/dielage-cache.py", "files/bin/dielage-server.py", "tests/regression.py"):
    compile(Path(name).read_text(encoding="utf-8"), name, "exec")
PY
ok "Python sources compile"
for f in install.sh uninstall.sh emergency-clean-dielage.sh release-checks-v2.1.7.sh; do
    bash -n "$f" || fail "$f syntax"
done
ok "shell scripts parse"

echo "-- metadata --"
python3 - "$VERSION" <<'PY' || fail "metadata mismatch"
import json, sys, pathlib
want = sys.argv[1]
d = json.loads(pathlib.Path("files/plasmoid/metadata.json").read_text(encoding="utf-8"))
assert d["KPlugin"]["Version"] == want, d["KPlugin"]["Version"]
assert d["Version"] == want
assert d["KPackageStructure"] == "Plasma/Applet"
assert d["X-Plasma-API-Minimum-Version"] == "6.0"
import xml.etree.ElementTree as ET
root = ET.parse("files/plasmoid/metadata.appdata.xml").getroot()
releases = root.find("releases")
assert releases is not None and len(releases), "AppStream releases missing"
assert releases[0].attrib.get("version") == want, releases[0].attrib
assert releases[0].attrib.get("date") == "2026-08-28", releases[0].attrib
assert root.findtext("id") == d["KPlugin"]["Id"]
PY
ok "metadata.json and AppStream metadata valid, latest release ${VERSION}"

echo "-- version strings agree --"
for f in files/bin/dielage-cache.py files/bin/dielage-server.py files/plasmoid/contents/ui/main.qml; do
    grep -q "$VERSION" "$f" || fail "$f does not mention $VERSION"
done
# Look for version *declarations* only. Historical prose in comments such as
# "before v2.1.0 this was broken" is documentation, not drift, so the pattern
# requires a quoted string, a filename form, or a doc heading.
python3 - "$VERSION" <<'PY' || fail "stale version declarations"
import pathlib, re, sys
want = sys.argv[1]
patterns = [
    re.compile(r'"(\d+\.\d+\.\d+)"'),          # current version in json/py/qml
    re.compile(r'\b(\d+_\d+_\d+)\b'),           # current version in filenames
    re.compile(r'^#\s*Die Lage v(\d+\.\d+\.\d+)', re.M),
    re.compile(r'release-checks-v(\d+\.\d+\.\d+)\.sh'),
]
skip_files = {"CHANGELOG.md", "metadata.appdata.xml"}
bad = []
for path in pathlib.Path(".").rglob("*"):
    if not path.is_file() or path.name in skip_files:
        continue
    if path.suffix not in (".py", ".qml", ".json", ".md", ".sh", ".xml"):
        continue
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        continue
    for pattern in patterns:
        for found in pattern.findall(text):
            normalised = found.replace("_", ".")
            # Ignore unrelated triples such as a Python version or a coordinate.
            if not re.fullmatch(r"\d+\.\d+\.\d+", normalised):
                continue
            if normalised.startswith(("2.0.", "2.1.")) and normalised != want:
                bad.append(f"{path}: {found}")
if bad:
    print("stale version declarations:", *sorted(set(bad)), sep="\n  ")
    raise SystemExit(1)
PY
ok "no stale version strings"

echo "-- config defaults are a single source of truth --"
HOME="$IMPORT_HOME" python3 - <<'PY' || fail "inline fallback config drifted from default-config.json"
import json, pathlib, importlib.util, sys
sys.argv = ["check"]
canon = json.loads(pathlib.Path("files/config/default-config.json").read_text(encoding="utf-8"))
for name, path in (("cache", "files/bin/dielage-cache.py"), ("server", "files/bin/dielage-server.py")):
    spec = importlib.util.spec_from_file_location("m_" + name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fallback = getattr(mod, "FALLBACK_DEFAULT_CONFIG", None) or mod.DEFAULT_CONFIG
    assert fallback == canon, f"{name} fallback differs from default-config.json"
PY
ok "cache and server fallbacks match default-config.json"

echo "-- QML structure --"
python3 - <<'PY' || fail "QML structural check"
import re, sys
raw = open("files/plasmoid/contents/ui/main.qml", encoding="utf-8").read()

def strip(src):
    out, i, n, prev = [], 0, len(src), ''
    while i < n:
        c = src[i]
        if c == '/' and i + 1 < n and src[i+1] == '/':
            j = src.find('\n', i); i = n if j < 0 else j; continue
        if c == '/' and i + 1 < n and src[i+1] == '*':
            j = src.find('*/', i+2); i = n if j < 0 else j+2; out.append(' '); continue
        if c == '/' and prev in '(,=:[!&|?{};+':
            j, okr = i + 1, False
            while j < n:
                if src[j] == '\\': j += 2; continue
                if src[j] == '[':
                    while j < n and src[j] != ']':
                        j += 2 if src[j] == '\\' else 1
                if src[j] == '/': okr = True; break
                if src[j] == '\n': break
                j += 1
            if okr:
                out.append('R'); i = j + 1
                while i < n and src[i].isalpha(): i += 1
                prev = 'R'; continue
        if c in '"\'':
            q = c; i += 1
            while i < n:
                if src[i] == '\\': i += 2; continue
                if src[i] == q: i += 1; break
                if src[i] == '\n': break
                i += 1
            out.append('S'); prev = 'S'; continue
        out.append(c); i += 1
        if not c.isspace(): prev = c
    return ''.join(out)

s, stack, line, errs = strip(raw), [], 1, []
pairs = {')': '(', ']': '[', '}': '{'}
for ch in s:
    if ch == '\n': line += 1
    elif ch in '([{': stack.append((ch, line))
    elif ch in ')]}':
        if not stack: errs.append(f"line {line}: unexpected {ch}"); continue
        op, ol = stack.pop()
        if op != pairs[ch]: errs.append(f"line {line}: {ch} closes {op} from line {ol}")
errs += [f"line {ol}: unclosed {op}" for op, ol in stack]
assert not errs, errs[:5]

ids = re.findall(r'^\s*id:\s*(\w+)', raw, re.M)
dupes = {i for i in ids if ids.count(i) > 1}
assert not dupes, f"duplicate ids: {sorted(dupes)}"

# A balanced-brace check is not enough for QML: assigning the same direct
# property twice inside one object is a parse-time error (for example two
# `opacity:` lines). Track each brace scope independently and reject duplicate
# direct assignments. This deliberately operates on the already stripped text,
# so comments and string contents cannot create false matches.
def duplicate_direct_properties(src):
    scopes = []
    found = []
    simple = re.compile(r'^\s*([A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)*)\s*:')
    declared = re.compile(r'^\s*(?:readonly\s+)?property\s+[A-Za-z_][\w<>.]*\s+([A-Za-z_][\w]*)\s*:')
    line_no = 0
    for line_text in src.splitlines():
        line_no += 1
        # Apply leading closing braces before examining a property on the same
        # line. Ordinary QML formatting puts properties on their own lines, but
        # this also handles `} else {` safely.
        stripped_line = line_text.lstrip()
        lead_close = 0
        while lead_close < len(stripped_line) and stripped_line[lead_close] == '}':
            if scopes:
                scopes.pop()
            lead_close += 1
        remainder = stripped_line[lead_close:].lstrip()

        if scopes:
            m = declared.match(remainder) or simple.match(remainder)
            if m:
                name = m.group(1)
                # `strip()` replaces every quoted string with the sentinel S.
                # JSON/JS object literals therefore contain lines such as
                # `S: S,`; those are data keys, not QML property names.
                if name == "S":
                    m = None
                if m is None:
                    name = None
                previous = scopes[-1].get(name) if name is not None else None
                if name is not None:
                    if previous is not None:
                        found.append((line_no, name, previous))
                    else:
                        scopes[-1][name] = line_no

        # Scan brace structure for the rest of the line. Leading `}` were
        # already consumed above. Every brace gets its own scope; nested JS
        # object literals/functions therefore cannot pollute their parent.
        tail = stripped_line[lead_close:]
        for ch in tail:
            if ch == '{':
                scopes.append({})
            elif ch == '}':
                if scopes:
                    scopes.pop()
    return found

# Self-test the detector so a future edit cannot silently neuter this guard.
_probe = "Item {\n    opacity: 0.5\n    opacity: 0.8\n}\n"
assert duplicate_direct_properties(_probe), "duplicate-property checker self-test failed"
property_dupes = duplicate_direct_properties(strip(raw))
assert not property_dupes, "duplicate QML properties: " + "; ".join(
    f"line {line}: {name} already set on line {prev}" for line, name, prev in property_dupes[:10]
)

# Both translation tables must define exactly the same keys, and every key
# used by a t() call must exist.
tables = {}
for name in ("i18nEn", "i18nDe"):
    marker = f"readonly property var {name}: ("
    start = raw.index(marker) + len(marker)
    body = raw[start:raw.index("\n    })", start)].rstrip().rstrip(",") + "\n}"
    import json
    tables[name] = json.loads(body)
en, de = set(tables["i18nEn"]), set(tables["i18nDe"])
assert en == de, f"key mismatch: {sorted(en ^ de)}"
used = set(re.findall(r'\bt\(\s*"(\w+)"\s*\)', raw))
assert not (used - en), f"undefined keys: {sorted(used - en)}"
print(f"    {len(en)} translation keys, {len(re.findall(chr(92)+'bt.'+chr(92)+'s*\"', raw))} call sites")
PY
ok "QML brackets balanced, ids unique, translations complete"

echo "-- error classification --"
HOME="$IMPORT_HOME" python3 - <<'PY' || fail "error classification"
import sys, urllib.error, socket, importlib.util
sys.argv = ["check"]
spec = importlib.util.spec_from_file_location("dlc", "files/bin/dielage-cache.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
expect = {403: "blocked", 429: "rate_limited", 451: "geo_blocked", 404: "not_found", 503: "server_error"}
for code, kind in expect.items():
    got = m.classify_error(urllib.error.HTTPError("u", code, "", {}, None))["kind"]
    assert got == kind, f"HTTP {code} -> {got}, expected {kind}"
assert m.classify_error(urllib.error.URLError(socket.gaierror(-2, "Name or service not known")))["kind"] == "dns"
for kind, (de, en) in m.ERROR_TEXTS.items():
    assert de and en, f"missing text for {kind}"
PY
ok "HTTP codes and network errors map to the right causes"

echo "-- behavioural regression suite --"
python3 tests/regression.py || fail "regression tests"
ok "regression suite green"

echo "-- systemd hardening --"
python3 - <<'PY' || fail "systemd unit hardening"
from pathlib import Path
cache_services = [
    Path("files/systemd/dielage-cache.service"),
    Path("files/systemd/dielage-cache-boot.service"),
]
server = Path("files/systemd/dielage-local-server.service")
for path in cache_services + [server]:
    text = path.read_text(encoding="utf-8")
    for required in ("UMask=0077", "NoNewPrivileges=yes", "PrivateTmp=yes",
                     "RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX",
                     "MemoryMax=256M", "TasksMax=64"):
        assert required in text, f"{path}: missing {required}"
for path in cache_services:
    assert "SuccessExitStatus=75" in path.read_text(encoding="utf-8"), f"{path}: lock exit not accepted"
assert "Restart=on-failure" in server.read_text(encoding="utf-8")
PY
ok "systemd units keep the expected privacy/resource hardening"

echo "-- release-specific UI sanity --"
python3 - <<'PY' || fail "v2.1.7 UI sanity"
from pathlib import Path
import re, json
qml = Path("files/plasmoid/contents/ui/main.qml").read_text(encoding="utf-8")
assert '"weatherApiOk": "OpenWeather API key works."' in qml
assert '"weatherApiOk": "OpenWeather-API-Key funktioniert."' in qml
assert "{location}" not in re.search(r'readonly property var i18n(?:En|De):.*?function t\(', qml, re.S).group(0)
server = Path("files/bin/dielage-server.py").read_text(encoding="utf-8")
assert '"reason": "ok"' in server and '"location"' not in re.search(r'def check_openweather_api\(.*?\n\n', server, re.S).group(0)
# v2.1.7 live-UI fixes
assert 'id: weatherSourceInfoButton' in qml and 'id: weatherSourcePopup' in qml
assert 'Weather data provided by OpenWeather' in qml
assert 'logo_white_cropped.png' in qml
assert 'opacity: 0.42' in qml
assert qml.count('QQC2.BusyIndicator {') >= 5
assert 'running: topRefreshButton.busy' in qml
assert 'function headlineAgeColor(entry)' in qml
assert '"news_age_color_minutes": root.newsAgeWindowMinutesValue()' in qml
PY
ok "OpenWeather success text, subtle attribution, refresh spinners and RSS age scale are wired"

echo "-- installer sandbox (upgrade path) --"
DL_SANDBOX="$CHECK_TMP/upgrade-home"
mkdir -p "$DL_SANDBOX/.config/die-lage"
cat > "$DL_SANDBOX/.config/die-lage/config.json" <<'JSON'
{"feeds":[{"limit":7,"name":"Eigener Feed","url":"https://example.org/rss"}],
 "ui":{"font_size":18,"custom_title":"Test","panel_popup_width":1000},
 "markets":{"twelve_data_api_key":"SANDBOXKEY","indices":[{"name":"DAX","symbol":"^DAX"}]},
 "fetch_interval_minutes":15}
JSON
mkdir -p "$DL_SANDBOX/.local/share/plasma/plasmoids/com.drissner.dielage"
touch "$DL_SANDBOX/.local/share/plasma/plasmoids/com.drissner.dielage/old-marker"
if ! HOME="$DL_SANDBOX" DIELAGE_SKIP_FIRST_REFRESH=1 DIELAGE_SKIP_SYSTEMD=1 timeout 120 ./install.sh >"$DL_SANDBOX/install.log" 2>&1; then
    tail -20 "$DL_SANDBOX/install.log" >&2
    fail "installer failed in sandbox"
fi
python3 - "$DL_SANDBOX" <<'PY' || fail "installer did not preserve user data or apply migrations"
import json, pathlib, sys, os
home = pathlib.Path(sys.argv[1])
cfg = json.loads((home / ".config/die-lage/config.json").read_text(encoding="utf-8"))
assert cfg["feeds"][0]["name"] == "Eigener Feed", "user feeds lost"
assert cfg["markets"]["twelve_data_api_key"] == "SANDBOXKEY", "API key lost"
assert cfg["ui"]["custom_title"] == "Test", "custom title lost"
assert cfg["fetch_interval_minutes"] == 15, "custom interval lost"
assert cfg["ui"]["panel_popup_width"] == 600, "popup width migration missing"
assert cfg["markets"]["indices"][0]["symbol"] == "^GDAXI", "index alias migration missing"
for key in ("system_interval_minutes", "local_server_port", "boot_refresh_enabled"):
    assert key in cfg, f"missing new key {key}"
for key in ("prayer_upcoming_before_minutes", "prayer_now_after_minutes", "news_show_age",
            "news_age_color_enabled", "news_age_color_minutes", "news_age_recent_color",
            "news_age_older_color"):
    assert key in cfg["ui"], f"missing new ui key {key}"
assert cfg["ui"]["news_age_color_minutes"] == 120, "RSS age scale migration default changed"
assert "openweather_api_key" in cfg.get("weather", {}), "missing OpenWeather config key"
mode = os.stat(home / ".config/die-lage/config.json").st_mode & 0o777
assert mode == 0o600, f"config.json mode {oct(mode)} should be 0600"
plasmoid = home / ".local/share/plasma/plasmoids/com.drissner.dielage"
assert (plasmoid / "contents/ui/main.qml").exists(), "plasmoid not installed"
assert not (plasmoid / "old-marker").exists(), "old package not replaced"
leftovers = list((plasmoid.parent).glob(".com.drissner.dielage.*"))
assert not leftovers, f"staging leftovers: {leftovers}"
PY
ok "upgrade preserves user data, applies migrations, installs cleanly"

FRESH_HOME="$CHECK_TMP/fresh-home"
mkdir -p "$FRESH_HOME"
if HOME="$FRESH_HOME" DIELAGE_SKIP_FIRST_REFRESH=1 DIELAGE_SKIP_SYSTEMD=1 timeout 120 ./install.sh >/dev/null 2>&1; then
    ok "fresh install completes"
else
    fail "fresh install failed"
fi

echo "-- corrupt-config installer safety --"
BROKEN_HOME="$CHECK_TMP/broken-home"
mkdir -p "$BROKEN_HOME/.config/die-lage" "$BROKEN_HOME/.local/share/plasma/plasmoids/com.drissner.dielage"
printf '%s' '{"feeds": [BROKEN' > "$BROKEN_HOME/.config/die-lage/config.json"
printf '%s' 'old-widget' > "$BROKEN_HOME/.local/share/plasma/plasmoids/com.drissner.dielage/old-marker"
cp "$BROKEN_HOME/.config/die-lage/config.json" "$CHECK_TMP/broken-before.json"
if HOME="$BROKEN_HOME" DIELAGE_SKIP_FIRST_REFRESH=1 DIELAGE_SKIP_SYSTEMD=1 timeout 60 ./install.sh >"$CHECK_TMP/broken-install.log" 2>&1; then
    fail "installer accepted corrupt existing config"
fi
cmp -s "$BROKEN_HOME/.config/die-lage/config.json" "$CHECK_TMP/broken-before.json" || fail "corrupt config was modified"
[ -f "$BROKEN_HOME/.local/share/plasma/plasmoids/com.drissner.dielage/old-marker" ] || fail "old widget changed before corrupt-config preflight failure"
[ ! -e "$BROKEN_HOME/.local/bin/dielage-cache.py" ] || fail "helper changed before corrupt-config preflight failure"
ok "corrupt existing config aborts before installed files are changed"

echo "-- required files --"
for f in files/bin/dielage-cache.py files/bin/dielage-server.py \
         files/plasmoid/contents/ui/main.qml files/plasmoid/metadata.json \
         files/plasmoid/contents/images/dielage.svg \
         files/plasmoid/contents/images/dielage-panel.svg \
         files/config/default-config.json \
         files/systemd/dielage-cache.service files/systemd/dielage-cache.timer \
         files/systemd/dielage-cache-boot.service files/systemd/dielage-cache-boot.timer \
         files/systemd/dielage-local-server.service \
         install.sh uninstall.sh README.md CHANGELOG.md LICENSE tests/regression.py; do
    [ -f "$f" ] || fail "missing $f"
done
ok "all shipped files present"

echo
echo "All checks passed for v${VERSION}."
