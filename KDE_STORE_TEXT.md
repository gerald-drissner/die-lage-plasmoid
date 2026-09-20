# Die Lage v2.1.8

## v2.1.8 highlights

- The first regular background cache check now waits three minutes after the Plasma user session starts, reducing login-time contention.
- The recurring one-minute timer cadence is unchanged after startup, so short user-selected fetch intervals remain supported.
- The existing Info / Dienst controls for the forced refresh after login/reboot remain available and unchanged.
- Includes all reliability, OpenWeather, RSS-age and UI improvements from v2.1.7.

## Files

- KDE Store package: `die-lage-2.1.8.plasmoid`
- Full/helper installer: `die-lage-v2.1.8.zip`
- Stable download alias: `die-lage-latest.zip`

The `.plasmoid` contains the Plasma widget only. The full ZIP additionally installs/updates the local Python helper and systemd user units.
