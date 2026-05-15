# Die Lage / Daily Briefing — v1.60.5

**Die Lage** means roughly **“the situation”** or **“the current state of affairs”**. In German journalism, *die Lage* also evokes the daily editorial question: what is happening, what matters right now, and what needs to be kept in view. The English name used inside the widget is **Daily Briefing**.


## Neu in v1.60.5

- Letzte Publish-Politur vor dem KDE-Store-Upload: Feed- und Indexnamen werden jetzt wirklich als PlainText gerendert.
- Die interne Panel-Popup-Breitenlogik merkt sich den gespeicherten Wert jetzt zentral nach jedem Konfigurationsladen; das vermeidet unnötiges Schließen bei Fallback-/Legacy-Konfigurationen.
- Zwei Titelzeilen im Popup können bei sehr schmalen Panel-Popups sauber schrumpfen.
- v1.60.4 hatte bereits die AppStream-Metadaten bereinigt, die Block-Reihenfolge vereinheitlicht und das Panel-Popup-Verkleinern repariert.

## Neu in v1.60.2

- Märkte: Zeitangaben sind jetzt kontextabhängig kompakt. Für Werte vom heutigen lokalen Tag wird das Datum ausgeblendet; bei Vortagsdaten, Wochenenden oder alten Schlusskursen bleibt das Datum sichtbar. Fremde Börsenzeitzonen wie EDT oder JST bleiben sichtbar, lokale CEST-Angaben werden weggelassen.
- Wetterdetails bleiben kompakt: gefühlte Temperatur, Luftfeuchte, Sonne, danach nur vorhandene Wind-/Böen-/Regen-/Schnee-Werte. Nullwerte werden ausgeblendet, Temperaturen bleiben sichtbar.
- AppStream-Screenshot-Metadaten verweisen auf die öffentlichen Screenshots für Hochformat-Dashboard und Panel-Popup.
- Hinweis: Die Panel-Popup-Standardbreite wurde in v1.60.1 von 1000 px auf 600 px reduziert. Bestehende Standardwerte werden migriert; bewusst gesetzte andere Werte bleiben erhalten.

## Screenshots für KDE Store / AppStream

Die AppStream-Metadaten verweisen auf diese öffentlichen PNG-Dateien:

- `https://drissner.media/die-lage/screenshots/die-lage-portrait-dashboard.png` — Hochformat-Dashboard auf schwarzem Hintergrund
- `https://drissner.media/die-lage/screenshots/die-lage-panel-popup.png` — Panel-Popup-Ansicht

Die Bilder werden nicht in das Plasmoid eingebettet, damit das Installationspaket schlank bleibt.

## Neu in v1.58.8

- Neues mitgeliefertes Die-Lage-SVG für den Panel-Modus und separate Store-Assets als Icon/Wordmark in SVG und PNG.
- In den Einstellungen kann das Panel-Symbol gewählt werden: mitgeliefertes Die-Lage-Symbol oder Plasma-/Breeze-Themensymbol mit Presets und freiem Icon-Namen.
- KDE-Store-Texte ergänzt: Entstehung als persönlicher Conky-Ersatz, Hinweis auf Wayland/NVIDIA-Probleme, optimale Nutzung auf hochformatigem Zweit-/Drittmonitor mit schwarzem Hintergrund.
- XHR-Anfragen aus dem Widget haben Timeouts, damit die Oberfläche bei einem hängenden lokalen Helper nicht ewig wartet.
- Twelve Data wird sparsamer genutzt: ein Request pro Instrument statt zusätzlichem Time-Series-Request.
- Bei klaren API-Key-/Quota-Fehlern wird ein keyed Provider für den laufenden Refresh übersprungen, statt pro Symbol erneut in dieselbe Wand zu laufen.
- AppStream-Metadaten um Update-Kontakt ergänzt.

## Neu in v1.58.5

- Bevorstehende Gebetszeiten werden kurz vorher markiert und nach Ablauf wieder normal dargestellt.
- Wetterdetails sind logisch sortiert: gefühlt, Luftfeuchte, Wind, Böen, Regen, Schnee, Sonne.
- Robusteres Konfigurationshandling: Default-Fallbacks werden deep-copied, einklappbare Blöcke speichern Fehler sauberer, Setup-Pfad nutzt die Versionsvariable.

## Neu in v1.58.4

- RSS-Nachrichten mit sauberem hängendem Einzug: mehrzeilige Überschriften stehen jetzt unter dem Text, nicht unter dem Aufzählungspunkt.
- Standard-RSS-Quellen aktualisiert: BILD Berlin entfernt, Polizei Berlin und Heise online ergänzt.
- Dienststatus-Hilfe erweitert: Wenn der lokale Dienst rot ist, zeigt der Info/Dienst-Tab konkrete Reparaturbefehle.
- URLs in Hilfetexten der Einstellungen sind jetzt anklickbar.

