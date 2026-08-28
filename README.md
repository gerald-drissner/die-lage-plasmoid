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

### KDE Store updates

The KDE Store `.plasmoid` contains only the Plasma package. It cannot update the Python helper in `~/.local/bin` or the systemd user units. Die Lage compares the widget and helper versions; after a Store-only update, a mismatch notice tells the user to run the current full installer ZIP once.

## Settings

Open the widget, go to Einstellungen → Info / Dienst.

Important service settings:

- Local helper port: configurable in the safe local range 8765–8775.
- First refresh after login/reboot: can be enabled or disabled.
- Boot/login refresh delay: default 120 seconds.
- Cache löschen: removes Die Lage cache data but keeps settings and API keys.
- Lokalen Dienst neu starten: restarts the local helper service.

Appearance also includes a checkbox for the per-headline RSS publication-age labels. Their age indicator can optionally use a continuous color scale: the duration is configurable (120 minutes by default), while the newest/older colors can be overridden or left empty to follow the current Plasma/widget accent and Plasma text color. General settings offer Automatic (system language), Deutsch and English; fresh installations default to Automatic while upgrades preserve an existing manual choice.

Under Sources, Open-Meteo remains the default weather provider and needs no API key. An optional OpenWeather API key switches the weather block fully to OpenWeather; the two providers are not queried in parallel. The key can be tested directly in Settings before saving. The alternative is not presented as universally more accurate; results vary by location and situation. Provider attribution is deliberately kept out of the heading: a compact info button shows source details, while a quiet footer keeps the required provider credit visible.

## When sources fail

Die Lage keeps showing the last cached headlines when a source cannot be
reached, and tells you why in plain language rather than printing an exception
name. A warning-triangle button beside the News refresh control appears when a
source has a problem; clicking it opens the status box. "Details je Quelle"
then expands the per-source breakdown with the concrete cause and the age of
the data still on screen.

Publishers commonly refuse connections from VPN exit addresses. When several
sources fail that way while a tunnel is up, the summary says so instead of
leaving you to guess. Nothing needs to be switched off: sources that keep
failing are retried on a widening interval (5, 15, 30, 60, 120, up to 240 minutes) and a
manual refresh always retries immediately.

## Uninstall

Complete removal including settings and cache:

```bash
dielage-uninstall --purge
```

Fallbacks:

```bash
~/.local/bin/dielage-uninstall --purge
./uninstall.sh --purge
```

To remove only the widget and helper while keeping settings and cache:

```bash
dielage-uninstall
```

The interface is available in German and English. Fresh installs use Automatic (system language); users can override this at any time under General settings.
