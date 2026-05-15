---
name: Bug report
about: Report a problem with Die Lage
labels: bug
---

## What happened?

Describe the problem.

## Expected behavior

What should have happened?

## Environment

- KDE Plasma version:
- Distribution:
- Wayland or X11:
- Die Lage version:
- Installed via KDE Store, GitHub ZIP, or local build:

## Logs

Please include relevant output:

```bash
systemctl --user status dielage-server.service --no-pager
systemctl --user status dielage-cache.timer --no-pager
journalctl --user -u dielage-server.service -n 100 --no-pager
journalctl --user -u dielage-cache.service -n 100 --no-pager
```

## Screenshots

Attach screenshots if the problem is visual.
