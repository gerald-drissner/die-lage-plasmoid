# Quellen und API-Hinweise

Diese Datei fasst die externen Quellen zusammen, die "Die Lage" / "Daily Briefing" nutzt oder in den Einstellungen erwähnt. Die URLs sind bewusst direkt lesbar, damit man sie auch außerhalb des Plasmoids prüfen kann.

## Wetter

Quelle: Open-Meteo

- https://open-meteo.com/
- https://open-meteo.com/en/docs

Open-Meteo ist eine offene Wetter-API und kann ohne API-Key genutzt werden. Im Widget werden die Daten nur für die kompakte Textanzeige verwendet. Wetterorte werden als `Name|Breitengrad|Längengrad` eingetragen. Koordinaten lassen sich z. B. über OpenStreetMap oder einen Geocoder ermitteln.

## Islamische Gebetszeiten

Quelle: AlAdhan Prayer Times API

- https://aladhan.com/prayer-times-api
- https://aladhan.com/calculation-methods

Die Ortsfelder werden als Stadt und Land an die API gesendet. Sinnvoll sind übliche englische Orts-/Ländernamen, z. B. `Berlin` und `Germany`. Die Berechnungsmethode ist eine Zahl. Häufige Werte: `3` Muslim World League, `2` ISNA, `4` Umm al-Qura Makkah, `5` Egyptian Authority, `12` France, `13` Diyanet Turkey.

## Warnmeldungen

Quelle: BBK / warnung.bund.de / NINA

- https://warnung.bund.de/
- https://warnung.bund.de/meldungen
- https://nina.api.bund.dev/

NINA ist in diesem Widget die deutsche Quelle für Warnmeldungen. Die Gebietscodes sind die von warnung.bund.de/NINA erwarteten Ortscodes. Aktuelles Format: `NINA|Berlin|110000000000`. Das alte Zwei-Spalten-Format bleibt aus Kompatibilitätsgründen lesbar.

Weitere unterstützte Quellen:

- Österreich punktgenau: GeoSphere/ZAMG, Format `GEOSPHERE|Bludenz|47.1527|9.8276`
- Europa/Länderfeeds: MeteoAlarm, Format `METEOALARM|Österreich|austria|Vorarlberg`
- USA punktbasiert: National Weather Service, Format `NWS|El Paso|31.7725|-106.461|El Paso`
- Eigene Atom-/RSS-Feeds: `URL|Eigener Feed|https://example.org/warnings.atom`

Quellen:

- USA: https://api.weather.gov/
- Österreich: https://openapi.hub.geosphere.at/warnapi/v1/
- Schweiz: https://www.meteoswiss.admin.ch/ und https://opendatadocs.meteoswiss.ch/
- Europa: https://meteoalarm.org/ und https://api.meteoalarm.org/

## Märkte

Quellen:

- Frankfurter / Wechselkurse: https://frankfurter.dev/
- Twelve Data: https://twelvedata.com/docs
- Finnhub: https://finnhub.io/register und https://finnhub.io/docs/api/quote
- Yahoo Finance fallback: öffentliche Chart-/Quote-Endpunkte, ohne API-Key, aber weniger offiziell dokumentiert.

API-Keys werden lokal in `~/.config/die-lage/config.json` gespeichert.

## Systeminfo

Der Systemblock nutzt lokale Linux-Werkzeuge, wenn sie vorhanden sind. Die Werkzeuge werden beim Installieren geprüft und als Hinweis ausgegeben, aber nicht mehr im Widget selbst angezeigt. Optional hilfreich:

- `nvidia-smi` aus den NVIDIA-Tools für NVIDIA-Treiber und GPU-Modell
- `lspci` aus `pciutils` für Grafikkarten-/Treiberinformationen
- `ip` aus `iproute2` für LAN-IP und Gateway
- `resolvectl` aus systemd für DNS
- `checkupdates` aus `pacman-contrib` oder alternativ `pacman -Qu` / `apt list --upgradable` für Updates

Die öffentliche IP/ISP-Abfrage ist standardmäßig deaktiviert und nutzt eine externe Anfrage, wenn sie ausdrücklich eingeschaltet wird.


## Warnquellen / Warning sources

Unterstützte Zeilenformate im Warngebiete-Feld:

```text
NINA|Berlin|110000000000
GEOSPHERE|Bludenz|47.1527|9.8276
METEOALARM|Österreich|austria|Vorarlberg
METEOALARM|Schweiz|switzerland
METEOALARM|Europa|europe
NWS|El Paso|31.7725|-106.461|El Paso
NWS|Nashville|36.1626|-86.7816|Davidson
URL|Eigener Feed|https://example.org/warnings.atom
```

- `NINA` nutzt die NINA/warnung.bund.de-API des BBK. `DE` bleibt aus Kompatibilitätsgründen lesbar, wird aber im UI nicht mehr als neues Format ausgegeben.
- `METEOALARM` nutzt die öffentlichen Atom-Feeds von MeteoAlarm, z. B. `austria`, `switzerland`, `europe`.
- `NWS` nutzt die API des US National Weather Service für aktive Warnungen an einem Punkt.
- `URL` liest einen eigenen Atom- oder RSS-Feed.
