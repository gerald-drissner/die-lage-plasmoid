# Release Checklist — Die Lage

## Before tagging

- [ ] Confirm version number in `files/plasmoid/metadata.json`.
- [ ] Confirm version number in `files/plasmoid/metadata.appdata.xml`.
- [ ] Confirm version number in `files/bin/dielage-server.py` and `files/bin/dielage-cache.py`.
- [ ] Confirm `README.md`, `KDE_STORE_TEXT.md` and `PUBLISHING.md` mention the same version.
- [ ] Run static checks.
- [ ] Run a fresh install test.
- [ ] Test `dielage-uninstall --purge`.
- [ ] Test screenshot URLs.

## Static checks

```bash
python -m py_compile files/bin/dielage-cache.py files/bin/dielage-server.py
bash -n install.sh uninstall.sh emergency-clean-dielage.sh
python -m json.tool files/plasmoid/metadata.json >/dev/null
python -m xml.etree.ElementTree files/plasmoid/metadata.appdata.xml >/dev/null
```

Optional:

```bash
appstreamcli validate files/plasmoid/metadata.appdata.xml
```

## Build artifacts

```bash
./tools/build-release.sh
```

Expected output in `dist/`:

- `die-lage-1.60.5.plasmoid`
- `die-lage-v1.60.5.zip`
- `die-lage-store-assets-v1.60.5.zip`

## GitHub release

- [ ] Push `main`.
- [ ] Push tag `v1.60.5`.
- [ ] Create GitHub release from tag.
- [ ] Attach three artifacts.
- [ ] Paste release notes from `GITHUB_RELEASE_NOTES_v1.60.5.md`.

## KDE Store

- [ ] Upload `.plasmoid` as main file.
- [ ] Upload full ZIP as additional/download file if the form allows it.
- [ ] Use `docs/KDE_STORE_FORM_TEXT_DE.md` and `docs/KDE_STORE_FORM_TEXT_EN.md`.
- [ ] Add screenshots.
- [ ] Add clear installation note about the local helper service.
