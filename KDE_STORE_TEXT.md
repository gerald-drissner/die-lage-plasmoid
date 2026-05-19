# Die Lage

## v2.0.11 highlights

- Fixes package-update counting on Arch/CachyOS systems, especially under systemd user services.
- Uses a safer command-resolution path for Linux helper tools.
- Prevents overlapping cache refreshes when manual refresh and the background timer run at the same time.
- Keeps the v2 service/settings workflow, configurable helper port, boot-refresh controls, cache cleanup, tool checks and local cache display refresh.

## Installation note

The KDE Store plasmoid package installs the visible widget. The full installer ZIP is still needed for the local Python helper, cache refresh timers and systemd user services.
