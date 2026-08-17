# us-mediakit

Python-Library, CLI und optionaler Netzwerkdienst für Bild-Metadaten (EXIF/IPTC/XMP), Content Credentials (C2PA) und KI-gestützte Bildverarbeitung — Resize/Crop, Wasserzeichen, KI-Upscaling und KI-Bildbeschreibung, mit durchgängiger Provenienz-Weiterreichung bei jeder erzeugten Bildvariante.

**Status:** in aktiver Entwicklung. Phase 1 (Zuschnitt/Resize, Formate, Sicherheits-Grundhärtung)
ist umgesetzt. Metadaten, C2PA, Netzwerk-Dienst, KI-Provider und Wasserzeichen folgen in den
weiteren Phasen — siehe Roadmap unten.

## Ziele

- [x] Resize/Crop/Skalierung wie in der bisherigen PHP-Lösung, inklusive EXIF-Rotationskorrektur
- [ ] EXIF/IPTC/XMP lesen und schreiben, Content Credentials (C2PA) prüfen und erzeugen
- [ ] Metadaten und C2PA-Herkunftsnachweis werden bei jeder erzeugten Bildvariante automatisch geprüft und weitergereicht
- [ ] KI-Upscaling/Bildverbesserung über austauschbare Provider (u. a. selbst gehostete Modelle)
- [ ] KI-generierte Bildbeschreibungen/Alt-Texte über eine generische, OpenAI-kompatible Schnittstelle
- [ ] Sichtbares und unsichtbares Wasserzeichen sowie Erkennung unsichtbarer Wasserzeichen
- [ ] Nutzbar als Library, CLI-Tool und systemd-Dienst mit JSON-API

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Systemabhängigkeiten (macOS via Homebrew, Debian via `apt`): `ffmpeg`, `poppler-utils`
(für Video-Frame- bzw. PDF-Seiten-Extraktion). `exiftool` wird ab Phase 2 benötigt.

```bash
us-mediakit thumbnail photo.jpg --mode showcase_medium -o thumb.jpg
```

Verfügbare Presets stehen in [`src/us_mediakit/config/imageformats.json`](src/us_mediakit/config/imageformats.json),
die Fit-Modi sind in [`docs/fit-modes.md`](docs/fit-modes.md) mit Beispielbildern erklärt.

## Lizenz

Apache License 2.0, siehe [LICENSE](LICENSE).

## Mitwirken

Contribution-Richtlinien folgen mit dem ersten lauffähigen Release.
