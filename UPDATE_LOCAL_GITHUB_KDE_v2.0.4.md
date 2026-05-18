# Die Lage v2.0.4 – local test, GitHub and KDE Store

## Local test

```bash
cd ~/Downloads
rm -rf die-lage-v2.0.4
unzip -o die-lage-v2.0.4.zip
cd die-lage-v2.0.4
chmod +x install.sh uninstall.sh emergency-clean-dielage.sh
./install.sh
systemctl --user daemon-reload
systemctl --user restart dielage-local-server.service
systemctl --user restart plasma-plasmashell.service
curl -s http://127.0.0.1:8765/status
```

Expected: `"version": "2.0.4"`.

## GitHub release assets

Upload:

- `die-lage-2.0.4.plasmoid`
- `die-lage-v2.0.4.zip`
- `die-lage-latest.zip`

Use `GITHUB_RELEASE_NOTES_v2.0.4.md` as the release text.

## KDE Store

- Main package: `die-lage-2.0.4.plasmoid`
- Full/helper installer ZIP: `die-lage-v2.0.4.zip`
- Changelog: paste `KDE_STORE_CHANGELOG_v2.0.4.txt`
