# Docker

Fertiges `Dockerfile` + `docker-compose.yml` im Repo-Root, gedacht zum schnellen
Ausprobieren (lokal oder auf einem Server mit Docker-Unterstützung, z. B. via
Plesk-Docker-Extension) — für einen gehärteten Produktivbetrieb weiterhin
[`operations.md`](operations.md) (systemd + nginx, `DynamicUser`, `ProtectSystem`, ...).

## Fertiges Image (kein eigener Build nötig)

Bei jedem Push auf `main` und bei jedem Versions-Tag baut
[`.github/workflows/docker.yml`](../.github/workflows/docker.yml) das Image automatisch
für `linux/amd64` und `linux/arm64` und veröffentlicht es öffentlich auf GitHub Container
Registry — kein eigener Docker-Hub-Account nötig:

```bash
docker pull ghcr.io/urbanstudiogmbh/us-mediakit:latest
```

Versionierte Tags (`:1.0.0`, `:1.0`, `:1`) entstehen bei jedem `v*`-Git-Tag, `:latest`
folgt immer dem aktuellen `main`-Stand. Direkt startbar:

```bash
docker run -p 8000:8000 -e USMEDIAKIT_ADMIN_TOKEN=dev-token \
  -v us-mediakit-data:/data ghcr.io/urbanstudiogmbh/us-mediakit:latest
```

## Lokal selbst bauen und starten

```bash
docker compose up -d --build
```

Baut das Image (Python 3.12-slim + `ffmpeg`/`poppler-utils`/`exiftool`, `[server]`-Extra),
startet den Container, führt `alembic upgrade head` automatisch beim Start aus
(`deploy/docker-entrypoint.sh`) und bindet Port 8000. Standard-DB ist SQLite in einem
benannten Volume (`us-mediakit-data`, gemountet unter `/data`) — überlebt Neustarts und
komplette Container-Neuerstellung (`docker compose down && docker compose up -d`), nicht
aber `docker compose down -v` (löscht auch Volumes).

```bash
curl http://localhost:8000/health
docker compose exec us-mediakit us-mediakit admin api-key create --account-ref test --label docker-test
```

Swagger UI danach unter `http://localhost:8000/docs` (siehe
[`operations.md`](operations.md#api-dokumentation-swaggerredoc) zum Ablauf mit
"Authorize").

## Eigene Datenbank statt SQLite

Für MariaDB/PostgreSQL das passende Extra beim Bauen mitgeben und `USMEDIAKIT_DB` setzen:

```bash
docker build --build-arg EXTRAS=server,postgres -t us-mediakit .
docker run -p 8000:8000 \
  -e USMEDIAKIT_DB="postgresql+psycopg://user:pass@db-host/us_mediakit" \
  -e USMEDIAKIT_ADMIN_TOKEN=dev-token \
  us-mediakit
```

Das `/data`-Volume ist dann irrelevant (keine lokale SQLite-Datei mehr).

## Umgebungsvariablen

Dieselben wie im nicht-containerisierten Betrieb, siehe
[`operations.md`](operations.md#umgebungsvariablen) — `USMEDIAKIT_ADMIN_TOKEN` nur für
schnelles Ausprobieren im Klartext, für alles darüber hinaus `USMEDIAKIT_ADMIN_TOKEN_FILE`
auf ein gemountetes Secret zeigen lassen.

## Auf einem Server mit Plesk testen

Plesk selbst bringt (ab Obsidian, über die "Docker"-Extension) Unterstützung für
Container mit. Zwei praktikable Wege:

1. **Über die Plesk-Docker-Extension** (der direktere Weg dank des fertigen Images):
   In der Extension `ghcr.io/urbanstudiogmbh/us-mediakit:latest` als Image angeben (kein
   eigener Build nötig, öffentlich abrufbar, kein Registry-Login erforderlich), Port 8000
   auf einen freien Host-Port mappen, Umgebungsvariablen (`USMEDIAKIT_ADMIN_TOKEN`,
   `USMEDIAKIT_DB`, ...) eintragen, `/data` als persistentes Volume anlegen. Für HTTPS von
   außen anschließend in Plesk einen Reverse-Proxy-Vhost auf den gemappten Host-Port
   legen (Plesk kümmert sich dann um das Let's-Encrypt-Zertifikat).
2. **Per SSH direkt auf dem Server** (falls Zugriff besteht): entweder
   `docker run ...`/`docker compose up -d` mit dem fertigen Image wie oben, oder Repo
   klonen und `docker compose up -d --build` selbst bauen — unabhängig von Plesk selbst,
   Plesk sieht den laufenden Container nur als weiteren Prozess auf dem Server.

**Healthcheck:** `docker-compose.yml` prüft `GET /health` alle 30s — in Plesk taucht der
Container-Status entsprechend als "healthy"/"unhealthy" auf, sobald die Extension
Healthchecks anzeigt.

## Bekannte Grenzen dieses Docker-Aufbaus

- Läuft aktuell als `root` im Container (kein eigener `USER`) — für schnelles
  Ausprobieren unproblematisch, für einen gehärteten Produktivbetrieb eher der
  systemd-Weg in [`operations.md`](operations.md) mit `DynamicUser`.
- Ein einzelner Container = ein einzelner uvicorn-Prozess ohne Worker — für höheren
  Durchsatz mehrere Container hinter einem Load Balancer, nicht mehrere uvicorn-Worker
  in einem Container (das würde die In-Prozess-Zustände aus `operations.md`
  ["Rate-Limiting"](operations.md#rate-limiting--drei-unabhängige-ebenen) zusätzlich
  fragmentieren).
