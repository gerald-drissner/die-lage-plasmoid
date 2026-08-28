# Die Lage Changelog

## v2.1.7

UI polish after the v2.1.6 Plasma live test.

- Moved weather-provider attribution out of the Weather heading. A small info button now opens source details; the required provider credit remains as a very quiet footer so OpenWeather/Open-Meteo attribution is not lost.
- Refresh controls no longer fade almost out while a job is running. The active global or per-block refresh control shows a clearly visible animated BusyIndicator until the asynchronous refresh completes.
- Added an optional continuous RSS-age color scale. Users can enable/disable it, choose the scale duration (default 120 minutes), and optionally set newest/older colors. Empty fields follow the current Plasma/widget accent and Plasma text color.
- Added a live color preview and persisted/migrated the new age-color settings without changing existing feeds, API keys or other user configuration.
- Extended regression coverage for the new refresh spinner, compact weather attribution and RSS-age scale wiring/defaults.

## v2.1.6

Release-candidate hardening pass after the v2.1.5 live Plasma test. No new dashboard feature is introduced; the focus is correctness, recovery behaviour and store-safe upgrades.

- Simplified the OpenWeather API-key success message so it confirms the key without echoing OpenWeather's reverse-geocoded place name.
- Made per-block refreshes truly block-local. A manual News/Weather/Markets/System refresh no longer wakes other due blocks, while manual News retry still bypasses feed backoff.
- Hardened asynchronous refresh cleanup so a request timeout cannot leave the QML single-flight state stuck.
- Existing malformed `config.json` files now fail closed in the installer, cache helper and local server instead of being treated as empty/default configuration. User data is left untouched for manual recovery.
- Feed, weather and warning thread-pool workers now fail closed on unexpected internal exceptions: the configured source remains represented with an error/stale state instead of silently disappearing.
- Market partial failures now retain only exact, still-configured cached FX/index/stock entries for failed instruments. Removed instruments are never resurrected from cache.
- Prayer-day staleness uses the date/time zone returned by AlAdhan instead of assuming the computer's local date.
- Cache/config directories and JSON files are kept private; systemd services use `UMask=0077` plus resource and process hardening. Optional public-network lookup now has a bounded response size.
- Store/helper version mismatches are surfaced in the widget so a `.plasmoid` update cannot silently leave an older Python helper unnoticed.
- Metadata now uses a documented theme icon name; two News disclosure actions are keyboard accessible.
- Expanded regression/release checks for worker failures, exact block refresh, partial market cache continuity, corrupt-config preservation, metadata/AppStream consistency, systemd hardening and release-package cleanliness.

## v2.1.5

- Added an in-settings OpenWeather API-key check. The key is tested immediately without saving it first; success, invalid/inactive key, rate-limit and generic connection failures are reported in the selected UI language.
- Clarified the Weather-source help text: with a valid OpenWeather key, weather retrieval switches fully to OpenWeather; Open-Meteo is not queried in parallel. Both providers intentionally use the same widget layout.
- Added `Automatic (system language)` alongside the existing German/English language selector. Fresh installs default to automatic; existing users keep their stored language choice. The backend resolves automatic language from the user-session locale so provider descriptions and status texts follow the UI where possible.
- Added regression coverage for OpenWeather key probing, the new local endpoint, automatic language resolution and German/English translation parity.

## v2.1.4

Local test release focused on the three UI/source requests after the successful v2.1.3 Plasma test.

- News source problems no longer consume a full-width banner by default. A warning-triangle button appears beside the News refresh control and toggles the existing source-status box on demand. When the problem disappears, the disclosure resets to the compact state.
- Added `Appearance → Show age of RSS headlines`. It defaults to enabled and controls the per-headline `12 min.` / `2 hr.` publication-age labels without changing feed parsing or freshness logic.
- Added an optional OpenWeather API key under `Sources → Weather data source`. Leaving it blank keeps Open-Meteo. Entering a key switches weather retrieval to OpenWeather current conditions plus the free 5-day/3-hour forecast endpoint. The UI explicitly avoids claiming that one provider is universally more accurate.
- Weather cache identity now includes the selected provider, so switching between Open-Meteo and OpenWeather cannot inherit stale readings from the other source.
- Added a subtle visible weather-provider attribution in the Weather heading.
- Corrected the Open-Meteo snowfall unit from `mm` to `cm`.
- Added regression coverage for the compact News status control, RSS-age setting, OpenWeather provider selection/schema mapping, provider-specific weather caches, and new config keys.

## v2.1.3

Local test hotfix for the QML load failure in v2.1.2.

- Fixed a duplicate `opacity` assignment in the prayer-location label that caused Plasma to reject `main.qml` with `Property value set multiple times`.
- Extended the QML release checker to detect duplicate direct property assignments inside the same brace scope, with a built-in self-test so this class of load-time error cannot silently pass the structural check again.

## v2.1.2

Local test release closing the remaining integration gaps found in the v2.1.1 audit.

### Refresh state is end-to-end

