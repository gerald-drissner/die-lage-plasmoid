# Die Lage

Die Lage is a KDE Plasma 6 dashboard widget for current news, weather, warnings, markets, prayer times and local system context.

The widget uses a small local helper service to fetch and cache data. This avoids doing heavy network work inside QML and keeps the visible applet responsive.

## Installation

For the complete installation, use the full release ZIP:

```bash
cd ~/Downloads
unzip -o die-lage-latest.zip
cd die-lage-latest
chmod +x install.sh uninstall.sh emergency-clean-dielage.sh
./install.sh
systemctl --user restart plasma-plasmashell.service
```

No root password is required. The helper runs as a systemd user service.

## Settings

Open the widget, go to Einstellungen → Info / Dienst.

Important service settings:

- Local helper port: configurable in the safe local range 8765–8775.
- First refresh after login/reboot: can be enabled or disabled.
- Boot/login refresh delay: default 120 seconds.
- Cache löschen: removes Die Lage cache data but keeps settings and API keys.
- Lokalen Dienst neu starten: restarts the local helper service.

## Uninstall

```bash
dielage-uninstall
# or, including configuration and cache:
dielage-uninstall --purge
```

Fallback:

```bash
~/.local/bin/dielage-uninstall --purge
```
