"""Laden der mitgelieferten Default-Konfiguration (Presets, Credits-Gewichte).

Selbst-Hoster ersetzen diese Dateien für den Produktivbetrieb typischerweise durch eigene
(siehe Programmierplan Abschnitt 3) — die hier ausgelieferten Werte sind Vorgaben, keine
für den produktiven Einsatz von urbanstudio kalibrierten Endwerte.
"""

from __future__ import annotations

import json
from functools import cache
from importlib import resources
from typing import Any


@cache
def load_imageformats(path: str | None = None) -> dict[str, Any]:
    if path is not None:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    with resources.files(__package__).joinpath("imageformats.json").open(encoding="utf-8") as f:
        return json.load(f)


@cache
def load_costweights(path: str | None = None) -> dict[str, Any]:
    if path is not None:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    with resources.files(__package__).joinpath("costweights.json").open(encoding="utf-8") as f:
        return json.load(f)
