# ADS-B Watch Proxy

HTTP-Proxy zwischen einem ADS-B-Aggregator und der Garmin-Watch-App
[ADS-B Radar](https://github.com/W0rkingChr1s/ADS-B-Watch---Garmin). Er holt die Rohdaten,
filtert sie auf Radius, Höhenband und Zielanzahl und liefert ein Kompaktformat, das klein genug
für eine Uhr mit 96 kB Anwendungsspeicher ist.

**Ohne diesen Proxy ist die Watch App nutzlos.** Sie enthält absichtlich keinen Zugang zu einem
zentralen Dienst — jeder betreibt seinen eigenen.

## Warum es ihn gibt

Eine Connect-IQ-App auf der Instinct 2X hat 96 kB Speicher und spricht nur über Bluetooth durch
das Telefon. Ein roher Abruf beim Aggregator ist je nach Sektor 80 kB groß und würde die App
allein beim Parsen erschlagen. Der Proxy macht daraus 29–32 Byte pro Ziel: alles Rechenintensive
passiert hier, die Uhr zeichnet nur.

Dazu kommt das Rate-Limit: die freien Aggregatoren erlauben etwa einen Request pro Sekunde. Der
Cache hier ist deshalb keine Optimierung, sondern Voraussetzung.

## Start

```bash
docker run -d --name adsb-proxy -p 8080:8080 \
  -e ADSB_PROVIDER=adsblol \
  -e ADSB_TOKEN=ein-langes-zufaelliges-geheimnis \
  ghcr.io/w0rkingchr1s/adsb-watch-backend:latest
```

Oder lokal:

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
ADSB_PROVIDER=demo ADSB_TOKEN=testtoken uvicorn app.main:app --port 8080
```

Prüfen:

```bash
curl "http://localhost:8080/v1/traffic?lat=48.77&lon=11.43&nm=25" -H "X-Api-Token: testtoken"
# [["DLH4AB",127,8.3,34000,215,0], ...]
```

## Die Uhr braucht HTTPS

Connect IQ lehnt `http://` ab. Der Proxy selbst spricht HTTP; TLS gehört davor — ein Reverse
Proxy oder ein Tunnel. Ohne gültiges Zertifikat erreicht die Uhr ihn nicht, auch nicht im
eigenen WLAN.

## Konfiguration

Alles über Umgebungsvariablen mit dem Präfix `ADSB_`:

| Variable | Default | Bedeutung |
|---|---|---|
| `ADSB_PROVIDER` | `adsblol` | `adsblol`, `airplaneslive`, `adsbone`, `adsbexchange` oder `demo` |
| `ADSB_TOKEN` | — | **Pflicht.** Shared Secret, das die Uhr im Header `X-Api-Token` schickt. Ohne gesetzten Wert startet der Dienst nicht und antwortet 503 |
| `ADSB_API_KEY` | leer | nur für `adsbexchange` (RapidAPI) |
| `ADSB_CACHE_TTL` | `8` | Cache-Lebensdauer in Sekunden |
| `ADSB_MIN_UPSTREAM_INTERVAL` | `1.0` | minimaler Abstand zweier Upstream-Requests |
| `ADSB_MAX_TARGETS` | `20` | harte Obergrenze zurückgegebener Ziele |
| `ADSB_UPSTREAM_TIMEOUT` | `6.0` | Timeout gegen den Upstream |
| `ADSB_LOG_LEVEL` | `INFO` | Loglevel |

`ADSB_PROVIDER=demo` liefert erfundenen Verkehr ohne Upstream — praktisch für den ersten Test.
`/healthz` meldet in diesem Fall `"demo": true`; wer den Dienst überwacht, sollte darauf prüfen
und nicht bloß auf HTTP 200.

## Endpoints

**`GET /v1/traffic`** — Header `X-Api-Token` erforderlich.

| Parameter | Default | Bereich | Bedeutung |
|---|---|---|---|
| `lat`, `lon` | — | — | eigene Position, Pflicht |
| `nm` | `25` | 1–250 | Radius in nautischen Meilen |
| `alt_min` | `0` | -1500–60000 | Untergrenze des Höhenbands in Fuß |
| `alt_max` | `45000` | -1500–60000 | Obergrenze in Fuß |
| `max` | `12` | 1–50 | maximale Zielanzahl, zusätzlich serverseitig gedeckelt |
| `fmt` | `compact` | `compact`, `full` | Antwortformat |

`fmt=compact` liefert ein Array von Arrays, sortiert nach Distanz aufsteigend:

| Index | Typ | Bedeutung |
|---|---|---|
| 0 | String | Callsign, sonst Registrierung, sonst ICAO-Hex |
| 1 | int | Peilung vom Nutzer zum Ziel, 0–359 |
| 2 | float | Distanz in NM |
| 3 | int | barometrische Höhe in Fuß, `0` = am Boden |
| 4 | int | Kurs über Grund, `-1` = unbekannt |
| 5 | int | Vertikaltendenz: `-1` sinkt, `0` stabil, `1` steigt |

`fmt=full` liefert zusätzlich Groundspeed, Provider-Name und die Attribution der Datenquelle.

**`GET /healthz`** — ohne Token, meldet Zustand und ob der Demo-Modus aktiv ist.

## Datenquellen und ihre Bedingungen

Der Proxy holt die Daten dort, wo du es einstellst. Die Lizenzbedingungen der gewählten Quelle
einzuhalten ist Sache dessen, der ihn betreibt:

* **adsb.lol** — ODbL 1.0, Namensnennung erforderlich
* **airplanes.live** — ausdrücklich nur nicht-kommerzielle Nutzung
* **adsb.one** — siehe deren Bedingungen
* **ADS-B Exchange** — kostenpflichtig über RapidAPI

Bei `fmt=full` liefert der Proxy die passende Attribution mit.

## Was das hier nicht ist

Kein Kollisionswarnsystem und kein Luftlagebild im operativen Sinn. ADS-B-Daten sind 5–30
Sekunden alt, und ein erheblicher Teil des Luftverkehrs sendet gar kein ADS-B — Segelflug, viele
Ultraleichte, ein großer Teil der allgemeinen Luftfahrt, häufig Militär. Gerade der untere
Höhenbereich ist am lückenhaftesten. Für den Betrieb unbemannter Luftfahrzeuge bleiben der
Sichtkontakt, die offiziellen Quellen und die Betriebsgenehmigung maßgeblich.

## Entwicklung

```bash
ruff check . && ruff format --check . && pytest -q
```

51 Tests. Änderungen an `geo.py` oder `filters.py` ohne Test sind eine schlechte Idee: ein falsch
berechnetes Bearing sieht auf einem Radarbild vollkommen plausibel aus.

## Lizenz

MIT, siehe [LICENSE](LICENSE). Die Lizenz gilt für diesen Code — nicht für die Daten, die du
damit abrufst.