- QML now treats refreshes as single-flight. A global refresh and the per-block Weather, System, Markets and News refreshes cannot overlap and overwrite each other's polling state.
- The immediate `/refresh` and `/refresh-block` responses are checked for `started` and `already_running` instead of treating every HTTP 200 as a started job.
- `/refresh-status` now drives the visible result: `already_running` shows a specific notice, `last_ok: false` reports a failed background job while keeping the previous cache visible, and a successful job clears the refresh state normally.

### Cache identity and stale data

- Cached weather is reused only when the configured name, latitude and longitude match. A location renamed or repointed to different coordinates can no longer inherit weather from the previous configuration.
- Caches written before v2.1.2 did not contain coordinates and are intentionally not reused after a failed weather fetch, because their identity cannot be proven safely.
- Cached warning cards now carry their own visible cached/age marker instead of relying only on the block-level incomplete-source banner.

### Permissions and QA

- The local server's atomic JSON writer now creates replacement config files as 0600 and ensures the config directory is 0700, matching the cache helper and installer.
- Regression tests now cover async helper failure, external-lock status, duplicate refresh rejection, both config writers, weather cache identity, QML single-flight/status wiring and the warning-card stale marker.

## v2.1.1

Fixes found in an independent review of v2.1.0.

### Warnings could report a false all-clear

- If one warning source loaded and another failed, the block rebuilt itself from the sources that happened to succeed. A still-valid warning from the failed area disappeared, and an empty result was rendered as "no current warnings" even though a source had never been checked. Each source now reports its own status, keeps its last known warnings flagged as cached, and the block reports itself incomplete. The all-clear text is shown only when every source was actually checked.

### Refreshing no longer looks like a broken helper

- `/refresh` and `/refresh-block` ran the whole cache rebuild inside the HTTP request. A legitimate refresh can exceed the widget's 25 s request timeout, so a healthy helper was declared unreachable and the user was sent to the setup screen. Refreshes now start in the background and return immediately; the widget polls `/refresh-status` for completion. A request timeout no longer marks the helper as dead.
- The News block's own retry button sent `--block news`, but the feed backoff was only bypassed by `--force`. A source in a long backoff was therefore not contacted at all and the button appeared to do nothing. Both `--force` and `--block` now count as a manual refresh.
- A cache run that lost the file lock to the systemd timer exited 0, which the server reported as a completed refresh. It now exits 75, which the server reports as already running.

### Installer

- The plasmoid swap is now genuinely atomic: the new package is staged and validated beside the target, switched in by rename, and rolled back on any failure. Previously the old directory was removed first and validation ran afterwards, so a failure left no working widget.
- `systemctl --user daemon-reload` was unguarded under `set -e`, so on a machine with no systemd user bus the installer aborted after copying files, with no explanation. All systemd calls are now best-effort and print manual instructions if the bus is unavailable.
- The first cache refresh no longer runs synchronously; the installer no longer waits for every feed, weather and market request before finishing.
- `~/.config/die-lage` is created 0700 and `config.json` 0600, since it can hold Twelve Data and Finnhub API keys.

### Freshness is now visible, not just recorded

- Weather kept the last good reading for a failed location but the UI never showed that it was cached; it looked identical to a fresh reading. Cached values are now labelled and dimmed, with the age and cause on hover.
- Prayer times had the same problem, and across midnight a cached plan is not merely old but wrong. Cached times are labelled, and times that are not for today are flagged prominently.

### Diagnosis accuracy

- The VPN explanation used `count >= max(2, fail_count // 2)` as a majority test, so two filtered sources out of five triggered a confident VPN diagnosis. A real majority is now required.
- The wording no longer asserts that a VPN is responsible. A running tunnel daemon does not prove web traffic leaves through it, so the text states what was observed and offers the VPN as a possibility.
- TLS failures were detected by searching the message for "certificate" or "ssl". Detection is now based on the exception type, so an SSL error with different wording is no longer misfiled as a generic network failure.
- Generic socket errors such as `ConnectionError` and bare `OSError` fell through to "unknown error", the exact uninformative label this classifier exists to remove.

### Other fixes

- Cached headlines were matched by feed name alone, so editing a feed's URL could make the old source's headlines reappear under the new one. Matching now uses name and URL.
- Decompression was unbounded: the size cap applied to the downloaded bytes, not the inflated result, so a small compressed document could expand without limit. Inflation is now capped and streamed.
- "Clear cache" left `feedstate.json` in place, so failure counters and backoff windows survived a cache clear.
- Feed state for sources the user has removed is now dropped instead of accumulating forever.
- The server's fallback block order had drifted from `default-config.json`; it now reads the canonical order.
- `delayed_service_restart()` returned unconditionally after calling `systemd-run`, so a non-zero exit meant neither the restart nor the documented fallback ran. The fallback now triggers correctly, and the transient unit name is unique.

### Release QA

- `release-checks-v2.1.1.sh` now runs a real behavioural regression suite (`tests/regression.py`) covering transport, error classification, warning completeness, feed bookkeeping and permissions, plus a sandboxed installer upgrade test. The v2.1.0 script only checked syntax, metadata and structure, which is why a broken News retry passed it.
- The stale-version scan covered only `files/`, so `PUBLISHING.md` and `KDE_STORE_TEXT.md` stayed on 2.0.19 through a release. It now scans the whole tree for version declarations while ignoring historical prose.
- Fixed a duplicated `v2.0.18` heading in this changelog and a README/code disagreement about the backoff ceiling.

