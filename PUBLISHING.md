# Publishing Die Lage

## Build

Run the release check for the current version, for example:

```bash
./release-checks-v2.0.13.sh
```

## GitHub release assets

Upload the generated files:

- `die-lage-<version>.plasmoid`
- `die-lage-v<version>.zip`
- `die-lage-latest.zip`

Release notes and KDE Store changelog snippets should be used in the release UI, but should not be committed to the source tree.

## KDE Store

- Main package: `die-lage-<version>.plasmoid`
- Full/helper installer ZIP: `die-lage-v<version>.zip`
