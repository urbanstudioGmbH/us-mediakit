# us-mediakit

Python-Library, CLI und optionaler Netzwerkdienst für Bild-Metadaten (EXIF/IPTC/XMP), Content Credentials (C2PA) und KI-gestützte Bildverarbeitung — Resize/Crop, Wasserzeichen, KI-Upscaling und KI-Bildbeschreibung, mit durchgängiger Provenienz-Weiterreichung bei jeder erzeugten Bildvariante.

## Features

**Bildverarbeitung**
- Vier Fit-Modi (`crop`/`greedycrop`/`greedyscalecrop`/`full`) für Zuschnitt/Skalierung, inklusive EXIF-Rotationskorrektur
- HEIC/AVIF-Erkennung, Video-Frame- und PDF-Seiten-Extraktion als Bildquelle

**Metadaten & Provenienz**
- EXIF/IPTC/XMP lesen und schreiben, gezieltes Entfernen von Standortdaten (`strip_gps`)
- Content Credentials (C2PA) prüfen, erzeugen und automatisch an jede erzeugte Bildvariante weiterreichen

**Netzwerk-Dienst**
- API-Keys, Credits-basierte Abrechnung, Idempotenz (`request_id`) und Kostenschätzung (`dry_run`)
- Rate-Limiting auf mehreren Ebenen, systemd-/nginx-Betriebsdateien inklusive

**KI-Funktionen**
- Bild-Upscaling/-Verbesserung über austauschbare Provider (Real-ESRGAN, CodeFormer, SeedVR2, claid.ai, eigene), mit Fallback bei Ausfall
- Bildbeschreibungen über eine generische, OpenAI-kompatible Schnittstelle

**Wasserzeichen**
- Sichtbares Wasserzeichen (Logo/Text) und unsichtbares Wasserzeichen samt Erkennung

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[server,dev]"
```

Systemabhängigkeiten: `ffmpeg`, `poppler-utils`, `exiftool` — auf macOS via Homebrew
(`brew install ffmpeg poppler exiftool`), für Debian/Ubuntu/Fedora/Arch siehe die
Paketnamen-Tabelle in [`docs/operations.md`](docs/operations.md#systemabhängigkeiten).

### Library/CLI

```bash
us-mediakit thumbnail photo.jpg --mode showcase_medium -o thumb.jpg
us-mediakit meta read photo.jpg
us-mediakit c2pa verify photo.jpg
us-mediakit watermark invisible photo.jpg
us-mediakit watermark detect photo.jpg
```

Verfügbare Presets stehen in [`src/us_mediakit/config/imageformats.json`](src/us_mediakit/config/imageformats.json),
die Fit-Modi sind in [`docs/fit-modes.md`](docs/fit-modes.md) mit Beispielbildern erklärt.

### Netzwerk-Dienst

```bash
alembic upgrade head
USMEDIAKIT_ADMIN_TOKEN=dev-token us-mediakit serve
```

**Für CLI-Befehle wie `us-mediakit admin api-key create` in einem zweiten Terminal:**
Ohne gesetztes `USMEDIAKIT_DB` ist die Datenbank die relative Datei `us_mediakit.db` im
jeweiligen Arbeitsverzeichnis — CLI und Server müssen deshalb entweder aus demselben
Verzeichnis laufen, oder beide dieselbe absolute `USMEDIAKIT_DB`-URL gesetzt haben
(`export USMEDIAKIT_DB="sqlite:////absoluter/pfad/us_mediakit.db"`, vier Slashes), sonst
sieht der Server einen dort erzeugten API-Key nicht.

Läuft der Dienst, bringt er eine vollständige, automatisch generierte API-Dokumentation
gleich mit: interaktives Swagger UI unter `/docs`, ReDoc unter `/redoc`, rohes
OpenAPI-3.1-Schema unter `/openapi.json`.

Vollständige Endpunkt-Referenz in [`docs/api-reference.md`](docs/api-reference.md),
Produktivbetrieb (systemd, nginx, Hardening) in [`docs/operations.md`](docs/operations.md),
Docker-Betrieb (inkl. Hinweisen für Server mit Plesk) in [`docs/docker.md`](docs/docker.md),
KI-Provider konfigurieren in [`docs/providers.md`](docs/providers.md), C2PA-Zertifikat für
den Produktivbetrieb beantragen in [`docs/c2pa-conformance.md`](docs/c2pa-conformance.md).

### Docker

```bash
docker compose up -d --build
```

Details, eigene Datenbank statt SQLite und Hinweise zum Testen auf einem Server mit
Plesk in [`docs/docker.md`](docs/docker.md).

## Lizenz

Apache License 2.0, siehe [LICENSE](LICENSE).

## Mitwirken

Siehe [CONTRIBUTING.md](CONTRIBUTING.md).
