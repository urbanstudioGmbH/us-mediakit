"""SeedVR2 als eigener Provider-Prozess. Braucht in jeder Variante eine dedizierte GPU
(siehe Ressourcentabelle in docs/providers.md) — Einsatzempfehlung: stark degradiertes
Ausgangsmaterial, nicht der Standardfall."""

from __future__ import annotations

import httpx

from us_mediakit.providers.image_enhance import HttpImageEnhanceProvider


class SeedVR2Provider(HttpImageEnhanceProvider):
    def __init__(
        self,
        *,
        endpoint: str,
        variant: str = "3b",
        timeout_seconds: float = 180.0,
        client: httpx.Client | None = None,
    ) -> None:
        super().__init__(
            endpoint=endpoint,
            name=f"seedvr2-{variant}",
            timeout_seconds=timeout_seconds,
            client=client,
        )
