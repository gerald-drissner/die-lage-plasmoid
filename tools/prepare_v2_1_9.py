#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import json
import pprint
import re
import shutil

ROOT = Path(__file__).resolve().parents[1]
VERSION = "2.1.9"
DATE = "2026-09-28"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def write(rel: str, text: str) -> None:
    path = ROOT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one match, got {count}")
    return text.replace(old, new, 1)


def replace_regex_once(text: str, pattern: str, repl: str, label: str, flags: int = 0) -> str:
    out, count = re.subn(pattern, repl, text, count=1, flags=flags)
    if count != 1:
        raise SystemExit(f"{label}: expected exactly one regex match, got {count}")
    return out


# ---------------------------------------------------------------------------
# Canonical defaults
# ---------------------------------------------------------------------------
defaults_path = ROOT / "files/config/default-config.json"
defaults = json.loads(defaults_path.read_text(encoding="utf-8"))
system = defaults.setdefault("system", {})
system.update({
    "updates_check_native": True,
    "updates_check_flatpak": False,
    "updates_check_snap": False,
    "updates_interval_minutes": 60,
    "updates_low_memory_protection": True,
})
defaults_path.write_text(json.dumps(defaults, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
pretty_defaults = pprint.pformat(defaults, width=120, sort_dicts=False)


# ---------------------------------------------------------------------------
# Cross-distribution update checker module
# ---------------------------------------------------------------------------
updates_module = r'''#!/usr/bin/env python3
"""Read-only, cached Linux update checks for Die Lage.

The module never installs packages and never refreshes package metadata by
itself.  It detects one native package manager, then optionally checks Flatpak
and Snap as separate sources.  Heavy checks are rate-limited independently of
the normal System-block refresh and are skipped under acute memory pressure.
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime
import json
import os
import re
import shutil
import subprocess
import time

STATE_FILE = Path.home() / ".cache" / "die-lage" / "updates.json"
DEFAULT_INTERVAL_MINUTES = 60
MIN_INTERVAL_MINUTES = 10
MAX_INTERVAL_MINUTES = 1440
LOW_MEMORY_SKIP_MIB = 1024
LOW_TOTAL_MEMORY_WARN_MIB = 4096
LOW_MEMORY_RETRY_MINUTES = 10
SAFE_PATH = "/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"


def _bool(value, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    return str(value).strip().lower() not in {"0", "false", "no", "off", "aus", "nein"}


def _int(value, fallback: int, lo: int, hi: int) -> int:
    try:
        value = int(value)
    except Exception:
        value = fallback
    return max(lo, min(hi, value))


def _read_os_release() -> dict[str, str]:
    data: dict[str, str] = {}
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8", errors="replace").splitlines():
            if not line or line.lstrip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            value = value.strip().strip('"').strip("'")
            data[key.strip().upper()] = value
    except Exception:
        pass
    return data


def memory_snapshot() -> dict[str, int]:
    values: dict[str, int] = {}
    try:
        text = Path("/proc/meminfo").read_text(encoding="utf-8", errors="replace")
        for key in ("MemTotal", "MemAvailable", "SwapFree"):
            m = re.search(rf"^{key}:\s+(\d+)\s+kB", text, re.M)
            if m:
                values[key] = int(m.group(1)) // 1024
    except Exception:
        pass
    return {
        "total_mib": values.get("MemTotal", 0),
        "available_mib": values.get("MemAvailable", 0),
        "swap_free_mib": values.get("SwapFree", 0),
    }


def _run(args: list[str], timeout: float = 30.0, extra_env: dict[str, str] | None = None):
    if not args:
        return None
    exe = shutil.which(args[0], path=os.environ.get("PATH") or SAFE_PATH) or shutil.which(args[0], path=SAFE_PATH)
    if not exe:
        return None
    env = {**os.environ, "PATH": SAFE_PATH, "LC_ALL": "C", "LANG": "C"}
    if extra_env:
        env.update(extra_env)
    try:
        return subprocess.run(
            [exe] + list(args[1:]),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
        )
    except Exception:
        return None


def _lines(text: str) -> list[str]:
    return [line.strip() for line in (text or "").splitlines() if line.strip()]


def _result(status: str, count: int | None, backend: str, message: str = "") -> dict:
    return {"status": status, "count": count, "backend": backend, "message": message}


def _count_apt() -> dict:
    proc = _run(["apt-get", "-s", "upgrade"], timeout=35)
    if proc is not None and proc.returncode == 0:
        return _result("ok", sum(1 for line in _lines(proc.stdout) if line.startswith("Inst ")), "APT")
    proc = _run(["apt", "list", "--upgradable"], timeout=30)
    if proc is not None and proc.returncode == 0:
        count = sum(1 for line in _lines(proc.stdout) if "/" in line and "upgradable" in line.lower())
        return _result("ok", count, "APT")
    return _result("error", None, "APT", "update query failed")


def _count_pacman() -> dict:
    checkupdates = shutil.which("checkupdates")
    if checkupdates:
        db = STATE_FILE.parent / "checkupdates-db"
        db.mkdir(parents=True, exist_ok=True)
        proc = _run(["checkupdates"], timeout=60, extra_env={"CHECKUPDATES_DB": str(db)})
        if proc is not None and proc.returncode in (0, 2):
            return _result("ok", len(_lines(proc.stdout)), "checkupdates")
    proc = _run(["pacman", "-Qu"], timeout=20)
    if proc is not None and proc.returncode in (0, 1):
        return _result("ok", len(_lines(proc.stdout)), "pacman")
    return _result("error", None, "pacman", "update query failed")


def _count_dnf() -> dict:
    for args, label in ((["dnf5", "-q", "check-upgrade"], "DNF5"), (["dnf", "-q", "check-update"], "DNF")):
        proc = _run(args, timeout=55)
        if proc is None or proc.returncode not in (0, 100):
            continue
        count = 0
        for line in _lines(proc.stdout):
            low = line.lower()
            if low.startswith(("last metadata", "metadata", "obsoleting", "security:")):
                continue
            parts = line.split()
            if len(parts) >= 3 and re.search(r"\.[a-z0-9_]{2,12}$", parts[0], re.I):
                count += 1
        return _result("ok", count, label)
    return _result("error", None, "DNF", "update query failed")


def _count_zypper() -> dict:
    proc = _run(["zypper", "--non-interactive", "-q", "list-updates"], timeout=45)
    if proc is not None and proc.returncode == 0:
        count = sum(1 for line in _lines(proc.stdout) if re.match(r"^(v|package)\s*\|", line, re.I))
        return _result("ok", count, "Zypper")
    return _result("error", None, "Zypper", "update query failed")


def _count_apk() -> dict:
    proc = _run(["apk", "version", "-l", "<"], timeout=30)
    if proc is not None and proc.returncode == 0:
        return _result("ok", len(_lines(proc.stdout)), "APK")
    return _result("error", None, "APK", "update query failed")


def _count_xbps() -> dict:
    proc = _run(["xbps-install", "-Mun"], timeout=45)
    if proc is not None and proc.returncode == 0:
        count = 0
        for line in _lines(proc.stdout):
            low = line.lower()
            if low.startswith(("name", "size", "total", "transaction", "dry run")):
                continue
            if re.search(r"\bupdate\b|\bupgrade\b|->", line, re.I) or re.match(r"^[A-Za-z0-9+_.:@-]+-[0-9]", line):
                count += 1
        return _result("ok", count, "XBPS")
    return _result("error", None, "XBPS", "update query failed")


def _count_eopkg() -> dict:
    proc = _run(["eopkg", "list-upgrades"], timeout=45)
    if proc is not None and proc.returncode == 0:
        rows = []
        for line in _lines(proc.stdout):
            low = line.lower()
            if low.startswith(("package", "program", "no packages", "following packages")):
                continue
            if not set(line) <= {"-", "=", " "}:
                rows.append(line)
        return _result("ok", len(rows), "eopkg")
    return _result("error", None, "eopkg", "update query failed")


def _count_emerge() -> dict:
    proc = _run(["emerge", "-puDN", "@world"], timeout=90)
    if proc is not None and proc.returncode == 0:
        count = sum(1 for line in _lines(proc.stdout) if re.search(r"\[(?:ebuild|binary).*\bU\b", line))
        return _result("ok", count, "Portage")
    return _result("error", None, "Portage", "update query failed")


def _count_rpm_ostree() -> dict:
    proc = _run(["rpm-ostree", "upgrade", "--check"], timeout=60)
    if proc is not None and proc.returncode == 0:
        text = (proc.stdout or "") + "\n" + (proc.stderr or "")
        if re.search(r"no upgrade available|no updates available", text, re.I):
            return _result("ok", 0, "rpm-ostree")
        # rpm-ostree presents a deployment, not a package count. Treat one
        # available deployment as one system update rather than inventing a
        # package number from diff text.
        available = bool(re.search(r"availableupdate|upgrade available|diff:", text, re.I))
        return _result("ok", 1 if available else 0, "rpm-ostree")
    return _result("error", None, "rpm-ostree", "update query failed")


def _count_packagekit() -> dict:
    proc = _run(["pkcon", "get-updates"], timeout=55)
    if proc is None:
        return _result("unsupported", None, "PackageKit", "not installed")
    text = (proc.stdout or "") + "\n" + (proc.stderr or "")
    count = 0
    unknown = 0
    status_prefixes = (
        "getting", "loading", "querying", "refreshing", "finished", "waiting", "starting",
        "available updates", "there are no updates", "no packages require updating", "transaction",
        "percentage", "status",
    )
    for line in _lines(text):
        low = line.lower()
        if low.startswith(status_prefixes):
            continue
        if ";" in line:
            count += 1
        else:
            unknown += 1
    if count or (proc.returncode == 0 and unknown == 0):
        return _result("ok", count, "PackageKit")
    return _result("error", None, "PackageKit", "unrecognized output")


_NATIVE = {
    "apt": _count_apt,
    "pacman": _count_pacman,
    "dnf": _count_dnf,
    "zypper": _count_zypper,
    "apk": _count_apk,
    "xbps": _count_xbps,
    "eopkg": _count_eopkg,
    "emerge": _count_emerge,
    "rpm-ostree": _count_rpm_ostree,
}


def native_backend() -> str:
    info = _read_os_release()
    ids = " ".join((info.get("ID", ""), info.get("ID_LIKE", ""))).lower().replace("-", "_")
    families = (
        (("arch", "manjaro", "endeavour", "cachyos", "arcolinux"), "pacman", ("pacman",)),
        (("debian", "ubuntu", "mint", "pop", "neon", "elementary", "zorin"), "apt", ("apt-get", "apt")),
        (("fedora", "rhel", "centos", "rocky", "alma", "nobara"), "dnf", ("dnf5", "dnf")),
        (("opensuse", "suse", "sles", "tumbleweed"), "zypper", ("zypper",)),
        (("alpine",), "apk", ("apk",)),
        (("void",), "xbps", ("xbps-install",)),
        (("solus",), "eopkg", ("eopkg",)),
        (("gentoo",), "emerge", ("emerge",)),
        (("coreos", "silverblue", "kinoite", "bootc"), "rpm-ostree", ("rpm-ostree",)),
    )
    for needles, backend, commands in families:
        if any(n in ids for n in needles) and any(shutil.which(cmd) for cmd in commands):
            return backend

    # Unknown derivative: choose a single installed native manager in a stable
    # order. Never run several managers and add their results together.
    command_fallbacks = (
        ("apt", ("apt-get", "apt")),
        ("pacman", ("pacman",)),
        ("dnf", ("dnf5", "dnf")),
        ("zypper", ("zypper",)),
        ("apk", ("apk",)),
        ("xbps", ("xbps-install",)),
        ("eopkg", ("eopkg",)),
        ("emerge", ("emerge",)),
        ("rpm-ostree", ("rpm-ostree",)),
    )
    for backend, commands in command_fallbacks:
        if any(shutil.which(cmd) for cmd in commands):
            return backend
    return "packagekit" if shutil.which("pkcon") else ""


def check_native() -> dict:
    backend = native_backend()
    if not backend:
        return _result("unsupported", None, "native", "no supported package manager found")
    if backend == "packagekit":
        return _count_packagekit()
    try:
        result = _NATIVE[backend]()
    except Exception as exc:
        result = _result("error", None, backend, type(exc).__name__)
    # PackageKit is a fallback only if the native query could not be used. A
    # confident native zero is final and must not trigger a second heavy query.
    if result.get("status") != "ok" and shutil.which("pkcon"):
        fallback = _count_packagekit()
        if fallback.get("status") == "ok":
            return fallback
    return result


def check_flatpak() -> dict:
    if not shutil.which("flatpak"):
        return _result("unsupported", None, "Flatpak", "not installed")
    proc = _run(["flatpak", "remote-ls", "--updates", "--columns=application"], timeout=35)
    if proc is not None and proc.returncode == 0:
        return _result("ok", len(_lines(proc.stdout)), "Flatpak")
    # Older Flatpak releases may not support --columns.
    proc = _run(["flatpak", "remote-ls", "--updates"], timeout=35)
    if proc is not None and proc.returncode == 0:
        rows = [line for line in _lines(proc.stdout) if not line.lower().startswith(("application id", "ref", "name"))]
        return _result("ok", len(rows), "Flatpak")
    return _result("error", None, "Flatpak", "update query failed")


def check_snap() -> dict:
    if not shutil.which("snap"):
        return _result("unsupported", None, "Snap", "not installed")
    proc = _run(["snap", "refresh", "--list"], timeout=40)
    if proc is not None and proc.returncode == 0:
        lines = _lines(proc.stdout)
        if any("all snaps up to date" in line.lower() for line in lines):
            return _result("ok", 0, "Snap")
        rows = [line for line in lines if not re.match(r"^Name\s+Version\s+Rev\s+", line, re.I)]
        return _result("ok", len(rows), "Snap")
    return _result("error", None, "Snap", "update query failed")


def _load_state() -> dict:
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_state(data: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_name(f"{STATE_FILE.name}.tmp.{os.getpid()}.{time.time_ns()}")
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.chmod(0o600)
        tmp.replace(STATE_FILE)
    finally:
        try:
            tmp.unlink()
        except FileNotFoundError:
            pass


def _fingerprint(cfg: dict) -> str:
    payload = {
        "native": _bool(cfg.get("updates_check_native"), True),
        "flatpak": _bool(cfg.get("updates_check_flatpak"), False),
        "snap": _bool(cfg.get("updates_check_snap"), False),
        "protect": _bool(cfg.get("updates_low_memory_protection"), True),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _policy(state: dict, cfg: dict, memory: dict, interval: int) -> dict:
    total = int(memory.get("total_mib", 0) or 0)
    available = int(memory.get("available_mib", 0) or 0)
    return {
        "interval_minutes": interval,
        "memory": memory,
        "low_total_memory": bool(total and total < LOW_TOTAL_MEMORY_WARN_MIB),
        "low_available_memory": bool(available and available < LOW_MEMORY_SKIP_MIB),
        "low_memory_protection": _bool(cfg.get("updates_low_memory_protection"), True),
        "skipped_low_memory": bool(state.get("skipped_low_memory")),
        "last_checked": int(state.get("checked_at", 0) or 0),
        "last_attempt": int(state.get("attempted_at", 0) or 0),
        "sources": state.get("sources", {}) if isinstance(state.get("sources"), dict) else {},
    }


def check_updates(system_cfg: dict, force: bool = False) -> dict:
    cfg = system_cfg if isinstance(system_cfg, dict) else {}
    interval = _int(cfg.get("updates_interval_minutes"), DEFAULT_INTERVAL_MINUTES,
                    MIN_INTERVAL_MINUTES, MAX_INTERVAL_MINUTES)
    enabled = {
        "native": _bool(cfg.get("updates_check_native"), True),
        "flatpak": _bool(cfg.get("updates_check_flatpak"), False),
        "snap": _bool(cfg.get("updates_check_snap"), False),
    }
    now = int(time.time())
    memory = memory_snapshot()
    state = _load_state()
    fingerprint = _fingerprint(cfg)

    if not any(enabled.values()):
        state = {
            "schema": 1, "fingerprint": fingerprint, "checked_at": 0,
            "attempted_at": now, "total": 0, "sources": {
                key: {"status": "disabled", "count": None, "backend": key, "message": "disabled"}
                for key in enabled
            }, "skipped_low_memory": False,
        }
        _save_state(state)
        return {**state, "policy": _policy(state, cfg, memory, interval)}

    changed = state.get("fingerprint") != fingerprint
    last_checked = int(state.get("checked_at", 0) or 0)
    retry_at = int(state.get("retry_at", 0) or 0)
    due = force or changed or not last_checked or (now - last_checked >= interval * 60)
    if retry_at and now < retry_at and not force:
        due = False

    if not due:
        return {**state, "policy": _policy(state, cfg, memory, interval)}

    available = int(memory.get("available_mib", 0) or 0)
    protect = _bool(cfg.get("updates_low_memory_protection"), True)
    if protect and available and available < LOW_MEMORY_SKIP_MIB:
        # Keep the previous successful counts.  A skipped check is not a zero.
        state["fingerprint"] = fingerprint
        state["attempted_at"] = now
        state["skipped_low_memory"] = True
        state["retry_at"] = now + LOW_MEMORY_RETRY_MINUTES * 60
        _save_state(state)
        return {**state, "policy": _policy(state, cfg, memory, interval)}

    sources: dict[str, dict] = {}
    total = 0
    successful = 0
    # Intentionally sequential. Flatpak/Snap/package managers can each be
    # memory-hungry; running them in parallel defeats the low-memory guard.
    for key, checker in (("native", check_native), ("flatpak", check_flatpak), ("snap", check_snap)):
        if not enabled[key]:
            sources[key] = _result("disabled", None, key, "disabled")
            continue
        result = checker()
        sources[key] = result
        if result.get("status") == "ok" and result.get("count") is not None:
            successful += 1
            total += int(result["count"])

    state = {
        "schema": 1,
        "fingerprint": fingerprint,
        "checked_at": now,
        "attempted_at": now,
        "retry_at": 0,
        "total": total if successful else None,
        "sources": sources,
        "skipped_low_memory": False,
    }
    _save_state(state)
    return {**state, "policy": _policy(state, cfg, memory, interval)}


def as_system_item(result: dict, english: bool = False) -> dict:
    total = result.get("total")
    sources = result.get("sources", {}) if isinstance(result.get("sources"), dict) else {}
    policy = result.get("policy", {}) if isinstance(result.get("policy"), dict) else {}
    pieces: list[str] = []
    partial = False
    for key, label in (("native", "System"), ("flatpak", "Flatpak"), ("snap", "Snap")):
        src = sources.get(key, {}) if isinstance(sources.get(key), dict) else {}
        status = src.get("status")
        if status == "disabled":
            pieces.append(f"{label}: " + ("off" if english else "aus"))
        elif status == "ok":
            pieces.append(f"{src.get('backend') or label}: {int(src.get('count') or 0)}")
        elif status in ("unsupported", "error"):
            partial = True
            pieces.append(f"{label}: " + ("unavailable" if english else "nicht verfügbar"))

    checked = int(result.get("checked_at", 0) or 0)
    if checked:
        try:
            pieces.append(("checked " if english else "geprüft ") + datetime.fromtimestamp(checked).strftime("%H:%M"))
        except Exception:
            pass
    if policy.get("skipped_low_memory"):
        partial = True
        pieces.append("skipped: low memory" if english else "übersprungen: wenig freier RAM")

    return {
        "key": "updates",
        "label": "Updates",
        "value": "--" if total is None else str(total),
        "state": "warning" if partial else "ok",
        "details": " · ".join(pieces),
    }
'''
write("files/bin/dielage_updates.py", updates_module)


# ---------------------------------------------------------------------------
# Cache helper integration + version/default synchronization
# ---------------------------------------------------------------------------
cache_path = "files/bin/dielage-cache.py"
cache = read(cache_path)
cache = cache.replace("2.1.8", VERSION)
cache = replace_regex_once(
    cache,
    r"DEFAULT_CONFIG = \{.*?\}\n\nFALLBACK_DEFAULT_CONFIG",
    "DEFAULT_CONFIG = " + pretty_defaults + "\n\nFALLBACK_DEFAULT_CONFIG",
    "cache inline defaults",
    re.S,
)
anchor = 'SAFE_SUBPROCESS_ENV = {**os.environ, "PATH": SAFE_SUBPROCESS_PATH}\n'
loader = '''SAFE_SUBPROCESS_ENV = {**os.environ, "PATH": SAFE_SUBPROCESS_PATH}\n\n\ndef _load_update_checker():\n    path = Path(__file__).with_name("dielage_updates.py")\n    try:\n        spec = __import__("importlib.util", fromlist=["util"]).spec_from_file_location("dielage_updates", path)\n        if spec is None or spec.loader is None:\n            return None\n        module = __import__("importlib.util", fromlist=["util"]).module_from_spec(spec)\n        spec.loader.exec_module(module)\n        return module\n    except Exception:\n        return None\n\n\nUPDATE_CHECKER = _load_update_checker()\n'''
cache = replace_once(cache, anchor, loader, "cache update module loader")
old_update_block = '''    if show_updates:\n        updates, source = updates_available()\n        item = {"key": "updates", "label": labels["updates"], "value": updates}\n        if source:\n            item["source"] = source\n        items.append(item)\n\n    return {\n        "updated": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),\n        "items": items,\n        "errors": [],\n        "enabled": True,\n    }'''
new_update_block = '''    update_policy = {}\n    if show_updates:\n        if UPDATE_CHECKER is not None:\n            try:\n                result = UPDATE_CHECKER.check_updates(cfg, force=manual_refresh())\n                item = UPDATE_CHECKER.as_system_item(result, english=english)\n                item["label"] = labels["updates"]\n                items.append(item)\n                update_policy = result.get("policy", {}) if isinstance(result, dict) else {}\n            except Exception as exc:\n                items.append({"key": "updates", "label": labels["updates"], "value": "--",\n                              "state": "warning", "details": f"{type(exc).__name__}"})\n        else:\n            # Packaging error fallback: preserve the old read-only native\n            # checker rather than breaking the entire System block.\n            updates, source = updates_available()\n            item = {"key": "updates", "label": labels["updates"], "value": updates}\n            if source:\n                item["source"] = source\n            items.append(item)\n\n    return {\n        "updated": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),\n        "items": items,\n        "errors": [],\n        "enabled": True,\n        "update_policy": update_policy,\n    }'''
cache = replace_once(cache, old_update_block, new_update_block, "cache fetch_system_info integration")
write(cache_path, cache)


# ---------------------------------------------------------------------------
# Local server: defaults, version and cache clearing
# ---------------------------------------------------------------------------
server_path = "files/bin/dielage-server.py"
server = read(server_path).replace("2.1.8", VERSION)
server = replace_regex_once(
    server,
    r"DEFAULT_CONFIG = \{.*?\}\n\nINDEX_SYMBOL_ALIASES",
    "DEFAULT_CONFIG = " + pretty_defaults + "\n\nINDEX_SYMBOL_ALIASES",
    "server inline defaults",
    re.S,
)
old_clear = '''        if path.name in ("rss.json", "feedstate.json") or path.name.startswith(("rss.json.tmp.", "feedstate.json.tmp.")):\n'''
new_clear = '''        if path.name in ("rss.json", "feedstate.json", "updates.json") or path.name.startswith(("rss.json.tmp.", "feedstate.json.tmp.", "updates.json.tmp.")):\n'''
server = replace_once(server, old_clear, new_clear, "server clear-cache update state")
write(server_path, server)


# ---------------------------------------------------------------------------
# Installer / uninstaller + wider distro hint detection
# ---------------------------------------------------------------------------
install = read("install.sh")
install = replace_once(
    install,
    'install -m 0755 "$BASE_DIR/files/bin/dielage-cache.py"        "$HOME/.local/bin/dielage-cache.py"\n',
    'install -m 0755 "$BASE_DIR/files/bin/dielage-cache.py"        "$HOME/.local/bin/dielage-cache.py"\n'
    'install -m 0644 "$BASE_DIR/files/bin/dielage_updates.py"      "$HOME/.local/bin/dielage_updates.py"\n',
    "installer update helper",
)
# Extend installer family labels only for package suggestions. Install behaviour
# remains user-local and identical on every distro.
install = replace_once(
    install,
    '        opensuse*|sles|tumbleweed) echo "suse"; return ;;\n',
    '        opensuse*|sles|tumbleweed) echo "suse"; return ;;\n'
    '        alpine) echo "alpine"; return ;;\n'
    '        void) echo "void"; return ;;\n'
    '        solus) echo "solus"; return ;;\n'
    '        gentoo) echo "gentoo"; return ;;\n',
    "installer distro family ids",
)
install = replace_once(
    install,
    '        *" suse "*|*" opensuse "*) echo "suse"; return ;;\n',
    '        *" suse "*|*" opensuse "*) echo "suse"; return ;;\n'
    '        *" alpine "*) echo "alpine"; return ;;\n'
    '        *" void "*) echo "void"; return ;;\n'
    '        *" gentoo "*) echo "gentoo"; return ;;\n',
    "installer distro family id_like",
)
install = replace_once(
    install,
    '        suse)   echo "sudo zypper install $pkgs" ;;\n        *)      echo "(manuell installieren: $pkgs)" ;;\n',
    '        suse)   echo "sudo zypper install $pkgs" ;;\n'
    '        alpine) echo "sudo apk add $pkgs" ;;\n'
    '        void)   echo "sudo xbps-install -S $pkgs" ;;\n'
    '        solus)  echo "sudo eopkg install $pkgs" ;;\n'
    '        gentoo) echo "sudo emerge --ask $pkgs" ;;\n'
    '        *)      echo "(manuell installieren: $pkgs)" ;;\n',
    "installer install hints",
)
write("install.sh", install)

uninstall = read("uninstall.sh")
uninstall = replace_once(
    uninstall,
    'rm -f "$HOME/.local/bin/dielage-cache.py"\nrm -f "$HOME/.local/bin/dielage-server.py"\n',
    'rm -f "$HOME/.local/bin/dielage-cache.py"\nrm -f "$HOME/.local/bin/dielage_updates.py"\nrm -f "$HOME/.local/bin/dielage-server.py"\n',
    "uninstaller update helper",
)
write("uninstall.sh", uninstall)


# ---------------------------------------------------------------------------
# QML: explicit sources, independent interval, low-memory warning
# ---------------------------------------------------------------------------
qml_path = "files/plasmoid/contents/ui/main.qml"
qml = read(qml_path).replace('readonly property string appVersion: "2.1.8"', f'readonly property string appVersion: "{VERSION}"')
qml = replace_once(
    qml,
    '    property bool showSystemUpdates: true\n',
    '    property bool showSystemUpdates: true\n'
    '    property bool systemUpdateCheckNative: true\n'
    '    property bool systemUpdateCheckFlatpak: false\n'
    '    property bool systemUpdateCheckSnap: false\n'
    '    property string systemUpdateIntervalMinutes: "60"\n'
    '    property bool systemUpdateLowMemoryProtection: true\n',
    "qml update properties",
)
qml = replace_once(
    qml,
    '            "showSystemUpdates": "Show available updates",\n',
    '            "showSystemUpdates": "Show available updates",\n'
    '            "updateSources": "Update checks",\n'
    '            "checkNativeUpdates": "System packages (APT, Pacman, DNF, Zypper, APK, …)",\n'
    '            "checkFlatpakUpdates": "Flatpak updates",\n'
    '            "checkSnapUpdates": "Snap updates",\n'
    '            "updateCheckInterval": "Update-check interval (minutes)",\n'
    '            "updateCheckIntervalHelp": "Independent of the normal System interval. Default: 60 minutes; allowed: 10–1440. A manual System/global refresh may check immediately.",\n'
    '            "updateHeavyHelp": "Flatpak and Snap are optional and off by default. Package sources are checked sequentially, never in parallel, and no package is installed or metadata refresh forced.",\n'
    '            "updateLowMemoryProtection": "Skip package checks when free memory is low",\n'
    '            "updateLowMemoryHelp": "When enabled, a due update check is postponed if less than about 1 GiB RAM is currently available. The previous result remains visible.",\n'
    '            "updateLowMemoryWarning": "Low-memory system: optional package checks can temporarily use several hundred MiB. Leave Flatpak/Snap off unless you want them enabled.",\n'
    '            "updateLowMemorySkipped": "The last due update check was postponed because little RAM was available.",\n',
    "qml english update translations",
)
qml = replace_once(
    qml,
    '            "showSystemUpdates": "Verfügbare Updates anzeigen",\n',
    '            "showSystemUpdates": "Verfügbare Updates anzeigen",\n'
    '            "updateSources": "Update-Prüfung",\n'
    '            "checkNativeUpdates": "Systempakete (APT, Pacman, DNF, Zypper, APK, …)",\n'
    '            "checkFlatpakUpdates": "Flatpak-Updates",\n'
    '            "checkSnapUpdates": "Snap-Updates",\n'
    '            "updateCheckInterval": "Intervall der Update-Prüfung (Minuten)",\n'
    '            "updateCheckIntervalHelp": "Unabhängig vom normalen System-Intervall. Standard: 60 Minuten; erlaubt: 10–1440. Eine manuelle System-/Gesamtaktualisierung kann sofort prüfen.",\n'
    '            "updateHeavyHelp": "Flatpak und Snap sind optional und standardmäßig aus. Paketquellen werden nacheinander geprüft, nie parallel; es werden keine Pakete installiert und keine Metadaten-Aktualisierung erzwungen.",\n'
    '            "updateLowMemoryProtection": "Paketprüfung bei wenig freiem RAM auslassen",\n'
    '            "updateLowMemoryHelp": "Wenn aktiv, wird eine fällige Update-Prüfung verschoben, sobald aktuell weniger als etwa 1 GiB RAM verfügbar ist. Das bisherige Ergebnis bleibt sichtbar.",\n'
    '            "updateLowMemoryWarning": "System mit wenig Arbeitsspeicher: Optionale Paketprüfungen können kurzfristig mehrere hundert MiB benötigen. Flatpak/Snap nur aktivieren, wenn Sie das möchten.",\n'
    '            "updateLowMemorySkipped": "Die letzte fällige Update-Prüfung wurde wegen wenig freien Arbeitsspeichers verschoben.",\n',
    "qml german update translations",
)
qml = replace_once(
    qml,
    '        root.showSystemUpdates = !(data.system && data.system.show_updates === false)\n',
    '        root.showSystemUpdates = !(data.system && data.system.show_updates === false)\n'
    '        root.systemUpdateCheckNative = !(data.system && data.system.updates_check_native === false)\n'
    '        root.systemUpdateCheckFlatpak = Boolean(data.system && data.system.updates_check_flatpak === true)\n'
    '        root.systemUpdateCheckSnap = Boolean(data.system && data.system.updates_check_snap === true)\n'
    '        root.systemUpdateIntervalMinutes = String(data.system && data.system.updates_interval_minutes !== undefined ? data.system.updates_interval_minutes : 60)\n'
    '        root.systemUpdateLowMemoryProtection = !(data.system && data.system.updates_low_memory_protection === false)\n',
    "qml load update config",
)
qml = replace_once(
    qml,
    '                "show_updates": root.showSystemUpdates\n',
    '                "show_updates": root.showSystemUpdates,\n'
    '                "updates_check_native": root.systemUpdateCheckNative,\n'
    '                "updates_check_flatpak": root.systemUpdateCheckFlatpak,\n'
    '                "updates_check_snap": root.systemUpdateCheckSnap,\n'
    '                "updates_interval_minutes": root.clampInt(root.systemUpdateIntervalMinutes, 60, 10, 1440),\n'
    '                "updates_low_memory_protection": root.systemUpdateLowMemoryProtection\n',
    "qml save update config",
)
# Add helpers beside systemItems().
qml = replace_once(
    qml,
    '''    function systemItems() {\n        if (!root.rssData || !root.rssData.system || !root.rssData.system.items) {\n            return []\n        }\n        return root.rssData.system.items\n    }\n''',
    '''    function systemItems() {\n        if (!root.rssData || !root.rssData.system || !root.rssData.system.items) {\n            return []\n        }\n        return root.rssData.system.items\n    }\n\n    function systemUpdatePolicy() {\n        var p = root.rssData && root.rssData.system ? root.rssData.system.update_policy : null\n        return (p && typeof p === "object") ? p : ({})\n    }\n\n    function systemUpdateMemoryText() {\n        var p = root.systemUpdatePolicy()\n        var mem = p.memory || {}\n        var total = Number(mem.total_mib || 0)\n        var available = Number(mem.available_mib || 0)\n        var suffix = ""\n        if (total > 0) {\n            suffix = " (" + (total / 1024.0).toFixed(total < 10240 ? 1 : 0) + " GiB RAM"\n            if (available > 0) suffix += ", " + (available / 1024.0).toFixed(1) + " GiB " + (root.isEnglish() ? "available" : "frei")\n            suffix += ")"\n        }\n        if (p.skipped_low_memory === true) return root.t("updateLowMemorySkipped") + suffix\n        if (p.low_total_memory === true) return root.t("updateLowMemoryWarning") + suffix\n        return ""\n    }\n''',
    "qml update policy helpers",
)
# Insert the update settings after the existing top-level System checkboxes.
settings_anchor = '''                                }\n\n                                ColumnLayout {\n                                    Layout.fillWidth: true\n                                    Layout.minimumWidth: 0\n                                    spacing: Kirigami.Units.smallSpacing\n\n                                    PlasmaComponents3.Label {\n                                        text: root.t("systemInterval")\n'''
settings_new = '''                                }\n\n                                ColumnLayout {\n                                    visible: root.showSystem && root.showSystemUpdates\n                                    Layout.fillWidth: true\n                                    Layout.minimumWidth: 0\n                                    spacing: Kirigami.Units.smallSpacing\n\n                                    PlasmaComponents3.Label {\n                                        text: root.t("updateSources")\n                                        font.bold: true\n                                        font.pixelSize: root.smallSize\n                                    }\n\n                                    QQC2.CheckBox {\n                                        text: root.t("checkNativeUpdates")\n                                        checked: root.systemUpdateCheckNative\n                                        font.pixelSize: root.smallSize\n                                        onToggled: root.systemUpdateCheckNative = checked\n                                    }\n                                    QQC2.CheckBox {\n                                        text: root.t("checkFlatpakUpdates")\n                                        checked: root.systemUpdateCheckFlatpak\n                                        font.pixelSize: root.smallSize\n                                        onToggled: root.systemUpdateCheckFlatpak = checked\n                                    }\n                                    QQC2.CheckBox {\n                                        text: root.t("checkSnapUpdates")\n                                        checked: root.systemUpdateCheckSnap\n                                        font.pixelSize: root.smallSize\n                                        onToggled: root.systemUpdateCheckSnap = checked\n                                    }\n\n                                    PlasmaComponents3.Label {\n                                        Layout.fillWidth: true\n                                        Layout.minimumWidth: 0\n                                        text: root.t("updateHeavyHelp")\n                                        opacity: 0.70\n                                        font.pixelSize: Math.max(9, root.smallSize - 1)\n                                        wrapMode: Text.WordWrap\n                                        elide: Text.ElideNone\n                                    }\n\n                                    RowLayout {\n                                        Layout.fillWidth: true\n                                        Layout.minimumWidth: 0\n                                        spacing: Kirigami.Units.largeSpacing\n                                        ColumnLayout {\n                                            PlasmaComponents3.Label { text: root.t("updateCheckInterval"); font.pixelSize: root.smallSize }\n                                            QQC2.TextField {\n                                                Layout.preferredWidth: 150\n                                                text: root.systemUpdateIntervalMinutes\n                                                placeholderText: "60"\n                                                inputMethodHints: Qt.ImhDigitsOnly\n                                                font.pixelSize: root.smallSize\n                                                onTextChanged: root.systemUpdateIntervalMinutes = text\n                                            }\n                                        }\n                                        PlasmaComponents3.Label {\n                                            Layout.fillWidth: true\n                                            Layout.minimumWidth: 0\n                                            text: root.t("updateCheckIntervalHelp")\n                                            opacity: 0.68\n                                            font.pixelSize: Math.max(9, root.smallSize - 1)\n                                            wrapMode: Text.WordWrap\n                                            elide: Text.ElideNone\n                                        }\n                                    }\n\n                                    QQC2.CheckBox {\n                                        text: root.t("updateLowMemoryProtection")\n                                        checked: root.systemUpdateLowMemoryProtection\n                                        font.pixelSize: root.smallSize\n                                        onToggled: root.systemUpdateLowMemoryProtection = checked\n                                    }\n                                    PlasmaComponents3.Label {\n                                        Layout.fillWidth: true\n                                        Layout.minimumWidth: 0\n                                        text: root.t("updateLowMemoryHelp")\n                                        opacity: 0.68\n                                        font.pixelSize: Math.max(9, root.smallSize - 1)\n                                        wrapMode: Text.WordWrap\n                                        elide: Text.ElideNone\n                                    }\n                                    Rectangle {\n                                        visible: root.systemUpdateMemoryText().length > 0\n                                        Layout.fillWidth: true\n                                        Layout.minimumWidth: 0\n                                        color: Kirigami.Theme.backgroundColor\n                                        border.color: Kirigami.Theme.neutralTextColor\n                                        border.width: 1\n                                        radius: 6\n                                        implicitHeight: updateMemoryWarningLabel.implicitHeight + Kirigami.Units.largeSpacing * 2\n                                        PlasmaComponents3.Label {\n                                            id: updateMemoryWarningLabel\n                                            anchors.fill: parent\n                                            anchors.margins: Kirigami.Units.largeSpacing\n                                            text: root.systemUpdateMemoryText()\n                                            color: Kirigami.Theme.neutralTextColor\n                                            font.pixelSize: Math.max(9, root.smallSize - 1)\n                                            wrapMode: Text.WordWrap\n                                            elide: Text.ElideNone\n                                        }\n                                    }\n                                }\n\n                                ColumnLayout {\n                                    Layout.fillWidth: true\n                                    Layout.minimumWidth: 0\n                                    spacing: Kirigami.Units.smallSpacing\n\n                                    PlasmaComponents3.Label {\n                                        text: root.t("systemInterval")\n'''
qml = replace_once(qml, settings_anchor, settings_new, "qml system update settings section")
# Expose source details on the update value tile.
old_value = '''                                        PlasmaComponents3.Label {\n                                            Layout.fillWidth: true\n                                            Layout.minimumWidth: 0\n                                            text: sys.value || "--"\n                                            textFormat: Text.PlainText\n                                            font.pixelSize: root.smallSize\n                                            font.bold: true\n                                            color: root.systemValueColor(sys)\n                                            elide: Text.ElideRight\n                                        }'''
new_value = '''                                        PlasmaComponents3.Label {\n                                            Layout.fillWidth: true\n                                            Layout.minimumWidth: 0\n                                            text: sys.value || "--"\n                                            textFormat: Text.PlainText\n                                            font.pixelSize: root.smallSize\n                                            font.bold: true\n                                            color: root.systemValueColor(sys)\n                                            elide: Text.ElideRight\n                                            QQC2.ToolTip.visible: updateDetailsHover.hovered && Boolean(sys.details)\n                                            QQC2.ToolTip.delay: 500\n                                            QQC2.ToolTip.text: sys.details ? String(sys.details) : ""\n                                            HoverHandler { id: updateDetailsHover }\n                                        }'''
qml = replace_once(qml, old_value, new_value, "qml update source tooltip")
write(qml_path, qml)


# ---------------------------------------------------------------------------
# Metadata / changelog / publishing
# ---------------------------------------------------------------------------
metadata_path = ROOT / "files/plasmoid/metadata.json"
metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
metadata["KPlugin"]["Version"] = VERSION
metadata["Version"] = VERSION
metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

appdata = read("files/plasmoid/metadata.appdata.xml")
release_xml = f'''    <release version="{VERSION}" date="{DATE}">\n      <description>\n        <p>Separates Linux update checks from the normal System refresh, adds explicit native/Flatpak/Snap controls and a configurable interval, broadens native package-manager support, and prevents memory pressure from optional update queries. Cache refresh services now have a realistic 768 MiB safety ceiling.</p>\n        <p xml:lang="de">Entkoppelt Linux-Update-Prüfungen vom normalen System-Refresh, ergänzt getrennte Schalter für Systempakete/Flatpak/Snap und ein eigenes Intervall, erweitert die Paketmanager-Unterstützung und schützt Systeme mit wenig freiem RAM. Die Cache-Dienste erhalten zudem eine realistische Sicherheitsgrenze von 768 MiB.</p>\n      </description>\n    </release>\n'''
appdata = replace_once(appdata, "  <releases>\n", "  <releases>\n" + release_xml, "AppStream release insertion")
write("files/plasmoid/metadata.appdata.xml", appdata)

changelog = read("CHANGELOG.md")
entry = f'''# Die Lage Changelog\n\n## v{VERSION}\n\nCross-distribution update-check and memory-safety release.\n\n- Fixed a reproducible cgroup OOM: Flatpak could push `dielage-cache.service` beyond its old 256 MiB limit. Cache and boot-refresh services now use a 768 MiB ceiling; the lightweight local server stays at 256 MiB.\n- Update checks now have their own interval (default 60 minutes) and no longer run whenever the normal System block refreshes.\n- Added explicit switches for native system packages, Flatpak and Snap. Native checks are enabled by default; Flatpak and Snap are opt-in and run sequentially.\n- Added read-only native update detection for Debian/Ubuntu (`apt`), Arch derivatives (`checkupdates`/`pacman`), Fedora/RHEL derivatives (`dnf5`/`dnf`), openSUSE (`zypper`), Alpine (`apk`), Void (`xbps`), Solus (`eopkg`), Gentoo (`emerge`) and rpm-ostree systems, with PackageKit as a generic fallback. Unknown distributions degrade to an unavailable status instead of failing the System block.\n- Added low-memory protection: when less than about 1 GiB RAM is currently available, a due package check can be postponed while the last successful result remains visible. Systems below 4 GiB total RAM show an in-settings warning before optional Flatpak/Snap checks are enabled.\n- Update checks never install packages and never force a package-metadata refresh.\n\n'''
if not changelog.startswith("# Die Lage Changelog\n\n"):
    raise SystemExit("unexpected CHANGELOG header")
changelog = entry + changelog[len("# Die Lage Changelog\n\n"):]
write("CHANGELOG.md", changelog)

publishing = read("PUBLISHING.md").replace("2.1.8", VERSION)
write("PUBLISHING.md", publishing)


# ---------------------------------------------------------------------------
# Tests for update checker
# ---------------------------------------------------------------------------
update_tests = r'''#!/usr/bin/env python3
from __future__ import annotations
import importlib.util
import pathlib
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
SPEC = importlib.util.spec_from_file_location("du", ROOT / "files/bin/dielage_updates.py")
du = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(du)

failures = []
def check(name, condition):
    print(("    ok   " if condition else "    FAIL ") + name)
    if not condition:
        failures.append(name)

orig_os = du._read_os_release
orig_which = du.shutil.which
try:
    cases = [
        ({"ID": "ubuntu", "ID_LIKE": "debian"}, {"apt-get"}, "apt"),
        ({"ID": "cachyos", "ID_LIKE": "arch"}, {"pacman"}, "pacman"),
        ({"ID": "fedora"}, {"dnf5"}, "dnf"),
        ({"ID": "opensuse-tumbleweed", "ID_LIKE": "suse"}, {"zypper"}, "zypper"),
        ({"ID": "alpine"}, {"apk"}, "apk"),
        ({"ID": "void"}, {"xbps-install"}, "xbps"),
        ({"ID": "solus"}, {"eopkg"}, "eopkg"),
        ({"ID": "gentoo"}, {"emerge"}, "emerge"),
        ({"ID": "fedora", "VARIANT_ID": "kinoite"}, {"rpm-ostree"}, "rpm-ostree"),
    ]
    for info, commands, expected in cases:
        du._read_os_release = lambda info=info: info
        du.shutil.which = lambda name, path=None, commands=commands: f"/usr/bin/{name}" if name in commands else None
        check(f"native backend {info.get('ID')} -> {expected}", du.native_backend() == expected)
finally:
    du._read_os_release = orig_os
    du.shutil.which = orig_which

with tempfile.TemporaryDirectory() as tmp:
    du.STATE_FILE = pathlib.Path(tmp) / "updates.json"
    calls = []
    old_native, old_flatpak, old_snap = du.check_native, du.check_flatpak, du.check_snap
    old_mem = du.memory_snapshot
    try:
        du.memory_snapshot = lambda: {"total_mib": 32768, "available_mib": 16000, "swap_free_mib": 512}
        du.check_native = lambda: (calls.append("native") or du._result("ok", 2, "APT"))
        du.check_flatpak = lambda: (calls.append("flatpak") or du._result("ok", 3, "Flatpak"))
        du.check_snap = lambda: (calls.append("snap") or du._result("ok", 1, "Snap"))
        cfg = {"updates_check_native": True, "updates_check_flatpak": True, "updates_check_snap": True,
               "updates_interval_minutes": 60, "updates_low_memory_protection": True}
        first = du.check_updates(cfg)
        check("enabled sources run sequentially", calls == ["native", "flatpak", "snap"])
        check("source counts are summed", first.get("total") == 6)
        calls.clear()
        second = du.check_updates(cfg)
        check("cached interval avoids package-manager calls", calls == [] and second.get("total") == 6)

        # Changing a source setting invalidates the cache immediately.
        cfg2 = dict(cfg); cfg2["updates_check_snap"] = False
        du.check_updates(cfg2)
        check("source-setting change forces one new check", calls == ["native", "flatpak"])

        calls.clear()
        du.memory_snapshot = lambda: {"total_mib": 3072, "available_mib": 500, "swap_free_mib": 0}
        # Force makes the check due but must not override memory protection.
        low = du.check_updates(cfg2, force=True)
        check("low-memory protection skips external checks", calls == [] and low["policy"]["skipped_low_memory"] is True)
        check("low-memory skip preserves previous count", low.get("total") == 5)
        check("low-total-memory warning is exposed", low["policy"]["low_total_memory"] is True)
    finally:
        du.check_native, du.check_flatpak, du.check_snap = old_native, old_flatpak, old_snap
        du.memory_snapshot = old_mem

if failures:
    raise SystemExit("FAILED: " + ", ".join(failures))
print("All update-check tests passed.")
'''
write("tests/update_checks.py", update_tests)


# ---------------------------------------------------------------------------
# Release checker v2.1.9
# ---------------------------------------------------------------------------
old_checker = ROOT / "release-checks-v2.1.8.sh"
new_checker = ROOT / f"release-checks-v{VERSION}.sh"
checker = old_checker.read_text(encoding="utf-8").replace("2.1.8", VERSION).replace("2026-09-20", DATE)
old_hardening = '''for path in cache_services + [server]:\n    text = path.read_text(encoding="utf-8")\n    for required in ("UMask=0077", "NoNewPrivileges=yes", "PrivateTmp=yes",\n                     "RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX",\n                     "MemoryMax=256M", "TasksMax=64"):\n        assert required in text, f"{path}: missing {required}"\nfor path in cache_services:\n    assert "SuccessExitStatus=75" in path.read_text(encoding="utf-8"), f"{path}: lock exit not accepted"\nassert "Restart=on-failure" in server.read_text(encoding="utf-8")\n'''
new_hardening = '''for path in cache_services + [server]:\n    text = path.read_text(encoding="utf-8")\n    for required in ("UMask=0077", "NoNewPrivileges=yes", "PrivateTmp=yes",\n                     "RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX", "TasksMax=64"):\n        assert required in text, f"{path}: missing {required}"\nfor path in cache_services:\n    text = path.read_text(encoding="utf-8")\n    assert "MemoryMax=768M" in text, f"{path}: cache memory ceiling is not 768M"\n    assert "SuccessExitStatus=75" in text, f"{path}: lock exit not accepted"\nassert "MemoryMax=256M" in server.read_text(encoding="utf-8"), "local server should keep its smaller 256M ceiling"\nassert "Restart=on-failure" in server.read_text(encoding="utf-8")\n'''
checker = replace_once(checker, old_hardening, new_hardening, "release checker systemd hardening")
checker = replace_once(
    checker,
    'python3 tests/regression.py || fail "regression tests"\nok "regression suite green"\n',
    'python3 tests/regression.py || fail "regression tests"\n'
    'python3 tests/update_checks.py || fail "cross-distro update-check tests"\n'
    'ok "regression and update-check suites green"\n',
    "release checker update tests",
)
checker = replace_once(
    checker,
    'for name in ("files/bin/dielage-cache.py", "files/bin/dielage-server.py", "tests/regression.py"):\n',
    'for name in ("files/bin/dielage-cache.py", "files/bin/dielage_updates.py", "files/bin/dielage-server.py", "tests/regression.py", "tests/update_checks.py"):\n',
    "release checker Python syntax list",
)
checker = replace_once(
    checker,
    'for f in files/bin/dielage-cache.py files/bin/dielage-server.py \\\n',
    'for f in files/bin/dielage-cache.py files/bin/dielage_updates.py files/bin/dielage-server.py \\\n',
    "release checker required files",
)
# Release-specific sanity: settings/defaults and memory guard are part of the contract.
marker = 'ok "OpenWeather success text, subtle attribution, refresh spinners and RSS age scale are wired"\n'
extra = '''ok "OpenWeather success text, subtle attribution, refresh spinners and RSS age scale are wired"\n\necho "-- v2.1.9 update-check safety --"\npython3 - <<'PY' || fail "v2.1.9 update-check wiring"\nimport json, pathlib\ncfg = json.loads(pathlib.Path("files/config/default-config.json").read_text(encoding="utf-8"))\ns = cfg["system"]\nassert s["updates_check_native"] is True\nassert s["updates_check_flatpak"] is False\nassert s["updates_check_snap"] is False\nassert s["updates_interval_minutes"] == 60\nassert s["updates_low_memory_protection"] is True\nupdates = pathlib.Path("files/bin/dielage_updates.py").read_text(encoding="utf-8")\nfor token in ("apt-get", "pacman", "dnf5", "zypper", "apk", "xbps-install", "eopkg", "emerge", "rpm-ostree", "pkcon", "flatpak", "snap"):\n    assert token in updates, token\nassert "LOW_MEMORY_SKIP_MIB = 1024" in updates\nqml = pathlib.Path("files/plasmoid/contents/ui/main.qml").read_text(encoding="utf-8")\nfor token in ("systemUpdateCheckNative", "systemUpdateCheckFlatpak", "systemUpdateCheckSnap", "systemUpdateIntervalMinutes", "systemUpdateLowMemoryProtection"):\n    assert token in qml, token\nPY\nok "cross-distro sources, opt-in Flatpak/Snap, independent interval and memory guard are wired"\n'''
checker = replace_once(checker, marker, extra, "release checker v2.1.9 sanity")
new_checker.write_text(checker, encoding="utf-8")
new_checker.chmod(0o755)
old_checker.unlink()

# Update README minimally without turning it into a release dump.
readme = read("README.md")
needle = "## Installation"
if needle in readme and "Flatpak/Snap update checks" not in readme:
    note = ("## Update checks\n\n"
            "The System block can check the distribution's native package manager and, optionally, Flatpak and Snap. "
            "Native checks support common Debian/Ubuntu, Arch, Fedora/RHEL, openSUSE, Alpine, Void, Solus, Gentoo and rpm-ostree systems, with PackageKit as a fallback. "
            "Checks are read-only, separately rate-limited and protected against low-memory conditions. Flatpak and Snap are opt-in.\n\n")
    readme = readme.replace(needle, note + needle, 1)
write("README.md", readme)

print("Prepared Die Lage v2.1.9 update-check and memory-safety patch.")
