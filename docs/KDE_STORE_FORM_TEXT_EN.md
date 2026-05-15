# KDE Store form text — English

## Title

Die Lage (Daily Briefing)

## Short description

Compact KDE Plasma situation board: news, weather, warnings, prayer times, markets and system status.

## Description

**Die Lage** means roughly **“the situation”** or **“the current state of affairs”**. In German journalism, the phrase points to the daily editorial question: what is happening, what matters right now, and what needs to be kept in view. The English name used inside the widget is **Daily Briefing**.

Daily Briefing is a compact situation board directly on the KDE Plasma desktop or in a panel: RSS news from configurable sources, weather for multiple locations, official warnings via NINA, MeteoAlarm, GeoSphere, US NWS or custom feeds, Islamic prayer times, exchange rates, indices, stocks and optional Linux system information including network and VPN status.

I created it as my personal replacement for Conky because Conky kept causing trouble in my Wayland/NVIDIA setup. It is therefore not a generic everything-for-everyone widget, but a personal work dashboard that I am sharing for people who find this kind of setup useful. It also works well in the panel, but it is strongest on a portrait-oriented second or third monitor and looks best on a plain black desktop background.

Block order is configurable. Blocks can be collapsed and expanded. The widget supports German and English, desktop and panel mode, custom titles, font sizes, accent color, selectable panel icons and local configuration. Some parts may become separate widgets in the future; for now Daily Briefing is intentionally one combined situation board for my everyday workflow.

Important: this is not a pure QML widget. RSS, weather, warnings, markets and system status need a small local background service. The KDE Store installation installs the visible plasmoid. On first launch the widget shows a setup screen. Download the full release zip as well, unpack it and run `./install.sh` once. The service then runs as a normal systemd user service without root privileges.

## Tags

KDE, Plasma, plasmoid, widget, RSS, news, weather, warnings, NINA, MeteoAlarm, prayer times, markets, stocks, system monitor, VPN

## Installation note

The KDE Store installation installs only the Plasma widget. Live data requires the local helper service. Please download the full release ZIP from GitHub, unpack it and run `./install.sh` once.
