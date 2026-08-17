"""CodeFormer (Gesichtsrestauration) als eigener Provider-Prozess.

Wird typischerweise als Zusatzschritt nach dem eigentlichen Upscaling aufgerufen
(`restore_faces=True`, siehe `api/v1/ai_upscale.py`), ist aber ein eigenständiger,
unabhängig konfigurierbarer Provider — kein Automatismus, der an Real-ESRGAN gekoppelt ist.
"""

from __future__ import annotations

import httpx

from us_mediakit.providers.image_enhance import HttpImageEnhanceProvider


class CodeFormerProvider(HttpImageEnhanceProvider):
    def __init__(
        self, *, endpoint: str, timeout_seconds: float = 120.0, client: httpx.Client | None = None
    ) -> None:
        super().__init__(
            endpoint=endpoint, name="codeformer", timeout_seconds=timeout_seconds, client=client
        )
