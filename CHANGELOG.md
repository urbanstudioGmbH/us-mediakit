# Changelog

Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/1.0.0/), Versionierung nach [SemVer](https://semver.org/lang/de/).

## [Unreleased]

### Hinzugefügt

- Docker-Support: `Dockerfile`/`docker-compose.yml`, automatisch gebautes und auf
  GitHub Container Registry veröffentlichtes Image (`ghcr.io/urbanstudiogmbh/us-mediakit`).

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
