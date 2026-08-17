"""Real-ESRGAN als eigener Provider-Prozess, angesprochen über den generischen
Bild-rein/Bild-raus-HTTP-Vertrag (siehe `image_enhance.py`).

Läuft nicht in-process — Modellgewichte werden nicht mit us-mediakit ausgeliefert.
"""

from __future__ import annotations

import httpx

from us_mediakit.providers.image_enhance import HttpImageEnhanceProvider


class RealEsrganProvider(HttpImageEnhanceProvider):
    def __init__(
        self, *, endpoint: str, timeout_seconds: float = 120.0, client: httpx.Client | None = None
    ) -> None:
        super().__init__(
            endpoint=endpoint, name="real-esrgan", timeout_seconds=timeout_seconds, client=client
        )
