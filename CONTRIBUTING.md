# Beitragen zu us-mediakit

Danke für dein Interesse an us-mediakit.

## Entwicklungsumgebung

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[server,dev,fast,watermark]"
pip install "cuttlefish @ git+https://github.com/urbanstudioGmbH/cuttlefish.git"
```

Der zweite `pip install` ist bewusst getrennt: `cuttlefish` (der OpenAI-kompatible
Mock-Server, den die `caption`-Tests gegen einen echten Prozess statt gegen Mocks
laufen lassen) ist auf PyPI durch ein fremdes, unverwandtes Paket belegt — ein
`pip install cuttlefish` ohne die Git-URL installiert das falsche Paket. `cuttlefish`
selbst verlangt Python 3.12+; unter 3.10/3.11 lässt sich dieser Schritt weglassen,
`tests/integration/test_caption.py` überspringt die betroffenen Tests dann automatisch.

Systemabhängigkeiten: `exiftool`, `ffmpeg`, `poppler-utils` — auf macOS via Homebrew,
für verschiedene Linux-Distributionen siehe die Tabelle in
[`docs/operations.md`](docs/operations.md#systemabhängigkeiten).

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
