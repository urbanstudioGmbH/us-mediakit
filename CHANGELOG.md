# Changelog

Format angelehnt an [Keep a Changelog](https://keepachangelog.com/de/1.0.0/), Versionierung nach [SemVer](https://semver.org/lang/de/).

## [Unreleased]

### Hinzugefügt

- Projekt-Grundgerüst (Paketstruktur, CI, Lizenz).
- Phase 1: Zuschnitt/Resize (crop/greedycrop/greedyscalecrop/full), Formaterkennung
  (inkl. HEIC/AVIF), Sicherheits-Grundhärtung, Video-/PDF-Frame-Extraktion.
- Phase 2: EXIF/IPTC/XMP lesen/schreiben über einen persistenten `exiftool`-Prozess,
  `strip_gps`, automatische Metadaten-Übernahme bei jeder erzeugten Bildvariante.
- Phase 3: C2PA Content Credentials (lesen/signieren/verifizieren) über `c2pa-python`,
  automatische Provenienz-Propagation gemäß Programmierplan Abschnitt 5a.
- Phase 4: Netzwerk-Dienst (FastAPI/uvicorn), API-Key- und Admin-Token-Auth, Credits-
  basierte Abrechnung, Idempotenz (`request_id`), `dry_run`, cursor-basierter Usage-
  Export, Rate-Limiting (nginx + Credits/Minute + Video/PDF-Concurrency), systemd-/
  nginx-Betriebsdateien.
- Phase 5: KI-Provider-Schnittstellen (`ImageEnhanceProvider`, `VisionChatProvider`),
  eingebaute Implementierungen für Real-ESRGAN/CodeFormer/SeedVR2/claid.ai und einen
  generischen OpenAI-kompatiblen Vision-Chat-Provider, YAML-basierte Provider-Konfiguration
  (`providers/registry.py`), `POST /v1/caption` (`only_if_empty`, BYOK-Override) und
  `POST /v1/ai_upscale` (`restore_faces` als separat abgerechneter CodeFormer-Zusatzschritt,
  Fallback auf einfaches Resize bei Provider-Ausfall).
