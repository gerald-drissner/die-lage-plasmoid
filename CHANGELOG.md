# Changelog

## v1.60.7

- Hardened `/config` request parsing in the local helper server: invalid or empty JSON now returns clear 400/411 errors instead of a generic 500.
- The cache script now reads `~/.config/die-lage/default-config.json` as the primary default configuration source, with an inline fallback only for broken installs.
- Optional `defusedxml` support for RSS/warning XML parsing. If `defusedxml` is installed, it is used automatically; otherwise the script falls back to Python's standard XML parser.
- Twelve Data and Finnhub API keys are now sent via provider-supported HTTP headers instead of URL query parameters.
- Fedora/RPM update checks use `dnf --cacheonly check-update` to avoid slow metadata refreshes during normal widget updates.
- The normal installer and uninstaller now clear only Die-Lage-specific Plasma/QML cache entries. The emergency cleaner still performs a full Plasma cache reset for rare broken-cache cases.
- Moved two nested QML helper functions out of loop/control blocks for better Qt/QML compatibility.

## v1.60.6

- Improved the first-run setup screen for KDE Store users.
- Added a direct download button/link for the full installer ZIP.
- The setup screen now points to the GitHub project page instead of the personal website.
- The helper installation instructions now use the stable latest-release ZIP: `die-lage-latest.zip`.
- Clarified that the KDE Store `.plasmoid` installs only the visible widget, while live data requires the included local Python helper and systemd user services.

## v1.60.5

- Final publishing polish for the first public release.
- Hardened plain-text rendering for feed/index names.
- Improved panel popup width state tracking for narrow popup layouts.
- Added clearer public release text for GitHub and KDE Store.

## v1.60.2

- Market timestamps are context-aware: same-day local values stay compact, while stale or foreign-market values keep useful date/timezone context.
- Weather details are more compact: zero values for wind, gusts, rain and snow are hidden, while temperatures remain visible.
- AppStream screenshot metadata points to public screenshot URLs.

## v1.58.8

- Added bundled Die-Lage SVG icons and separate store assets.
- Added configurable panel icon handling.
- Improved KDE Store text and publishing guidance.

## v1.58.5

- Added upcoming/now highlighting for Islamic prayer times.
- Improved weather detail ordering and display.
- Improved configuration handling and collapsible block persistence.

## v1.58.1

- Added scrollable multi-line settings fields.
- Hardened external news-link handling.
- Improved local server responses and partial config saves.

## v1.57.0

- Improved spacing, service-status feedback and VPN-status handling.
