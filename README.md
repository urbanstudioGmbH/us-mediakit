# us-mediakit

Python-Library, CLI und optionaler Netzwerkdienst für Bild-Metadaten (EXIF/IPTC/XMP), Content Credentials (C2PA) und KI-gestützte Bildverarbeitung — Resize/Crop, Wasserzeichen, KI-Upscaling und KI-Bildbeschreibung, mit durchgängiger Provenienz-Weiterreichung bei jeder erzeugten Bildvariante.

**Status:** in Planung, noch kein lauffähiger Code. Der aktuelle Umsetzungsplan liegt in einem separaten internen Dokument, öffentliche Roadmap folgt hier, sobald Phase 1 startet.

## Ziele

- EXIF/IPTC/XMP lesen und schreiben, Content Credentials (C2PA) prüfen und erzeugen
- Resize/Crop/Skalierung wie in der bisherigen PHP-Lösung, inklusive EXIF-Rotationskorrektur
- Metadaten und C2PA-Herkunftsnachweis werden bei jeder erzeugten Bildvariante automatisch geprüft und weitergereicht
- KI-Upscaling/Bildverbesserung über austauschbare Provider (u. a. selbst gehostete Modelle)
- KI-generierte Bildbeschreibungen/Alt-Texte über eine generische, OpenAI-kompatible Schnittstelle
- Sichtbares und unsichtbares Wasserzeichen sowie Erkennung unsichtbarer Wasserzeichen
- Nutzbar als Library, CLI-Tool und systemd-Dienst mit JSON-API

## Lizenz

Apache License 2.0, siehe [LICENSE](LICENSE).

## Mitwirken

Contribution-Richtlinien folgen mit dem ersten lauffähigen Release.
