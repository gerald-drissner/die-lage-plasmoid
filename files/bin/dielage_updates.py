#!/usr/bin/env python3
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
