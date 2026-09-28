# Die Lage v2.1.9

## v2.1.9 highlights

- Fixes cache-service OOM kills caused by package/update helpers exceeding the former 256 MiB service limit; cache refresh services now use a 768 MiB safety ceiling.
- Adds a separate update-check interval, independent of the normal System refresh.
- Adds explicit controls for native system packages, Flatpak and Snap. Flatpak and Snap are opt-in and all package sources are checked sequentially.
- Adds low-memory protection that can postpone package checks while preserving the last successful result.
- Broad native package-manager support covers Debian/Ubuntu, Arch derivatives, Fedora/RHEL derivatives, openSUSE, Alpine, Void, Solus, Gentoo and rpm-ostree systems, with PackageKit as a generic fallback.
- Update checks are read-only: Die Lage never installs packages and never forces a package-metadata refresh.

## Files

- KDE Store package: `die-lage-2.1.9.plasmoid`
- Full/helper installer: `die-lage-v2.1.9.zip`
- Stable download alias: `die-lage-latest.zip`

The `.plasmoid` contains the Plasma widget only. The full ZIP additionally installs/updates the local Python helpers and systemd user units.
