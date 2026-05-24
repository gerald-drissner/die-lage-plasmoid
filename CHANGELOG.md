# Die Lage Changelog

## v2.0.19

- Fixes duplicate GeoSphere Austria warnings that appeared as several visually identical cards when the provider split one warning into consecutive daily slices.
- Merges identical GeoSphere warning entries by source area, location, warning type, warning level, title and description, keeping the latest expiry time.
- Keeps NINA, MeteoAlarm, NWS and custom feed behavior unchanged.

## v2.0.18

- Restores the cleaner KDE/theme refresh icon for the top refresh action and per-block refresh controls.
- Keeps refresh icons visible while a refresh is running by avoiding the theme's disabled-icon rendering state.
- Keeps the compact icon-only layout introduced in v2.0.16/v2.0.17.
- No backend, cache or API behavior changed.

## v2.0.18

- Adds configurable timing for Islamic prayer-time hints: minutes before a prayer time is marked as upcoming and minutes after it remains marked as Now.
- Keeps defaults at 45 minutes before and 1 minute after, matching previous behavior.
- Polishes the per-block refresh controls with a smaller, lighter refresh icon in Weather, System, Markets and News.
- Replaces the top text buttons for Aktualisieren/Refresh and Einstellungen/Settings with compact icon buttons.
- Uses a back icon while the settings view is open.
- Fixes several review findings: timeout cleanup for busy UI states, clearer helper-unreachable wording, safer Stooq fallback matching, broader dnf architecture matching, safer PackageKit update counting and more robust boot-refresh installer handling.

## v2.0.14

- Adds per-block refresh buttons to Weather, System, Markets and News.
- Keeps the global Aktualisieren/Refresh button for full updates.
- Block refreshes update only the selected block and preserve the other cached blocks.
- Does not add refresh controls to Islamic prayer times, which normally do not need manual frequent updates.

## v2.0.13

- Splits the cache refresh cadence into a main data interval and a separate System interval.
- The main interval continues to refresh RSS/news, warnings, weather, prayer times and markets.
- The new System interval refreshes Linux system, network, VPN, DNS, public-IP and update-count data more frequently without refetching all external feeds.
- Adds a System-interval setting in the System tab. Default: 3 minutes.
- Preserves old cached main-data blocks when only the System interval is due.

## v2.0.12

- Makes System-block update counting more robust across Arch/CachyOS/EndeavourOS, Debian/Ubuntu/KDE neon, Fedora/dnf5, openSUSE/zypper, PackageKit and Flatpak setups.
- Avoids returning unknown when one update tool fails but another desktop/package-manager backend can still report pending updates.
- Keeps the v2.0.11 cache-lock and HTTP-response hardening.

## v2.0.11

- Fixed package-update counting on Arch/CachyOS systems by resolving helper commands more reliably under systemd user services and preferring `checkupdates` over stale `pacman -Qu` zero results.
- Added a cache-refresh file lock so manual refreshes and systemd timer refreshes do not run the cache builder at the same time.
- Made oversized HTTP responses fail explicitly instead of silently parsing truncated data.
- Tightened one dynamic prayer-times label to render as plain text.
- Updated KDE Store text and release metadata for the new version.

## v2.0.9

Warning-block wording and visual polish.

- Reworded the warning-status text in German and English so it reads more naturally.
- Changed the German text from the awkward “Amtliche Warnmeldung vorhanden” wording to a clearer active-warning notice.
- Added a subtle warning banner treatment inside the Warnmeldungen/Warnings block so active warnings are easier to notice without making the whole dashboard noisy.
- Kept the existing warning item cards and severity coloring intact.

## v2.0.8

Display refresh reliability fix.

- Added a lightweight local cache polling timer so the visible dashboard re-reads `/rss.json` every 30 seconds.
- Keeps the display in sync when the systemd background timer has refreshed the cache but the QML view did not repaint or reload it yet.
- Avoids an observed stale-display race where opening settings caused the dashboard to update immediately.
- Does not increase external network calls; it only reads the local helper cache.

## v2.0.7

Uninstall-instruction correction after the 2.0 release.

- Clarified the uninstall commands shown in Info / Dienst so users choose one command instead of copying a full multi-command example.
- Put complete removal with `dielage-uninstall --purge` first.
- Added the full-ZIP fallback `./uninstall.sh --purge` to the visible uninstall instructions.
- Changed the normal uninstaller so it keeps `dielage-uninstall` available when settings/cache are preserved, making a later purge possible.
- Removed the installed uninstaller only during `--purge`.

## v2.0.6

Small settings polish after v2.0.4.

- Made the plain `twelvedata.com` reference clickable in the market settings.
- Added an API-key check button for Twelve Data and Finnhub in the market settings.
- Added a local helper endpoint that checks the entered market API keys without saving them first.
- Changed the bundled default block order to: warnings, weather, prayer times, system, markets, news.

## v2.0.4

RSS typography fix after the 2.0 release.

- Added a clearly visible RSS/news font-size setting near the general font-size control in Darstellung/Appearance.
- The RSS/news font-size setting controls only RSS feed names and headlines.
- Kept the separate news font-family setting for users who want a different typeface for headlines.
- Removed the duplicate, easy-to-miss RSS font-size field from the lower news-font section.
- Kept the cache-clear success text clean, without the confusing numeric counter.

## v2.0.2

Settings/service polish after the 2.0 release.

- Fixed the Cache löschen button so it no longer opens an unreliable dialog path; it now performs the action directly and shows visible feedback in Info / Dienst.
- Added a local tool check in Info / Dienst so users can see whether required tools such as Python 3 and systemctl are available.
- Added a backend /tools endpoint that reports required, recommended and optional helper tools.
- Extended German and English translations for the new tool-check UI.
- Kept cache clearing limited to Die-Lage cache files in ~/.cache/die-lage; settings and API keys are not touched.

## v2.0.1

Settings polish and wording cleanup after the 2.0 release.

- Fixed the layout of the section-separator setting in Darstellung/Appearance so the help text no longer overlaps the control.
- Made cache-clearing feedback visible directly in Info / Dienst.
- Reworded the market-data source help text in German and English.
- Rechecked German/English translation parity and removed informal wording from user-facing help text.

## v2.0.0

Major maintenance release focused on a clean, reliable helper workflow.

- Polished the Info / Dienst settings page with clearer helper-status wording and better restart guidance.
- Added explicit user-facing controls for boot/login refresh: enable/disable plus configurable delay in seconds.
- Kept the default boot/login refresh enabled with a conservative 120-second delay for Wi-Fi, VPN and network startup.
- Kept the local helper port configurable in a safe loopback-only range and made the active/configured port state visible.
- Added reliable Cache löschen and Lokalen Dienst neu starten flows with clearer feedback and safer fallback instructions.
- Improved the first-run KDE Store workflow: the stable latest ZIP now extracts to die-lage-latest, matching the copy-paste setup commands.
- Cleaned up reset/cache QML flows, removed stale dialog code, avoided duplicate cache loads after reset and improved helper restart handling.
