# Die Lage

## v2.0.9 highlights

- Improves automatic display refresh reliability.
- The widget now re-reads the local cache every 30 seconds, so background updates become visible without opening the settings first.
- This does not increase external network calls; it only reads the local helper cache.

## Installation note

The KDE Store plasmoid package installs the visible widget. The full installer ZIP is still needed for the local Python helper, cache refresh timers and systemd user services.
