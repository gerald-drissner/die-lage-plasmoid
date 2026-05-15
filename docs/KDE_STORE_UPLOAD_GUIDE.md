# KDE Store Upload Guide — Die Lage v1.60.5

## Files to upload

Use these files from the release:

1. `die-lage-1.60.5.plasmoid` — main KDE Store file.
2. `die-lage-v1.60.5.zip` — full installer bundle for users who need the local helper service.
3. `die-lage-store-assets-v1.60.5.zip` — artwork package for the store page, not required by the widget itself.

Recommended artwork:

- Project icon / preview image: `store-assets/dielage-icon-512.png`
- Optional banner / README image: `store-assets/dielage-wordmark-1200x400.png`

## Screenshot URLs

These are already referenced in `metadata.appdata.xml`:

- `https://drissner.media/die-lage/screenshots/die-lage-portrait-dashboard.png`
- `https://drissner.media/die-lage/screenshots/die-lage-panel-popup.png`

Before upload, test:

```bash
curl -I -A "appstreamcli/1.0" https://drissner.media/die-lage/screenshots/die-lage-portrait-dashboard.png
curl -I -A "appstreamcli/1.0" https://drissner.media/die-lage/screenshots/die-lage-panel-popup.png
```

Both should return HTTP 200.

## Store text

Use:

- `docs/KDE_STORE_FORM_TEXT_DE.md` for German fields.
- `docs/KDE_STORE_FORM_TEXT_EN.md` for English fields.

## Important warning for users

Make this clear in the KDE Store page:

> The KDE Store installation installs only the Plasma widget. For RSS, weather, warnings, markets and system status, the local helper service must be installed once from the full release ZIP.

## Sanity checks before upload

```bash
python -m py_compile files/bin/dielage-cache.py files/bin/dielage-server.py
bash -n install.sh uninstall.sh emergency-clean-dielage.sh
python -m json.tool files/plasmoid/metadata.json >/dev/null
python -m xml.etree.ElementTree files/plasmoid/metadata.appdata.xml >/dev/null
```

Optional if installed:

```bash
appstreamcli validate files/plasmoid/metadata.appdata.xml
```
