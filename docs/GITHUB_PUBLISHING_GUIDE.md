# GitHub Publishing Guide — Die Lage v1.60.5

This guide assumes the repository does not yet exist on GitHub.

## 1. Create the GitHub repository

Suggested repository name:

```text
die-lage-plasmoid
```

Recommended description:

```text
KDE Plasma 6 situation board for RSS news, weather, warnings, prayer times, markets and system status.
```

Recommended settings:

- Visibility: public
- License: MIT
- Issues: enabled
- Discussions: optional
- Wiki: optional/off

## 2. Put the source tree on your machine

Unpack the GitHub repository ZIP I prepared:

```bash
cd /home/gd/github
unzip ~/Downloads/die-lage-github-repo-v1.60.5.zip
cd die-lage
```

If you prefer another folder, use that. Computers are surprisingly flexible when not asked to print.

## 3. Initialize Git and make the first commit

```bash
git init
git add .
git commit -m "First public release v1.60.5"
git branch -M main
```

## 4. Add your GitHub remote

SSH variant:

```bash
git remote add origin git@github.com:YOUR-USERNAME/die-lage-plasmoid.git
git push -u origin main
```

HTTPS variant:

```bash
git remote add origin https://github.com/YOUR-USERNAME/die-lage-plasmoid.git
git push -u origin main
```

## 5. Create the version tag

```bash
git tag -a v1.60.5 -m "Die Lage v1.60.5"
git push origin v1.60.5
```

## 6. Create a GitHub release

Open GitHub → Releases → Draft a new release.

Use:

- Tag: `v1.60.5`
- Title: `Die Lage / Daily Briefing v1.60.5`
- Release notes: paste `GITHUB_RELEASE_NOTES_v1.60.5.md`

Attach these files:

- `die-lage-1.60.5.plasmoid`
- `die-lage-v1.60.5.zip`
- `die-lage-store-assets-v1.60.5.zip`

## 7. Suggested release assets location

Keep generated artifacts outside the source tree or under `dist/`. The `.gitignore` excludes `dist/`, `*.zip` and `*.plasmoid` by default, so the repository stays source-only.
