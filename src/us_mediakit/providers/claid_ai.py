"""claid.ai — echter externer Dienst, kein selbst kontrollierter Provider-Prozess.

Request-/Response-Form entspricht dem tatsächlichen claid.ai-Verhalten aus einer
bestehenden Produktivintegration. Als reiner externer Dienst wird claid.ai wie jeder
andere `ImageEnhanceProvider` behandelt — kein Sonderfall im restlichen Code.

**Nicht verifiziert:** ob und in welchem Feld claid.ai die tatsächlichen Kosten einer
Anfrage in der Antwort zurückmeldet — deshalb bleibt `external_cost_micros` hier `None`.
Vor Produktivbetrieb gegen die aktuelle claid.ai-API-Dokumentation prüfen, statt ein
plausibel klingendes Feld zu erfinden.
"""

from __future__ import annotations

import base64

import httpx

from us_mediakit.core.formats import get_content_type, get_image_type_from_bytes
from us_mediakit.providers.base import (
    ImageEnhanceProvider,
    ImageEnhanceResult,
    ProviderError,
    ProviderUnavailableError,
)

CLAID_ENDPOINT = "https://api.claid.ai/v1-beta1/image/edit"


class ClaidAiProvider(ImageEnhanceProvider):
    def __init__(
        self,
        *,
        api_key: str,
        upscale_mode: str = "smart_enhance",
        timeout_seconds: float = 120.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.name = "claid-ai"
        self._api_key = api_key
        self._upscale_mode = upscale_mode
        self._timeout_seconds = timeout_seconds
        self._client = client or httpx.Client()

    def enhance(
        self,
        data: bytes,
        *,
        target_width: int | None = None,
        target_height: int | None = None,
        restore_faces: bool = False,
    ) -> ImageEnhanceResult:
        image_type = get_image_type_from_bytes(data) or "jpg"
        mime_type = get_content_type(image_type) or "image/jpeg"
        format_name = "jpeg" if image_type == "jpg" else image_type  # claid erwartet den Formatnamen, kein MIME-Typ

        request: dict = {
            "input": f"data:{mime_type};base64,{base64.b64encode(data).decode('ascii')}",
            "operations": {
                "restorations": {"upscale": self._upscale_mode, "polish": False},
                "adjustments": {"sharpness": 0},
            },
            "output": {"format": {"type": format_name}},
        }
        if target_width and target_height:
            request["operations"]["resizing"] = {
                "width": target_width,
                "height": target_height,
                "fit": "cover",
            }
        if format_name not in ("png", "webp"):
            request["output"]["format"]["quality"] = 90
        elif format_name == "png":
            request["output"]["format"]["compression"] = "optimal"
        else:
            request["output"]["format"]["compression"] = {"type": "lossy"}

        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}

        try:
            response = self._client.post(
                CLAID_ENDPOINT, json=request, headers=headers, timeout=self._timeout_seconds
            )
        except httpx.TransportError as exc:
            raise ProviderUnavailableError(f"claid.ai nicht erreichbar: {exc}") from exc

        if response.status_code >= 500:
            raise ProviderUnavailableError(
                f"claid.ai antwortete mit {response.status_code}: {response.text}"
            )
        if response.status_code >= 400:
            raise ProviderError(
                f"claid.ai lehnte die Anfrage ab ({response.status_code}): {response.text}"
            )

        try:
            tmp_url = response.json()["data"]["output"]["tmp_url"]
        except (KeyError, ValueError) as exc:
            raise ProviderError(f"Unerwartete Antwortstruktur von claid.ai: {response.text}") from exc

        try:
            download = self._client.get(tmp_url, timeout=self._timeout_seconds)
            download.raise_for_status()
        except httpx.HTTPError as exc:
            raise ProviderUnavailableError(f"claid.ai-Ergebnis konnte nicht geladen werden: {exc}") from exc

        return ImageEnhanceResult(data=download.content, provider=self.name, external_cost_micros=None)
