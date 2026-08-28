# Publishing Die Lage

## Release verification

Always run the release checks from the exact unpacked release ZIP, not only from a development folder:

```bash
./release-checks-v2.1.7.sh
```

For a final release, also test the full ZIP on a real Plasma 6 desktop because the static QML checks cannot replace `plasmashell` runtime rendering.

## GitHub release assets

Attach these three files to the `v2.1.7` release:

- `die-lage-2.1.7.plasmoid` — Plasma widget package
- `die-lage-v2.1.7.zip` — full installer including helper/systemd units
- `die-lage-latest.zip` — byte-identical stable alias of the full installer

## KDE Store

Update the existing Die Lage product; do not create a second product. Upload `die-lage-2.1.7.plasmoid` as the new Plasma package.

Important: a KDE Store `.plasmoid` update cannot write `~/.local/bin` or install systemd user units. Users whose local helper is older therefore receive a version-mismatch notice in the widget and should run the current full installer ZIP once. The helper/config/cache remain user-level; no root access is required.
