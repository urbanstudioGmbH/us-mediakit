# us-mediakit

Python-Library, CLI und optionaler Netzwerkdienst für Bild-Metadaten (EXIF/IPTC/XMP), Content Credentials (C2PA) und KI-gestützte Bildverarbeitung — Resize/Crop, Wasserzeichen, KI-Upscaling und KI-Bildbeschreibung, mit durchgängiger Provenienz-Weiterreichung bei jeder erzeugten Bildvariante.

**Status:** in aktiver Entwicklung. Phasen 1–4 (Zuschnitt, Metadaten, C2PA Content
Credentials, Netzwerk-Dienst mit Konten/Metering) sind umgesetzt. KI-Provider und
Wasserzeichen folgen in Phase 5/6 — siehe Roadmap unten.

## Ziele

- [x] Resize/Crop/Skalierung wie in der bisherigen PHP-Lösung, inklusive EXIF-Rotationskorrektur
- [x] EXIF/IPTC/XMP lesen und schreiben, Content Credentials (C2PA) prüfen und erzeugen
- [x] Metadaten und C2PA-Herkunftsnachweis werden bei jeder erzeugten Bildvariante automatisch geprüft und weitergereicht
- [x] Nutzbar als Library, CLI-Tool und systemd-Dienst mit JSON-API
- [ ] KI-Upscaling/Bildverbesserung über austauschbare Provider (u. a. selbst gehostete Modelle)
- [ ] KI-generierte Bildbeschreibungen/Alt-Texte über eine generische, OpenAI-kompatible Schnittstelle
- [ ] Sichtbares und unsichtbares Wasserzeichen sowie Erkennung unsichtbarer Wasserzeichen

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
```

Verfügbare Presets stehen in [`src/us_mediakit/config/imageformats.json`](src/us_mediakit/config/imageformats.json),
die Fit-Modi sind in [`docs/fit-modes.md`](docs/fit-modes.md) mit Beispielbildern erklärt.

### Netzwerk-Dienst

```bash
alembic upgrade head
USMEDIAKIT_ADMIN_TOKEN=dev-token us-mediakit serve
```

Vollständige Endpunkt-Referenz in [`docs/api-reference.md`](docs/api-reference.md),
Produktivbetrieb (systemd, nginx, Hardening) in [`docs/operations.md`](docs/operations.md).

## Lizenz

Apache License 2.0, siehe [LICENSE](LICENSE).

## Mitwirken

Contribution-Richtlinien folgen mit dem ersten lauffähigen Release.