## Neu in v1.58.3

- Einklapp-Schalter sitzen jetzt in derselben Zeile wie die Blocküberschrift.
- Wetterdetails zeigen zusätzlich Luftfeuchte, gefühlte Temperatur und Windböen, sofern Open-Meteo diese Werte liefert.
- Blöcke im Desktop-/Popup-Layout können mit einem kleinen Pfeil ein- und ausgeklappt werden; der Zustand wird lokal gespeichert.
- Info/Dienst enthält direkt eine Erklärung zur vollständigen Deinstallation inklusive systemd-User-Units.
- Version und Copyright stehen nicht mehr rechts in der Button-Zeile, sondern am Ende des Info/Dienst-Tabs.
- KDE-Store-Hinweise und Veröffentlichungstexte ergänzt.

## Neu in v1.58.1

- Mehrzeilige Eingabefelder in den Einstellungen haben eigene Scrollleisten, damit lange Feed-, Wetter-, Warn- und Marktlisten nicht im Blindflug editiert werden müssen.
- Externe News-Links werden vor dem Öffnen auf `http://` und `https://` begrenzt.
- Der lokale Server antwortet bei `HEAD`, `PUT` und `DELETE` kontrolliert und gibt keinen Python-Standard-Serverheader mehr preis.
- Partielle `/config`-POSTs erhalten vorhandene Einstellungen, statt fehlende Bereiche mit Standardwerten zu überschreiben.
- Temporäre Cache-Dateien werden jetzt lokal im Schreibpfad erzeugt statt über eine globale Modulvariable.

## Neu in v1.58.0

- Einstellungen sind jetzt in linke Register gegliedert: Allgemein, Darstellung, Blöcke, System, Quellen, Märkte, Gebetszeiten und Info/Dienst.
- VPN-Status wird farblich hervorgehoben: erkannt/AN grünlich, nicht erkannt/AUS rotartig, manueller Hinweis in Akzentfarbe.
- Das Projekt enthält keine lokale Alt-Migration für frühere Testnamen mehr.
- Der Installer legt zusätzlich `~/.local/bin/dielage-uninstall` an, damit die systemd-User-Units auch nach dem Entpackordner zuverlässig entfernt werden können.
- Der Uninstaller stoppt/deaktiviert die systemd-User-Units, entfernt Unit-Dateien und stale Enablement-Symlinks, lädt systemd neu und räumt Helper/Plasmoid auf.

## Neu in v1.57.0

- Etwas mehr Luft unter dem Titel-/Aktualisiert-Bereich vor dem ersten Block.
- Mehr Abstand vor größeren Einstellungsüberschriften.
- Dienststatus-Prüfung zeigt jetzt direkt sichtbares Feedback und bei Fehlern die passenden Terminalbefehle.
- Systemstatus kann optional einen VPN-Status anzeigen; Erkennung über Routen, aktive VPN-Interfaces, NetworkManager und bekannte Werkzeuge wie Mullvad, WARP, Tailscale und NordVPN.
- Optionales VPN-Kürzel in den Einstellungen, falls automatische Erkennung nicht eindeutig ist.
- Arabische Klammerbegriffe in den islamischen Gebetszeiten werden normal statt fett gerendert.

KDE-Plasma-6-Widget für Linux mit Python 3.9+ für ein kompaktes **Lagebild**: RSS-Nachrichten, Wetter, amtliche Warnmeldungen, islamische Gebetszeiten, Märkte (Wechselkurse, Indizes, Aktien) und kompakte Linux-Systeminfo. Funktioniert auf dem Desktop **und** im Panel; die stärkste Darstellung entsteht auf einem hochformatigen zweiten oder dritten Bildschirm.

Das Projekt entstand als persönlicher Ersatz für ein Conky-Dashboard, weil Conky in meinem Wayland-/NVIDIA-Setup immer wieder Ärger gemacht hat. Die Lage ist deshalb bewusst als persönliche Arbeitsfläche gedacht: Sie funktioniert auch gut im Panel, ist aber besonders sinnvoll auf einem hochformatigen zweiten oder dritten Bildschirm und optisch am stärksten, wenn der Desktop-Hintergrund schlicht schwarz ist. Einzelne Blöcke könnten später eigene Widgets werden, müssen es aber nicht; der Kern bleibt ein persönliches Workflow-Werkzeug, das mit anderen geteilt wird, wenn sie genau so etwas brauchen.

## Neu in v1.52.2

