# Changelog

## v1.60.5 — first public release candidate

This is the first intended public release of **Die Lage (Daily Briefing)**. Earlier version numbers were local development builds.

### Highlights

- KDE Plasma 6 widget for desktop and panel use.
- Compact situation board with RSS news, weather, official warnings, Islamic prayer times, markets and Linux system status.
- Best suited for a portrait-oriented second or third screen with a dark or black desktop background.
- Panel popup support with configurable popup width.
- Collapsible blocks and configurable block order.
- German and English interface.
- Local Python helper service and systemd user units for background fetching.
- AppStream metadata, screenshots and KDE Store text prepared.

### Important installation note

The KDE Store `.plasmoid` installs only the visible Plasma widget. The widget also needs the full installer bundle to set up the local helper service and systemd user units. Download the full release ZIP and run `./install.sh` once.
