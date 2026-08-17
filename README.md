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

Systemabhängigkeiten (macOS via Homebrew, Debian via `apt`): `ffmpeg`, `poppler-utils`,
`exiftool` (`libimage-exiftool-perl` unter Debian).

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

Vollständige Endpunkt-Referenz in [`docs/api-reference.md`](docs/api-reference.md),
Produktivbetrieb (systemd, nginx, Hardening) in [`docs/operations.md`](docs/operations.md),
KI-Provider konfigurieren in [`docs/providers.md`](docs/providers.md), C2PA-Zertifikat für
den Produktivbetrieb beantragen in [`docs/c2pa-conformance.md`](docs/c2pa-conformance.md).

## Lizenz

Apache License 2.0, siehe [LICENSE](LICENSE).

## Mitwirken

Siehe [CONTRIBUTING.md](CONTRIBUTING.md).
