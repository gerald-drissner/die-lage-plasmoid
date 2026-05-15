# Die Lage (Daily Briefing) v1.60.5

First public release candidate. Earlier version numbers were local development builds.

**Die Lage** means roughly **“the situation”** or **“the current state of affairs”**. In German journalism, the phrase points to the daily editorial question: what is happening, what matters right now, and what needs to be kept in view. The English name used inside the widget is **Daily Briefing**.

**Die Lage** is a compact KDE Plasma 6 situation board for RSS news, weather, official warnings, Islamic prayer times, markets and Linux system status. It works on the desktop and in the panel, but it is designed especially for a portrait-oriented second or third screen with a dark or black background.

## Downloads

Please attach these files to the GitHub release:

- `die-lage-1.60.5.plasmoid` — Plasma widget package for KDE Store / local plasmoid install.
- `die-lage-v1.60.5.zip` — full installer bundle including helper service, cache fetcher and systemd user units.
- `die-lage-store-assets-v1.60.5.zip` — icon and wordmark assets for store pages.

## Installation

The `.plasmoid` alone installs only the visible widget. For live data, install the helper service as well:

```bash
cd ~/Downloads
unzip -o die-lage-v1.60.5.zip
cd die-lage-v1.60.5
chmod +x install.sh uninstall.sh emergency-clean-dielage.sh
./install.sh
systemctl --user restart plasma-plasmashell.service
```

Then add **Die Lage** to the desktop or panel.

## Deinstallation

```bash
dielage-uninstall
# complete removal including config/cache:
dielage-uninstall --purge
```

## Notes

This project started as a personal replacement for a Conky dashboard because Conky caused recurring trouble in a Wayland/NVIDIA setup. It is shared as a practical workflow tool, not as a generic everything-for-everyone dashboard.
