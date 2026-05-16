# Publishing to the KDE Store

## Important: this widget has a backend dependency

"Die Lage" is **not** a pure-QML plasmoid. It needs:

- a Python helper service (`dielage-server.py`) listening on `127.0.0.1:8765`
- a periodic fetcher (`dielage-cache.py`) populating `~/.cache/die-lage/rss.json`
- five systemd user units

The KDE Store's one-click "Install" only deploys the QML plasmoid package (the contents of `files/plasmoid/`). It does **not** install the helper service or systemd units. Therefore the widget will, on a fresh KDE Store install, detect the missing helper and show a setup screen with a copy-pasteable install command.

This is by design and documented in the widget's KDE Store description.

## Recommended store description

```
Die Lage / Daily Briefing

Ein kompaktes Lagebild für KDE Plasma: RSS-Nachrichten, Wetter für mehrere
Orte, amtliche Warnmeldungen (NINA/MeteoAlarm/GeoSphere/US-NWS oder eigene
Feeds), islamische Gebetszeiten, optional Wechselkurse, Indizes, Aktien sowie
kompakte Linux-Systeminfo. Reihenfolge der Blöcke, Titel, Schriftgrößen,
Akzentfarbe und Panel-Symbol sind anpassbar.

Das Widget entstand als mein persönlicher Ersatz für Conky, weil Conky in
meinem Wayland-/NVIDIA-Setup immer wieder Ärger gemacht hat. Es funktioniert
auch gut im Panel, entfaltet seine Stärke aber besonders auf einem hochformatigen
zweiten oder dritten Monitor und sieht
am besten aus, wenn der Desktop-Hintergrund schlicht schwarz ist. Ob einzelne
Teile später eigene Widgets werden, ist offen; aktuell ist es bewusst ein
zusammenhängendes Arbeitsdashboard.

WICHTIG: Dieses Widget braucht einen kleinen lokalen Hintergrunddienst, der
RSS-Feeds und andere Daten im Hintergrund holt. Die KDE-Store-Installation
installiert nur das sichtbare Plasma-Widget. Nach dem ersten Start zeigt
das Widget eine Einrichtungsseite. Dort steht, dass das vollständige Release-
Zip heruntergeladen und ./install.sh einmalig ausgeführt werden muss.

Vollständiges Bundle / Installer: https://github.com/gerald-drissner/die-lage-plasmoid
```

## Upload recommendation

Upload both artifacts for the same version:

- `die-lage-1.60.7.plasmoid` as the Plasma widget package.
- `die-lage-v1.60.7.zip` as the full installer bundle for users who need the local helper service.
- Use the separate `die-lage-store-assets-v1.60.7.zip` package for KDE Store artwork. Recommended files: `dielage-icon-512.png` as project icon/upload image and `dielage-wordmark-1200x400.png` as a banner/README asset if the store form allows it.

Do not promise automatic backend activation through the KDE Store. The first-run helper-missing screen explains the required manual installer step.


## Package layout for KDE Store upload

The KDE Store accepts a `.plasmoid` file (just a zip with a specific layout). To produce one:

```bash
cd files/plasmoid
zip -r ../../die-lage-1.60.7.plasmoid . -x '*.pyc' '*/__pycache__/*'
```

The resulting `die-lage-1.60.7.plasmoid` contains:

```
metadata.json
metadata.appdata.xml          # AppStream metainfo
contents/
  ui/main.qml
  images/dielage.svg
  images/dielage-panel.svg
  images/block-weather.svg
  images/block-prayer.svg
  icons/dielage.svg
```

## What the user sees after KDE Store install

1. The widget appears in "Add Widgets" as "Die Lage" / "Daily Briefing".
2. On first launch it tries `http://127.0.0.1:8765/config`; that fails because the helper is not installed.
3. The widget shows the **setup screen**: title "Einrichtung erforderlich", a copy-paste command pointing to the project's installer zip from the KDE Store project page, and a "Retry connection" button.
4. The user downloads the full installer bundle from the same KDE Store entry, runs `./install.sh`, then clicks Retry.

This means the KDE Store version and the installer bundle are paired but uploaded together.

## Required metadata fields (already set)

- `KPackageStructure: Plasma/Applet`
- `X-Plasma-API-Minimum-Version: 6.0`
- `KPlugin.Id: com.drissner.dielage`
- `KPlugin.Name` (DE) / `KPlugin.Name[en]`
- `KPlugin.Description` (DE) / `KPlugin.Description[en]`
- `KPlugin.Version: 1.60.7`
- AppStream `update_contact` and `provides` block
- `KPlugin.License: MIT`
- `KPlugin.Authors`
- `KPlugin.Icon`
- `KPlugin.Category`
- `KPlugin.Website`
- AppStream contact/donation URLs

## Icons and artwork

`metadata.json` now uses a package-relative icon path (`/icons/dielage.svg`) so Plasma versions that support bundled widget icons can show the Die-Lage symbol in the Widget Explorer. The compact panel view uses a deliberately simplified `contents/images/dielage-panel.svg`, because the full dashboard icon is too detailed at 16–24 px. Users can still switch the panel icon in Settings → Appearance → Panel icon: bundled Die Lage icon or a named Plasma/Breeze icon.

Artwork is shipped separately in `die-lage-store-assets-v1.60.7.zip`:

- `dielage-icon.svg`
- `dielage-icon-256.png`
- `dielage-icon-512.png`
- `dielage-wordmark.svg`
- `dielage-wordmark-1200x400.png`
- `dielage-panel.svg`

## Screenshots

The AppStream metadata now references two public screenshot URLs:

- `https://drissner.media/die-lage/screenshots/die-lage-portrait-dashboard.png` — portrait dashboard on a black desktop background (`1364×2048`)
- `https://drissner.media/die-lage/screenshots/die-lage-panel-popup.png` — panel popup view (`1218×1021`)

Keep these URLs stable after publishing. If screenshots move, update `files/plasmoid/metadata.appdata.xml` and bump the release package. A third screenshot of the settings page can still be added later, but is not required for this release.

## Translations

QML strings use a custom `t()` dict (DE/EN). For proper KDE i18n, future versions should migrate to `i18n("…")` so the strings can be extracted with `xgettext` and translated by the KDE localization community. Strings already use double quotes so this migration is mechanical.

## License audit before upload

- Code: MIT — `LICENSE` is present.
- Logo / icon: bundled `/icons/dielage.svg`, simplified `dielage-panel.svg`, and the separate store-assets package — verify all SVG/PNG assets are owned/licensed under MIT before upload.
- Data sources: documented in `SOURCES.md`. The widget does not bundle copyrighted feed content — only feed URLs.

## Pre-upload checklist

1. `metadata.json` version, name, description in sync with `metadata.appdata.xml`.
2. No `__pycache__/` in the zip (`zip ... -x '*/__pycache__/*'`).
3. No personal API keys in any default config (run `grep -r 'sk-\|api_key.*[a-zA-Z]' files/`).
4. `install.sh` is idempotent — second run on the same machine must not break anything.
5. `uninstall.sh` completes without errors on a clean machine.
6. README contains both DE and EN install snippets.
7. Tag a Git release matching the version.
