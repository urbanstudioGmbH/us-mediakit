"""Abstrakte Provider-Schnittstellen.

`us_mediakit` selbst hat keinen voreingestellten KI-Anbieter (siehe Programmierplan
Abschnitt 2) — jede konkrete Implementierung unter `providers/` (Real-ESRGAN,
CodeFormer, SeedVR2, claid.ai, ein generischer OpenAI-kompatibler Vision-Chat) erfüllt
eine dieser beiden Schnittstellen. Ob und welche aktiv ist, entscheidet ausschließlich
die Konfiguration der jeweiligen Instanz.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ImageEnhanceResult:
    data: bytes
    provider: str
    external_cost_micros: int | None = None


class ImageEnhanceProvider(ABC):
    """Bild-rein/Bild-raus — Upscaling, Bildverbesserung, Gesichtsrestauration."""

    name: str

    @abstractmethod
    def enhance(
        self,
        data: bytes,
        *,
        target_width: int | None = None,
        target_height: int | None = None,
        restore_faces: bool = False,
    ) -> ImageEnhanceResult: ...


DEFAULT_CAPTION_PROMPT = (
    "Beschreibe dieses Bild in einem kurzen, prägnanten Satz auf Deutsch, "
    "geeignet als Alt-Text/Bildtitel."
)


class VisionChatProvider(ABC):
    """Generischer OpenAI-kompatibler Chat-Provider für Bildbeschreibungen."""

    name: str

    @abstractmethod
    def caption(self, image_data: bytes, *, prompt: str = DEFAULT_CAPTION_PROMPT) -> str: ...


class ProviderError(RuntimeError):
    """Ein Provider war erreichbar, hat die Anfrage aber nicht erfolgreich verarbeitet."""


class ProviderUnavailableError(ProviderError):
    """Ein Provider war nicht erreichbar (Netzwerk/Timeout) — Signal für Fallback-Logik."""
