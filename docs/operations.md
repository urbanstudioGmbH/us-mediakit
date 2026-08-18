# Betrieb

## Systemabhängigkeiten

Benötigt werden `ffmpeg`, `poppler-utils` (liefert `pdftoppm`), `exiftool`, sowie für
den in dieser Anleitung beschriebenen Aufbau `nginx` und `certbot`. Paketnamen
unterscheiden sich je Distribution:

| Distribution | Befehl |
|---|---|
| Debian / Ubuntu | `apt install python3-venv ffmpeg poppler-utils libimage-exiftool-perl nginx certbot python3-certbot-nginx` |
| Fedora / RHEL / Rocky / AlmaLinux | `dnf install python3 poppler-utils perl-Image-ExifTool nginx certbot python3-certbot-nginx` — `ffmpeg` liegt nicht in den Standard-Repos, [RPM Fusion](https://rpmfusion.org/Configuration) aktivieren, dann `dnf install ffmpeg` |
| Arch / Manjaro | `pacman -S python ffmpeg poppler perl-image-exiftool nginx certbot certbot-nginx` — `pdftoppm` kommt hier aus dem Paket `poppler`, nicht `poppler-utils` |

Nach der Installation prüfen, ob alle drei CLI-Tools tatsächlich im `PATH` des Nutzers
liegen, unter dem der systemd-Service läuft (siehe unten):

```bash
exiftool -ver && ffmpeg -version && pdftoppm -v
```

## Installation

```bash
python3 -m venv /opt/us-mediakit/venv
/opt/us-mediakit/venv/bin/pip install "us-mediakit[server,mysql,postgres]"
```

## Umgebungsvariablen

| Variable | Pflicht | Zweck |
|---|---|---|
| `USMEDIAKIT_DB` | empfohlen | SQLAlchemy-DB-URL. Default `sqlite:///us_mediakit.db` — für Produktivbetrieb MariaDB/PostgreSQL setzen. |
| `USMEDIAKIT_ADMIN_TOKEN_FILE` | ja, für Admin-Endpunkte | Datei mit dem Admin-Token (ein Token pro Instanz). Alternativ `USMEDIAKIT_ADMIN_TOKEN` direkt (nur für Entwicklung — im Klartext in der Prozessumgebung). |
| `USMEDIAKIT_C2PA_CERT_FILE` / `USMEDIAKIT_C2PA_KEY_FILE` | optional | PEM-Zertifikatskette/Privatschlüssel für die C2PA-Provenienz-Propagation. Ohne beide bleibt die Propagation ein No-Op (kein Fehler) — siehe `docs/c2pa-concepts.md`. |
| `USMEDIAKIT_MAX_CONCURRENT_VIDEO_PDF_JOBS` | optional | Tarifunabhängige Zusatzschwelle für gleichzeitige `ffmpeg`/`pdftoppm`-Jobs. Default `4`. |

**Gemeinsame Nutzung von CLI und Server:** Der Default-Wert von `USMEDIAKIT_DB` ist ein
*relativer* SQLite-Pfad — er zeigt auf `us_mediakit.db` im jeweiligen Arbeitsverzeichnis
des Prozesses. Laufen Server (`us-mediakit serve`) und CLI (z. B.
`us-mediakit admin api-key create`) aus unterschiedlichen Verzeichnissen oder mit
unterschiedlich gesetztem `USMEDIAKIT_DB`, sehen sie zwei getrennte Datenbanken — ein
per CLI erzeugter API-Key wäre dem Server dann unbekannt. Für lokale Entwicklung/Tests
entweder beide Prozesse aus demselben Verzeichnis starten, oder `USMEDIAKIT_DB` einmal
mit einem absoluten Pfad exportieren (`export USMEDIAKIT_DB="sqlite:////absoluter/pfad/us_mediakit.db"`,
vier Slashes), bevor beide gestartet werden. Im Produktivbetrieb ohnehin MariaDB/
PostgreSQL setzen — dort stellt sich die Frage nicht, da die URL keinen lokalen
Dateipfad enthält.

## Datenbank-Migrationen

```bash
USMEDIAKIT_DB=postgresql+psycopg://... alembic upgrade head
```

Bei jedem Deployment vor dem Neustart des Dienstes ausführen. `alembic.ini` liegt im
Repo-Root, `script_location` zeigt auf `src/us_mediakit/db/migrations`.

## Ersten Admin-Token und API-Key erzeugen

```bash
openssl rand -hex 32 > /var/lib/us-mediakit/admin.token
chmod 600 /var/lib/us-mediakit/admin.token

us-mediakit admin api-key create --account-ref "kunde-123" --label "Erster Test-Key"
```

## API-Dokumentation (Swagger/ReDoc)

FastAPI generiert die OpenAPI-Dokumentation automatisch aus den Endpunkt-Definitionen,
kein separater Schritt nötig. Sobald der Dienst läuft:

- `GET /docs` — interaktive Swagger-UI, Endpunkte direkt im Browser mit einem echten
  API-Key ausprobierbar: oben rechts auf "Authorize", dort **nur den reinen Key**
  eintragen (ohne `Bearer `-Präfix — das ergänzt Swagger selbst beim Absenden).
- `GET /redoc` — ReDoc, eher zum Lesen/Nachschlagen als zum interaktiven Testen.
- `GET /openapi.json` — das rohe OpenAPI-3.1-Schema, z. B. für Client-Codegenerierung.

## systemd (Socket-Aktivierung)

`deploy/us-mediakit.socket` und `deploy/us-mediakit.service` nach `/etc/systemd/system/`
kopieren, anpassen (Pfade, `USMEDIAKIT_DB`), dann:

```bash
systemctl daemon-reload
systemctl enable --now us-mediakit.socket
systemctl enable --now us-mediakit.service
```

Die Socket-Aktivierung (`--fd 3` in `ExecStart`) bedeutet: systemd öffnet den Port,
uvicorn übernimmt den bereits offenen Socket beim Start — kein Race zwischen
"Port ist offen" und "Anwendung ist bereit", nginx kann sofort proxy_pass machen.

### Hardening

`deploy/us-mediakit.service` enthält bereits eine sinnvolle Grundhärtung
(`DynamicUser`, `ProtectSystem=strict`, `NoNewPrivileges`, `MemoryDenyWriteExecute`, ...).
`ReadWritePaths` muss auf die tatsächlichen atomic-Verzeichnisse zeigen, in die
us-mediakit schreiben darf (Cache/Media) — alles andere bleibt read-only.

## nginx

`deploy/nginx-us-mediakit.conf` nach `/etc/nginx/sites-available/` kopieren, verlinken,
dabei **`limit_req_zone` in den `http{}`-Block von `nginx.conf` selbst** eintragen (nicht
in die Server-Config) — siehe Kommentar in der Datei.

### Zertifikat für einen rein internen Host

Ist der Host nicht von außen über Port 80 erreichbar (üblich für einen internen
Dienst wie diesen), funktioniert die Standard-HTTP-01-Challenge von certbot nicht.
Zwei Optionen:

1. **DNS-01-Challenge**: certbot-Plugin für den genutzten DNS-Provider verwenden
   (z. B. `certbot-dns-cloudflare`), kein offener Port 80 nötig.
2. Zertifikat auf einem öffentlich erreichbaren Host ausstellen und auf den internen
   Host synchronisieren (z. B. via `certbot-dns-*` auf einer Bastion + `rsync`/`scp`).

## Rate-Limiting — drei unabhängige Ebenen

1. **nginx** (`limit_req`/`limit_conn`): schützt gegen rohe Request-Flut, unabhängig
   von Auth/Abrechnung.
2. **Credits/Minute pro Plan-Tier** (`us_mediakit.billing.rate_limit.CreditsRateLimiter`):
   bewusst tarif-agnostisch — welches Limit für welchen `account_ref` gilt, kommt vom
   Kundenbereich, nicht aus us-mediakit selbst.
3. **Tarifunabhängige Video-/PDF-Concurrency** (`ConcurrencyLimiter`,
   `us_mediakit.api.limits.video_pdf_limiter`, `USMEDIAKIT_MAX_CONCURRENT_VIDEO_PDF_JOBS`):
   eine gemeinsame Instanz für den `is_video`/`is_pdf`-Zweig von `thumbnail` und für
   `/v1/animated_webp` — schützt den Server vor zu vielen gleichzeitigen
   `ffmpeg`/`pdftoppm`-Prozessen insgesamt, unabhängig vom Tarif.

**Bekannte Grenze:** Alle In-Prozess-Zustände (Idempotenz-Cache, Rate-Limiter) sind pro
Worker-Prozess. Bei mehreren uvicorn-Workern hinter nginx sieht jeder Worker nur seinen
eigenen Zustand — korrekt in der Abrechnung (die DB ist die gemeinsame Quelle der
Wahrheit), aber ein Retry kann auf einem anderen Worker landen und die Pipeline erneut
durchlaufen, statt aus dem Cache beantwortet zu werden. Für echte Mehr-Worker-Konsistenz
wäre ein gemeinsamer Speicher (Redis o. Ä.) nötig — bewusst nicht Teil des aktuellen
Funktionsumfangs, um die Abhängigkeitsliste schlank zu halten.

## Monitoring

`GET /health` ohne Auth, für Liveness-Checks (Load Balancer, systemd `ExecStartPost`,
externes Monitoring). Liefert `{"status": "ok"}`, sobald die Anwendung läuft — prüft
aktuell nicht die Erreichbarkeit von `exiftool`/`ffmpeg`/`pdftoppm` oder der Datenbank.
