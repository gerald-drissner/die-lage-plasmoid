# KDE Store text — Die Lage v1.60.7

## Title
Die Lage

## Category
Linux/Unix Desktops → Desktop Extensions → KDE Plasma Extensions → Plasma 6 Extensions → Plasma 6 Applets

## Short description
Die Lage (Daily Briefing): compact current-affairs board for KDE Plasma.

## Product description
Die Lage (Daily Briefing) is a KDE Plasma widget for a compact current-affairs board with RSS news, weather, public warnings, Islamic prayer times, markets and system status.

Important: The KDE Store installation alone is not enough. The .plasmoid file installs only the visible Plasma widget. To actually load RSS news, weather, public warnings, markets, prayer times and system status, Die Lage also needs its local Python helper and systemd user services.

These helper scripts and service files are already included in the full installer ZIP. They only need to be installed and activated manually once. This is done with a few terminal commands. This requires a Linux system with systemd user services, which is the default on most mainstream KDE Plasma distributions.

Direct download of the full installer ZIP:
https://github.com/gerald-drissner/die-lage-plasmoid/releases/latest/download/die-lage-latest.zip

After downloading the ZIP, run these commands in a terminal:

1. cd ~/Downloads
2. unzip -o die-lage-latest.zip
3. cd die-lage-latest
4. chmod +x install.sh uninstall.sh emergency-clean-dielage.sh
5. ./install.sh
6. systemctl --user restart plasma-plasmashell.service

Compatibility note:

Die Lage is intended for KDE Plasma 6 on Linux systems with systemd user services. This includes common Plasma distributions such as Arch, EndeavourOS, CachyOS, Kubuntu/Ubuntu, Debian, Fedora and openSUSE.

Systems without systemd are not officially supported. The visible Plasma widget may install, but the local helper service and automatic updates require systemctl --user and systemd user timers.

Uninstall:

The widget can be removed from Plasma like any other Plasma widget. However, Plasma does not reliably remove the local helper scripts, cache files or systemd user services. For a clean uninstall, run:

dielage-uninstall

For a complete removal including configuration and cache, run:

dielage-uninstall --purge

If the command is not in your PATH, use:

~/.local/bin/dielage-uninstall --purge

The German phrase "Die Lage" means roughly "the situation" or "the current state of affairs". It is pronounced roughly "dee LAH-guh" in English. In German journalism, the phrase points to the daily editorial question: what is happening, what matters right now, and what needs to be kept in view.

The widget works in a Plasma panel, but it is designed to work best on a portrait-oriented second or third screen, ideally with a dark or black desktop background.

It was built as a personal replacement for a Conky dashboard, especially for a Wayland/NVIDIA Plasma setup where Conky caused recurring problems.

Features:

- RSS/news briefing with configurable sources
- Weather with local time, humidity, sunrise/sunset, wind, gusts, rain and snow
- Public warning block
- Islamic prayer times with optional upcoming/now highlighting
- Market data for exchange rates, indices and stocks
- System status block with optional VPN detection
- Desktop and panel mode
- Configurable block order, colors, fonts, panel popup width and visibility options
- German and English UI texts

Source code:
https://github.com/gerald-drissner/die-lage-plasmoid

This is a personal workflow tool shared publicly because it may be useful to other KDE Plasma users. It is not a general-purpose news portal and not a standalone application.

## Changelog field
v1.60.7

- Hardened helper-server config request parsing with clearer errors for invalid or empty JSON.
- Cache script now uses the shipped default-config.json as the primary default source.
- Twelve Data and Finnhub API keys are sent via HTTP headers instead of URL query parameters.
- Added optional defusedxml support for safer RSS/warning XML parsing.
- Fedora/RPM update checks now use dnf --cacheonly to avoid slow metadata refreshes.
- Normal install/uninstall now clears only Die-Lage-specific Plasma/QML cache entries; the emergency cleaner remains available for full cache resets.
- Moved nested QML helper functions out of control blocks for better Qt/QML compatibility.
