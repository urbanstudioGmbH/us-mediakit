# Changelog

Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/1.0.0/), Versionierung nach [SemVer](https://semver.org/lang/de/).

## [Unreleased]

## [1.1.0] - 2026-08-18

### Hinzugefügt

- Docker-Support: `Dockerfile`/`docker-compose.yml`, automatisch gebautes und auf
  GitHub Container Registry veröffentlichtes Image (`ghcr.io/urbanstudiogmbh/us-mediakit`).
- `thumbnail`: `--mode`/`mode` ist jetzt optional — Alternative `--width`/`--height`
  (`width`/`height`) mit optionalem `--fit`/`fit` (Default `full`), ohne dafür vorher
  einen benannten Eintrag in `imageformats.json` anzulegen.
- `thumbnail`: `--align-x`/`--align-y` (`alignx`/`aligny`) jetzt auch über CLI und
  Netzwerk-Dienst steuerbar, nicht mehr nur als fest im Preset hinterlegter Wert —
  akzeptieren sowohl Schlüsselwörter (`left`/`center`/`right`, `top`/`center`/`bottom`)
  als auch numerische Prozentwerte 0–100.
- `thumbnail`: `--max-upscale-factor`/`max_upscale_factor` als explizites Opt-in für
  einfache (bikubische) Vergrößerung ohne KI-Provider, bis zu einem angegebenen Faktor.
  Ohne Angabe unverändertes bisheriges Verhalten (keine Vergrößerung).
- `thumbnail --video`: `--video-seek-seconds`/`video_seek_seconds` jetzt über CLI und
  Netzwerk-Dienst einstellbar, vorher nur auf Bibliotheks-Ebene möglich.
- `watermark invisible`: `--format` steuert jetzt das tatsächliche Ausgabeformat
  (vorher immer intern JPEG, unabhängig von der Dateiendung des Quellpfads).

### Geändert

- Unsichtbares Wasserzeichen nutzt keine externe `invisible-watermark`-Abhängigkeit
  mehr — der tatsächlich verwendete DWT-DCT-SVD-Algorithmus ist direkt in
  `watermark/_dwt_dct_svd.py` eingebaut (MIT-Lizenz, mit Attribution), identisches
  Verhalten. Damit entfällt die PyTorch-Abhängigkeit vollständig (kam nur über eine
  ungenutzte GAN-basierte Zusatzmethode der Bibliothek) und das `[watermark]`-Extra
  wird überflüssig: unsichtbares Wasserzeichen ist jetzt immer verfügbar, ohne
  gesonderte Installation.

## [1.0.0] - 2026-08-18

### Hinzugefügt

- Zuschnitt/Resize (`crop`/`greedycrop`/`greedyscalecrop`/`full`), Formaterkennung
  (inkl. HEIC/AVIF), Sicherheits-Grundhärtung, Video-/PDF-Frame-Extraktion.
- EXIF/IPTC/XMP lesen/schreiben über einen persistenten `exiftool`-Prozess, `strip_gps`,
  automatische Metadaten-Übernahme bei jeder erzeugten Bildvariante.
- C2PA Content Credentials (lesen/signieren/verifizieren), automatische
  Provenienz-Propagation bei jeder erzeugten Bildvariante.
- Netzwerk-Dienst (FastAPI/uvicorn), API-Key- und Admin-Token-Auth, Credits-basierte
  Abrechnung, Idempotenz (`request_id`), `dry_run`, cursor-basierter Usage-Export,
  Rate-Limiting (nginx + Credits/Minute + Video/PDF-Concurrency), systemd-/
  nginx-Betriebsdateien.
- KI-Provider-Schnittstellen für Bild-Upscaling/-Verbesserung und Bildbeschreibung,
  eingebaute Implementierungen für Real-ESRGAN/CodeFormer/SeedVR2/claid.ai und einen
  generischen OpenAI-kompatiblen Vision-Chat-Provider, YAML-basierte
  Provider-Konfiguration, Fallback auf einfaches Resize bei Provider-Ausfall.
- Sichtbares Wasserzeichen (Logo/Text), unsichtbares Wasserzeichen (DWT-DCT-SVD) und
  Erkennung als drei getrennte Operationen.
- Zuschnitt-Ausgabe zusätzlich in AVIF und HEIC/HEIF, mit klarem `422` statt stillem
  JPEG-Fallback bei unbekannten oder auf der Zielplattform nicht verfügbaren Formaten.
- Animierter WebP-Ausschnitt aus einem Video (`animated_webp`) als eigene Operation,
  mit fest gedeckelter Dauer/Framerate/Breite.
