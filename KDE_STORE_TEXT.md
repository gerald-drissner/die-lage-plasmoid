# KDE Store copy/paste text — Die Lage v1.60.5

## Title
Die Lage (Daily Briefing)

## Short description DE
Kompaktes Lagebild für KDE Plasma: RSS-Nachrichten, Wetter, Warnmeldungen, Gebetszeiten, Märkte und Systemstatus für Desktop und Panel; besonders stark auf einem hochformatigen Zusatzbildschirm.

## Short description EN
Compact KDE Plasma briefing board: RSS news, weather, warnings, prayer times, markets and system status for desktop and panel; strongest on a portrait-oriented extra screen.

## Long description DE
Der Name „Die Lage“ ist bewusst journalistisch gemeint: Er steht für den aktuellen Stand der Dinge, also für die Frage, was gerade wichtig ist und im Blick bleiben sollte. In der englischen Oberfläche heißt das Widget „Daily Briefing“.

Die Lage ist ein kompaktes Lagebild direkt auf dem KDE-Plasma-Desktop oder im Panel: RSS-Nachrichten aus frei konfigurierbaren Quellen, Wetter für mehrere Orte, amtliche Warnmeldungen über NINA, MeteoAlarm, GeoSphere, US-NWS oder eigene Feeds, islamische Gebetszeiten, Wechselkurse, Indizes, Aktien sowie optionale Linux-Systeminformationen inklusive Netzwerk- und VPN-Status.

Das Widget entstand als mein persönlicher Ersatz für Conky, weil Conky in meinem Wayland-/NVIDIA-Setup immer wieder Ärger gemacht hat. Es ist deshalb kein generisches Alles-für-alle-Widget, sondern ein persönliches Arbeitsdashboard, das ich mit anderen teile, wenn sie genau so etwas sinnvoll finden. Es funktioniert auch gut im Panel, entfaltet seine Stärke aber besonders auf einem hochformatigen zweiten oder dritten Monitor; am schönsten wirkt es mit einem schwarzen Desktop-Hintergrund.

Die Reihenfolge der Blöcke ist einstellbar. Blöcke können ein- und ausgeklappt werden. Das Widget unterstützt Deutsch und Englisch, Desktop- und Panel-Betrieb, eigene Titel, Schriftgrößen, Akzentfarbe, wählbares Panel-Symbol und lokale Konfiguration. Ob einzelne Teile später als eigene Widgets ausgelagert werden, ist offen; aktuell ist Die Lage bewusst als ein zusammenhängendes Lagebild für den eigenen Arbeitsalltag gedacht.

Wichtig: Dieses Widget ist nicht rein QML. Für RSS, Wetter, Warnungen, Märkte und Systemstatus braucht es einen kleinen lokalen Hintergrunddienst. Die KDE-Store-Installation installiert das sichtbare Plasmoid. Nach dem ersten Start zeigt das Widget eine Einrichtungsseite. Laden Sie zusätzlich das vollständige Release-Zip herunter, entpacken Sie es und führen Sie einmalig `./install.sh` aus. Der Dienst läuft danach als normaler systemd-User-Service ohne Root-Rechte.

## Long description EN
**Die Lage** means roughly **“the situation”** or **“the current state of affairs”**. In German journalism, the phrase points to the daily editorial question: what is happening, what matters right now, and what needs to be kept in view. The English name used inside the widget is **Daily Briefing**.

Daily Briefing is a compact situation board directly on the KDE Plasma desktop or in a panel: RSS news from configurable sources, weather for multiple locations, official warnings via NINA, MeteoAlarm, GeoSphere, US NWS or custom feeds, Islamic prayer times, exchange rates, indices, stocks and optional Linux system information including network and VPN status.

I created it as my personal replacement for Conky because Conky kept causing trouble in my Wayland/NVIDIA setup. It is therefore not a generic everything-for-everyone widget, but a personal work dashboard that I am sharing for people who find this kind of setup useful. It also works well in the panel, but it is strongest on a portrait-oriented second or third monitor and looks best on a plain black desktop background.

Block order is configurable. Blocks can be collapsed and expanded. The widget supports German and English, desktop and panel mode, custom titles, font sizes, accent color, selectable panel icons and local configuration. Some parts may become separate widgets in the future; for now Daily Briefing is intentionally one combined situation board for my everyday workflow.

Important: this is not a pure QML widget. RSS, weather, warnings, markets and system status need a small local background service. The KDE Store installation installs the visible plasmoid. On first launch the widget shows a setup screen. Download the full release zip as well, unpack it and run `./install.sh` once. The service then runs as a normal systemd user service without root privileges.

## Screenshot URLs
- Portrait dashboard: https://drissner.media/die-lage/screenshots/die-lage-portrait-dashboard.png
- Panel popup: https://drissner.media/die-lage/screenshots/die-lage-panel-popup.png

## Tags
KDE, Plasma, plasmoid, widget, RSS, news, weather, warnings, NINA, MeteoAlarm, prayer times, markets, stocks, system monitor, VPN

## Files to upload
- `die-lage-1.60.5.plasmoid`: KDE Store / Plasma widget package.
- `die-lage-v1.60.5.zip`: full installer bundle with helper scripts, systemd user units.
- Recommended store images from the separate assets ZIP: `dielage-icon-512.png` and `dielage-wordmark-1200x400.png`.

## Install note for users
After installing from KDE Store, add the widget to the desktop or panel. If the setup screen appears, download the full release zip, unpack it and run:

```bash
cd ~/Downloads
unzip -o die-lage-v1.60.5.zip
cd die-lage-v1.60.5
chmod +x install.sh uninstall.sh emergency-clean-dielage.sh
./install.sh
systemctl --user restart plasma-plasmashell.service
```

## Uninstall note for users
Use the Info/service tab or run:

```bash
dielage-uninstall
# or complete removal including config/cache:
dielage-uninstall --purge
```
