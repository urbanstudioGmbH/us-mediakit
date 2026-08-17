# Security Policy

## Meldung von Sicherheitslücken

Bitte Sicherheitslücken **nicht** über ein öffentliches GitHub-Issue melden. Stattdessen:

- E-Mail an **post@urbanstudio.de** mit Betreff `[SECURITY] us-mediakit`.
- Alternativ über den privaten "Report a vulnerability"-Weg im GitHub-Security-Tab dieses Repos.

Wir bestätigen den Eingang innerhalb von 5 Werktagen und informieren über den weiteren Umgang (Einschätzung, Fix-Zeitplan, koordinierte Veröffentlichung).

## Besonders relevant für dieses Projekt

- **C2PA-Signierschlüssel**: `c2pa/sign.py` verarbeitet private Signierschlüssel. Schlüsselmaterial darf nie geloggt, in Fehlermeldungen ausgegeben oder in `usage_events` landen.
- **API-Keys**: Ausschließlich als Hash (`key_hash`) in der Datenbank gespeichert, nie im Klartext. Ein Fund von Klartext-Keys in Logs/DB ist als Sicherheitslücke zu behandeln.
- **Subprozess-Aufrufe** (`exiftool`, `ffmpeg`, `pdftoppm`): ausschließlich als Argument-Arrays, nie über eine Shell — Command-Injection-Vektor bei Dateinamen/Nutzereingaben.

## Unterstützte Versionen

Solange es kein 1.0-Release gibt, wird ausschließlich der `main`-Branch mit Sicherheitsfixes versorgt.