## v2.1.0

### Feed errors now say what actually went wrong

- Failed sources previously showed the bare exception class name, so a publisher blocking a VPN exit IP, a rate limit, a geo-block and an overloaded origin all appeared as the single word `HTTPError`. Failures are now classified into concrete causes with plain-language text in German and English: blocked by the publisher, blocked in this region, rate limited, address no longer exists, DNS resolution failed, TLS problem, no network connection, timeout, invalid feed, empty feed.
- The News block shows one calm summary line instead of a joined list of error strings. When several publishers refuse the connection while a VPN tunnel is up, the summary names the VPN as the likely cause rather than leaving the user to guess.
- A partial outage where cached headlines are still on screen is rendered as a notice, not in the error colour. Only a total blackout uses the negative colour.
- Each failing source gets a small marker next to its name, with the cause and the age of its data in the tooltip. A "Details je Quelle" toggle expands the full per-source breakdown, and a retry link refreshes only the News block.
- Sources still serving cached headlines are labelled as cached instead of silently looking current.

### Speed

- RSS feeds are fetched in parallel instead of one after another. With eleven feeds, a 15 s timeout and one retry each, a flaky connection could previously keep one refresh busy for minutes; the same situation now costs roughly the slowest single feed.
- Weather locations are fetched in parallel for the same reason.
- Conditional requests: ETag and Last-Modified are stored per feed and sent on the next fetch. A publisher answering "not modified" costs almost nothing and counts as a success.
- gzip and deflate are now requested and decompressed, which cuts feed transfer size substantially.
- Per-feed backoff after repeated failures (5, 15, 30, 60, 120, up to 240 minutes) so a source that blocks the current exit IP is not retried every few minutes. A manual refresh always overrides the backoff.
- The translation tables were moved out of `t()` into properties. They were previously rebuilt on every one of roughly 290 call sites, on every theme, font, language or size change.
- The clock tick and the cache poll slow down while the popup is closed, where nothing they drive is visible.

### Fixes

- Oversized HTTP responses in the cache helper were silently truncated and handed to the XML parser. They now fail explicitly, which is what the v2.0.11 notes already claimed but only implemented in the local server.
- A weather location that failed to update disappeared from the block entirely whenever at least one other location succeeded. Its last known reading is now kept and marked as cached.
- Feeds that omit a charset header are decoded from the XML declaration instead of being forced to UTF-8, so regional feeds shipping ISO-8859-1 no longer show replacement characters.
- The installer created an empty timestamped quarantine directory in the home directory on every run, whether or not anything needed quarantining.
- The installer's config merge kept its own copy of the defaults, which had drifted and no longer contained `system_interval_minutes`, `prayer_upcoming_before_minutes` or `prayer_now_after_minutes`. It now reads the shipped `default-config.json`, and the inline fallback copies in both Python helpers are generated from that same file.
- The local server restarted itself by forking a shell inside its own cgroup, which the stop phase of that very restart then killed. It now asks systemd for a transient trigger unit and falls back to the old method only where `systemd-run` is unavailable.

### Additions

- Headlines show their publication age, parsed from the feed's own `pubDate` or `updated` field. Headlines published within the current refresh interval are highlighted as new. Feeds without timestamps are unaffected.
- Per-source diagnostics: last successful update time and last response time are recorded and shown in the details view.

### Security and robustness

- The local server sends `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` and `Referrer-Policy: no-referrer`, has a per-connection timeout, a bounded request queue and closes its listening socket on SIGTERM so a restart can rebind immediately.
- The systemd units now carry consistent hardening. The boot refresh service had none at all despite running the identical script as the timer service. Added `RestrictSUIDSGID`, `ProtectKernelTunables`, `ProtectControlGroups` and `SystemCallArchitectures=native`, plus `MemoryMax` and `TasksMax` on the local server.
- The cache timer sets `AccuracySec=20s` so systemd can coalesce its wake-ups.

### Removed

- Dead code: `_count_command_lines`, `first_ipv4`, `fmt_epoch` and `format_timestamp` in the cache helper, the unused `latestReleaseUrl` property and two orphaned translation keys in the QML.

## v2.0.19

- Fixes duplicate GeoSphere Austria warnings that appeared as several visually identical cards when the provider split one warning into consecutive daily slices.
- Merges identical GeoSphere warning entries by source area, location, warning type, warning level, title and description, keeping the latest expiry time.
- Keeps NINA, MeteoAlarm, NWS and custom feed behavior unchanged.

## v2.0.18

- Restores the cleaner KDE/theme refresh icon for the top refresh action and per-block refresh controls.
- Keeps refresh icons visible while a refresh is running by avoiding the theme's disabled-icon rendering state.
- Keeps the compact icon-only layout introduced in v2.0.16/v2.0.17.
- No backend, cache or API behavior changed.

## v2.0.17

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
