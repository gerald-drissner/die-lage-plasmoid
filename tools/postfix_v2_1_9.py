#!/usr/bin/env python3
from pathlib import Path

root = Path(__file__).resolve().parents[1]

def change(rel, old, new):
    p = root / rel
    text = p.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{rel}: expected one match for {old!r}, got {text.count(old)}")
    p.write_text(text.replace(old, new, 1), encoding="utf-8")

change(
    "files/systemd/dielage-local-server.service",
    "# The helper is a small JSON responder; if it ever leaks it should be capped\n# rather than taking the session down with it.\nMemoryMax=256M",
    "# The server itself is lightweight, but manual refreshes are child processes\n# in this same cgroup. Give them the same tested ceiling as timer-driven cache\n# refreshes; this is a cap, not reserved memory.\nMemoryMax=768M",
)

change(
    "release-checks-v2.1.9.sh",
    'assert "MemoryMax=256M" in server.read_text(encoding="utf-8"), "local server should keep its smaller 256M ceiling"',
    'assert "MemoryMax=768M" in server.read_text(encoding="utf-8"), "manual refresh children need the same 768M cgroup ceiling"',
)

change(
    "CHANGELOG.md",
    "Cache and boot-refresh services now use a 768 MiB ceiling; the lightweight local server stays at 256 MiB.",
    "Cache, boot-refresh and local-server services now use a 768 MiB ceiling because manual refresh workers are children of the local-server cgroup. The 768 MiB value is only a cap; it does not reserve memory.",
)

print("Applied manual-refresh cgroup safety postfix.")
