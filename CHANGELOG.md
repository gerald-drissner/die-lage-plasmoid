# Changelog

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
