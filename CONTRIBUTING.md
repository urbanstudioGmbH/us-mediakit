# Beitragen zu us-mediakit

Danke für dein Interesse an us-mediakit. Das Projekt befindet sich aktuell im Aufbau (siehe Phasenplan in den Issues/Milestones) — Contribution-Workflow im Detail wird mit dem ersten lauffähigen Release ergänzt.

## Entwicklungsumgebung

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[server,dev,fast,watermark]"
```

Systemabhängigkeiten (macOS via Homebrew, Debian via `apt`): `exiftool`, `ffmpeg`, `poppler-utils`.

## Tests & Lint

```bash
pytest
ruff check src tests
mypy src
```

## Pull Requests

- Ein PR pro thematisch abgeschlossener Änderung.
- Tests für neues Verhalten sind Pflicht, nicht optional.
- Docstrings/Doku unter `docs/` bei API-relevanten Änderungen mitpflegen.

## Code of Conduct

Sachlicher, respektvoller Umgang. Bei Verstößen: `post@urbanstudio.de` kontaktieren.
