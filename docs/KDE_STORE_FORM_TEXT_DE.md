# KDE Store Formulartext — Deutsch

## Titel

Die Lage (Daily Briefing)

## Kurzbeschreibung

Kompaktes Lagebild für KDE Plasma: Nachrichten, Wetter, Warnmeldungen, Gebetszeiten, Märkte und Systemstatus.

## Beschreibung

Der Name „Die Lage“ ist bewusst journalistisch gemeint: Er steht für den aktuellen Stand der Dinge, also für die Frage, was gerade wichtig ist und im Blick bleiben sollte. In der englischen Oberfläche heißt das Widget „Daily Briefing“.

Die Lage ist ein kompaktes Lagebild direkt auf dem KDE-Plasma-Desktop oder im Panel: RSS-Nachrichten aus frei konfigurierbaren Quellen, Wetter für mehrere Orte, amtliche Warnmeldungen über NINA, MeteoAlarm, GeoSphere, US-NWS oder eigene Feeds, islamische Gebetszeiten, Wechselkurse, Indizes, Aktien sowie optionale Linux-Systeminformationen inklusive Netzwerk- und VPN-Status.

Das Widget entstand als mein persönlicher Ersatz für Conky, weil Conky in meinem Wayland-/NVIDIA-Setup immer wieder Ärger gemacht hat. Es ist deshalb kein generisches Alles-für-alle-Widget, sondern ein persönliches Arbeitsdashboard, das ich mit anderen teile, wenn sie genau so etwas sinnvoll finden. Es funktioniert auch gut im Panel, entfaltet seine Stärke aber besonders auf einem hochformatigen zweiten oder dritten Monitor; am schönsten wirkt es mit einem schwarzen Desktop-Hintergrund.

Die Reihenfolge der Blöcke ist einstellbar. Blöcke können ein- und ausgeklappt werden. Das Widget unterstützt Deutsch und Englisch, Desktop- und Panel-Betrieb, eigene Titel, Schriftgrößen, Akzentfarbe, wählbares Panel-Symbol und lokale Konfiguration. Ob einzelne Teile später als eigene Widgets ausgelagert werden, ist offen; aktuell ist Die Lage bewusst als ein zusammenhängendes Lagebild für den eigenen Arbeitsalltag gedacht.

Wichtig: Dieses Widget ist nicht rein QML. Für RSS, Wetter, Warnungen, Märkte und Systemstatus braucht es einen kleinen lokalen Hintergrunddienst. Die KDE-Store-Installation installiert das sichtbare Plasmoid. Nach dem ersten Start zeigt das Widget eine Einrichtungsseite. Laden Sie zusätzlich das vollständige Release-Zip herunter, entpacken Sie es und führen Sie einmalig `./install.sh` aus. Der Dienst läuft danach als normaler systemd-User-Service ohne Root-Rechte.

## Schlagwörter

KDE, Plasma, Plasmoid, Widget, RSS, Nachrichten, Wetter, Warnmeldungen, NINA, MeteoAlarm, Gebetszeiten, Märkte, Aktien, Systemmonitor, VPN

## Hinweis für die Installationsbeschreibung

Die KDE-Store-Installation installiert nur das Plasma-Widget. Für die eigentlichen Daten wird zusätzlich der lokale Helper benötigt. Bitte laden Sie das vollständige Release-Zip von GitHub herunter, entpacken Sie es und führen Sie einmalig `./install.sh` aus.
