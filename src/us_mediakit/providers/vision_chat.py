"""Generischer OpenAI-kompatibler Vision-Chat-Provider für Bildbeschreibungen.

Funktioniert identisch für ein selbst gehostetes Gemma-Vision-Modell oder einen
BYOK-Endpunkt (Kunden-eigener API-Key gegen einen beliebigen OpenAI-kompatiblen
Dienst) — beides ist derselbe Vertrag, nur mit unterschiedlicher `base_url`/`api_key`.
"""

from __future__ import annotations

import base64

import httpx

from us_mediakit.core.formats import get_content_type, get_image_type_from_bytes
from us_mediakit.providers.base import (
    DEFAULT_CAPTION_PROMPT as DEFAULT_PROMPT,
)
from us_mediakit.providers.base import (
    ProviderError,
    ProviderUnavailableError,
    VisionChatProvider,
)


class OpenAICompatibleVisionProvider(VisionChatProvider):
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None = None,
        timeout_seconds: float = 60.0,
        name: str = "openai-compatible",
    ) -> None:
        self.name = name
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout_seconds = timeout_seconds

    def caption(self, image_data: bytes, *, prompt: str = DEFAULT_PROMPT) -> str:
        mime_type = get_content_type(get_image_type_from_bytes(image_data) or "") or "image/jpeg"
        data_uri = f"data:{mime_type};base64,{base64.b64encode(image_data).decode('ascii')}"

        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        payload = {
            "model": self._model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": data_uri}},
                    ],
                }
            ],
        }

        try:
            response = httpx.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=headers,
                timeout=self._timeout_seconds,
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
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, ValueError) as exc:
            raise ProviderError(f"Unerwartete Antwortstruktur von {self.name!r}: {response.text}") from exc
