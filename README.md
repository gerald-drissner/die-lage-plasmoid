# Die Lage (Daily Briefing)

**Die Lage** is a KDE Plasma 6 widget for a compact current-affairs board with RSS news, weather, public warnings, Islamic prayer times, markets and Linux system status.

The German phrase **„Die Lage“** means roughly **“the situation”** or **“the current state of affairs”**. In German journalism, it points to the daily editorial question: what is happening, what matters right now, and what needs to be kept in view. The English name used inside the widget is **Daily Briefing**.

Die Lage works in a Plasma panel, but it is designed to work best on a portrait-oriented second or third screen, ideally with a dark or black desktop background.

It was built as a personal replacement for a Conky dashboard, especially for a Wayland/NVIDIA Plasma setup where Conky caused recurring problems.

![Die Lage portrait dashboard](https://drissner.media/die-lage/screenshots/die-lage-portrait-dashboard.png)

## Features

- RSS/news briefing with configurable sources
- Weather with local time, humidity, sunrise/sunset, wind, gusts, rain and snow
- Public warning block
- Islamic prayer times with optional upcoming/now highlighting
- Market data for exchange rates, indices and stocks
- Linux system status block with optional VPN detection
- Desktop and panel mode
- Configurable block order, collapsible blocks, colors, fonts and panel popup width
- German and English UI texts
- Local-only configuration stored under the user account

## Important installation note

The `.plasmoid` file installs only the visible Plasma widget.

For RSS, weather, warnings, markets and system information, Die Lage also needs a local Python helper and systemd user services. For full functionality, use the full ZIP package and run the installer once.

## Installation from GitHub release

Download `die-lage-v1.60.5.zip` from the latest release and run:

```bash
cd ~/Downloads
unzip die-lage-v1.60.5.zip
cd die-lage-v1.60.5
chmod +x install.sh uninstall.sh emergency-clean-dielage.sh
./install.sh
systemctl --user restart plasma-plasmashell.service
```

Then add **Die Lage** to the desktop or panel from Plasma's widget browser.

## KDE Store installation

The KDE Store / `.plasmoid` installation installs only the widget package. It does **not** reliably install or activate the local Python helper or systemd user units.

After installing the widget from KDE Store, download the full release ZIP from GitHub and run `./install.sh` as shown above.

## Panel use

Die Lage can be placed in a Plasma panel. In panel mode it shows a compact icon or warning status. Clicking the panel item opens the full popup view. The popup width can be configured in the widget settings.

The full dashboard layout works best on a portrait-oriented secondary screen.

## Configuration

Most settings are available inside the widget popup via **Settings**.

The local configuration file is stored here:

```text
~/.config/die-lage/config.json
```

The local cache is stored here:

```text
~/.cache/die-lage/rss.json
```

Optional API keys for market providers are stored only in the local user configuration file.

## Helper service

The local helper runs as a systemd user service and listens only on localhost:

```text
127.0.0.1:8765
```

The helper fetches external data, writes the local cache and persists configuration changes from the widget.

Check service status with:

```bash
systemctl --user status dielage-server.service --no-pager
systemctl --user status dielage-cache.timer --no-pager
curl -s http://127.0.0.1:8765/status
```

## Uninstall

To remove the widget, helper scripts and systemd user units while keeping configuration and cache:

```bash
dielage-uninstall
```

To remove everything, including configuration and cache:

```bash
dielage-uninstall --purge
```

If the command is not in `PATH`, run:

```bash
~/.local/bin/dielage-uninstall --purge
```

## Data sources

See [`SOURCES.md`](SOURCES.md) for details.

Main sources include Open-Meteo, AlAdhan, public warning services, Frankfurter, Yahoo Finance and optional market providers such as Twelve Data and Finnhub.

## Requirements

- KDE Plasma 6
- Linux with systemd user services
- Python 3.9 or newer
- Network access for RSS/weather/warning/market data

The installer stays inside the user's home directory. It does not install files under `/usr`.

## Development

Build release artifacts locally with:

```bash
./tools/build-release.sh
```

The generated files are written to `dist/`.

For release history, see [`CHANGELOG.md`](CHANGELOG.md).

## License

MIT License. See [`LICENSE`](LICENSE).

Copyright © 2026 Gerald Drißner.
