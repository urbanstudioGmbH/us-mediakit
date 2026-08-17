"""Generische Bild-rein/Bild-raus-Schnittstelle über HTTP.

Es gibt für "Bild-Upscaling/-Verbesserung als HTTP-Dienst" keinen etablierten
Branchenstandard (anders als z. B. bei OpenAI-kompatiblen Chat-APIs) — der folgende
Vertrag ist deshalb projekteigen. Real-ESRGAN/CodeFormer/SeedVR2 laufen als eigene
Provider-Prozesse und müssen genau diesen Vertrag bedienen:

```
POST {endpoint}/enhance
{"image": "<base64>", "target_width": int|null, "target_height": int|null, "restore_faces": bool}

200:
{"image": "<base64>", "external_cost_micros": int|null}
```

`claid_ai.py` implementiert dieselbe `ImageEnhanceProvider`-Schnittstelle, spricht aber
gegen die tatsächliche claid.ai-REST-API, nicht gegen diesen Vertrag — Details dort.
"""

from __future__ import annotations

import base64

import httpx

from us_mediakit.providers.base import (
    ImageEnhanceProvider,
    ImageEnhanceResult,
    ProviderError,
    ProviderUnavailableError,
)


class HttpImageEnhanceProvider(ImageEnhanceProvider):
    """Basisklasse für Provider, die den projekteigenen HTTP-Vertrag oben bedienen."""

    def __init__(
        self,
        *,
        endpoint: str,
        name: str,
        timeout_seconds: float = 120.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.name = name
        self._endpoint = endpoint.rstrip("/")
        self._timeout_seconds = timeout_seconds
        # Injizierbar, damit Tests einen `httpx.MockTransport` unterschieben können,
        # ohne einen echten Provider-Prozess laufen lassen zu müssen.
        self._client = client or httpx.Client()

    def enhance(
        self,
        data: bytes,
        *,
        target_width: int | None = None,
        target_height: int | None = None,
        restore_faces: bool = False,
    ) -> ImageEnhanceResult:
        payload = {
            "image": base64.b64encode(data).decode("ascii"),
            "target_width": target_width,
            "target_height": target_height,
            "restore_faces": restore_faces,
        }

        try:
            response = self._client.post(
                f"{self._endpoint}/enhance", json=payload, timeout=self._timeout_seconds
            )
        except httpx.TransportError as exc:
            raise ProviderUnavailableError(f"Provider {self.name!r} nicht erreichbar: {exc}") from exc

        if response.status_code >= 500:
            raise ProviderUnavailableError(
                f"Provider {self.name!r} antwortete mit {response.status_code}: {response.text}"
            )
        if response.status_code >= 400:
            raise ProviderError(
                f"Provider {self.name!r} lehnte die Anfrage ab ({response.status_code}): {response.text}"
            )

        try:
            body = response.json()
            image_bytes = base64.b64decode(body["image"])
        except (KeyError, ValueError) as exc:
            raise ProviderError(f"Unerwartete Antwortstruktur von {self.name!r}: {response.text}") from exc

        return ImageEnhanceResult(
            data=image_bytes,
            provider=self.name,
            external_cost_micros=body.get("external_cost_micros"),
        )
