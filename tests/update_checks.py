#!/usr/bin/env python3
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