- Weitere Härtung des lokalen Servers: `Origin: null` wird nicht mehr als erlaubter Browser-Origin akzeptiert.
- POST-Endpunkte erwarten jetzt `Content-Type: application/json`, damit einfache HTML-Formulare oder `no-cors`-Text-POSTs nicht als CSRF-Umweg funktionieren.
- Temporäre Cache-/Config-Dateien werden bei Schreibfehlern bestmöglich entfernt.

## Neu in v1.52.1

- **Installer schreibt jetzt auch atomar**: Die Aktualisierung einer bestehenden `config.json` beim Upgrade nutzt `tmp+rename` statt direktem Überschreiben — konsistent mit dem Server-Verhalten.
- **`tmp`-Dateien werden bei Schreibfehlern aufgeräumt** statt als Müll liegenzubleiben (Disk-Full / IO-Fehler / Ctrl+C).
- **Refresh ohne Stale-Daten**: Das Widget interpretiert die `already_running:true`-Antwort des Servers und wartet kurz vor dem nächsten Cache-Read, damit man nach „Aktualisieren" nicht weiterhin die alten Daten sieht, wenn ein Refresh bereits unterwegs ist.

## Neu in v1.52

- **Sicherer lokaler Server**: Browser-Origins von normalen Webseiten werden abgewiesen. Dadurch können Webseiten nicht mehr per CORS `config.json` inklusive lokaler API-Keys lesen oder die Konfiguration ändern. QML/Plasma und lokale Werkzeuge bleiben erlaubt.
- **Konfigurationsdateien werden atomar geschrieben**, damit parallele Speicher-/Reset-Vorgänge keine halbe JSON-Datei hinterlassen.
- **Refresh-Lock verbessert**: Wenn ein Refresh bereits läuft, startet kein zweiter Cache-Prozess.
- **Leere Wetterorte oder Warngebiete bleiben wirklich leer** statt alte Cache-Daten weiter anzuzeigen.
- **Cache-Sprache überschreibt nicht mehr die frisch geladene Konfigurationssprache**, damit die UI beim Start nicht kurz in die falsche Sprache kippt.
- Release-Zip bereinigt: keine `__pycache__`-/`.pyc`-Dateien.

## Neu in v1.51

- **Umbenennung der sichtbaren Oberfläche** auf „Die Lage" (DE) / „Daily Briefing" (EN). Die vollständige interne Vereinheitlichung auf `dielage` / `com.drissner.dielage` erfolgte später in der lokalen Entwicklungsphase.
- **Eigener Titel** in den Einstellungen — überschreibt Popup-Titel und Tooltip. Leer = Standard.
- **Block-Reihenfolge anpassbar** in den Einstellungen (Pfeil-hoch / Pfeil-runter).
- **Cross-Distro**: dnf (Fedora/RHEL) und zypper (openSUSE) werden für die Update-Erkennung jetzt unterstützt; der Installer schlägt Pakete für die richtige Distribution vor.
- **Hintergrunddienst-Erkennung**: läuft der lokale Helper nicht, zeigt das Widget einen Setup-Bildschirm statt eines leeren Popups.
- **Reset auf Standardwerte** in den Einstellungen — mit Bestätigungsdialog.
- **Versionsanzeige** unten in den Einstellungen (klein).
- **Sicherheit**: URL-Schema-Allowlist (nur http/https) im Fetcher; POST-Bodygröße im lokalen Server begrenzt.
- **Uninstaller** `./uninstall.sh` (mit `--purge` für komplettes Entfernen inkl. Config/Cache).
- **AppStream-Metainfo** für den KDE Store.

## Logo und Store-Assets

Die Store-Grafiken liegen in einem separaten Paket `die-lage-store-assets-v1.60.5.zip`. Darin enthalten:

- `dielage-icon.svg`
- `dielage-icon-256.png`
- `dielage-icon-512.png`
- `dielage-wordmark.svg`
- `dielage-wordmark-1200x400.png`

Für `metadata.json` wird nun ein paketrelativer Symbolpfad (`/icons/dielage.svg`) gesetzt, damit Plasma-Versionen mit Unterstützung für gebündelte Widget-Symbole das Die-Lage-Symbol in der Miniprogramm-Liste anzeigen können. Im Panel wird zusätzlich ein stark vereinfachtes `contents/images/dielage-panel.svg` verwendet, weil das große Dashboard-Symbol bei 16–24 px zu detailreich ist. In den Einstellungen kann alternativ ein Plasma-/Breeze-Symbol ausgewählt oder ein eigener Icon-Name eingetragen werden.

## Installation

```fish
cd ~/Downloads
unzip -o die-lage-v1.60.5.zip
cd die-lage-v1.60.5
chmod +x emergency-clean-dielage.sh install.sh uninstall.sh
./install.sh
```

Der Installer:

- legt nichts unter `/usr` an — alles bleibt unter `$HOME`
- installiert das Plasmoid nach `~/.local/share/plasma/plasmoids/com.drissner.dielage/`
- legt den Python-Helper unter `~/.local/bin/` ab
- richtet systemd-User-Units für Cache und lokalen HTTP-Helper auf `127.0.0.1:8765` ein
- erkennt die Distribution und schlägt optional fehlende Tools vor (`lspci`, `ip`, `nvidia-smi`, `checkupdates`)
- erhält bestehende Konfigurationen und ergänzt nur neue Felder

Falls das Widget nach der Installation nicht auftaucht, einmal Plasma neu starten:

```fish
systemctl --user restart plasma-plasmashell.service
```

## Deinstallation

```fish
dielage-uninstall         # Widget + Helper entfernen, Konfiguration bleibt
dielage-uninstall --purge # zusätzlich Config und Cache löschen
```

Falls `dielage-uninstall` nicht im PATH gefunden wird:

```fish
~/.local/bin/dielage-uninstall --purge
```

Wichtig für KDE-Store-Nutzer: Plasma kann das sichtbare Widget entfernen, aber systemd-User-Units, Helper-Skripte und Cache-Dateien bleiben sonst liegen. Für eine saubere Deinstallation immer den Uninstaller ausführen. Ja, Desktop-Linux hält gern ein kleines Nachlassverfahren ab.

## Im Panel

Das Widget kann ins Panel gezogen werden. Dort zeigt es ein kleines Symbol mit Plasma-Tooltip oder einen kompakten Warnstatus (umschaltbar in den Einstellungen unter „Panel-Darstellung"). Klick öffnet die volle Ansicht als Popup, Mittelklick aktualisiert.

Auf dem Desktop wird immer das vollständige Layout angezeigt, unabhängig vom Panel-Modus.

## Reihenfolge der Blöcke

In den Einstellungen unter „Reihenfolge der Blöcke" kann jeder Block einzeln nach oben oder unten verschoben werden. Ausgeblendete Blöcke behalten ihre Position; wird ein Block wieder eingeblendet, taucht er an seiner alten Stelle auf statt am Ende.

## KDE Store / manuelle Helper-Installation

Für den KDE Store gibt es zwei Artefakte:

1. `die-lage-1.60.5.plasmoid` für die normale Widget-Installation über Plasma/KDE Store.
2. `die-lage-v1.60.5.zip` als vollständiges Bundle mit Installer, Helper-Skripten und systemd-User-Units.
3. `die-lage-store-assets-v1.60.5.zip` als separates Paket mit KDE-Store-Grafiken.

Die KDE-Store-Installation installiert nur das Plasmoid. Der lokale Hintergrunddienst kann aus Sicherheits- und Paketierungsgründen nicht zuverlässig automatisch über den Store aktiviert werden. Nach dem ersten Start zeigt das Widget deshalb eine Einrichtungsseite mit dem Hinweis, das vollständige Bundle herunterzuladen und `./install.sh` einmalig auszuführen.

## Hintergrunddienst

Der lokale Helper läuft als systemd-User-Service auf `127.0.0.1:8765`. Der Server akzeptiert lokale QML/Tool-Anfragen, weist aber normale Webseiten-Origin-Header ab, damit Webseiten im Browser nicht die lokale Konfiguration oder API-Keys auslesen können. Er macht drei Dinge:

1. RSS-Feeds, Wetter, Warnungen, Gebetszeiten und Märkte periodisch abrufen
2. Den letzten Cache als JSON unter `~/.cache/die-lage/rss.json` ablegen
3. Konfigurationsänderungen aus dem QML-Widget entgegennehmen und persistieren

Status prüfen:

```fish
systemctl --user status dielage-local-server.service
systemctl --user status dielage-cache.timer
systemctl --user status dielage-cache-boot.timer
```

Cache liegt unter `~/.cache/die-lage/rss.json`, Konfiguration unter `~/.config/die-lage/config.json`.

## Daten und externe Dienste

Siehe `SOURCES.md`. Kurzform: Open-Meteo (Wetter, kein Key), AlAdhan (Gebetszeiten, kein Key), warnung.bund.de / NINA / MeteoAlarm / NWS (Warnungen, kein Key), Frankfurter (Wechselkurse, kein Key), Yahoo Finance / Twelve Data / Finnhub (Aktien & Indizes — Yahoo ohne Key, andere optional).

Alle Konfigurationsdaten inklusive optionaler API-Keys liegen ausschließlich lokal in `~/.config/die-lage/config.json`.

## Autor, Kontakt und Spenden

Autor: Gerald Drißner. Kontakt: https://drissner.media/kontakt

Optionaler Spendenlink: https://www.paypal.me/drissner

## Lizenz

Copyright © 2026 Gerald Drißner.

MIT. Siehe `LICENSE`.
