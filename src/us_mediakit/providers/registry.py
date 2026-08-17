"""Baut konkrete Provider-Instanzen aus einer YAML-Konfigurationsdatei.

**Vorläufige Entscheidung, kein endgültig festgelegtes Format:** Der Programmierplan
listet "Provider-Konfigurationsformat (ENV vs. YAML-Datei) final festlegen" explizit als
offenen Punkt vor Umsetzungsstart (Abschnitt 9) und zeigt in Abschnitt 3 nur eine
YAML-Beispielskizze, keine verbindliche Spezifikation. Dieses Modul setzt genau jene
Skizze um, damit Phase 5 überhaupt lauffähig ist — die endgültige Festlegung (die auch
auf ENV-Variablen statt YAML fallen könnte) bleibt ein offener Punkt.

Erwartetes Format (Pfad über `USMEDIAKIT_PROVIDERS_CONFIG`):

```yaml
providers:
  caption:
    default: null              # Instanz-Default, z. B. "self-hosted-gemma"
    base_url: "http://localhost:8803/v1"
    model: "gemma-vision"
    api_key_env: null          # Name einer Umgebungsvariable, falls der Endpunkt Auth braucht
  ai_upscale:
    default: null               # Instanz-Default, z. B. "real-esrgan"
    registered:
      real-esrgan: {endpoint: "http://localhost:8801"}
      codeformer:  {endpoint: "http://localhost:8802"}
      seedvr2-3b:  {endpoint: "http://localhost:8804"}
      claid-ai:    {api_key_env: "CLAID_API_KEY"}
```
"""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Any

import yaml

from us_mediakit.providers.base import ImageEnhanceProvider, VisionChatProvider
from us_mediakit.providers.claid_ai import ClaidAiProvider
from us_mediakit.providers.codeformer import CodeFormerProvider
from us_mediakit.providers.real_esrgan import RealEsrganProvider
from us_mediakit.providers.resolution import NoProviderConfiguredError
from us_mediakit.providers.seedvr2 import SeedVR2Provider
from us_mediakit.providers.vision_chat import OpenAICompatibleVisionProvider

CONFIG_PATH_ENV_VAR = "USMEDIAKIT_PROVIDERS_CONFIG"


@lru_cache(maxsize=1)
def load_provider_config(path: str | None = None) -> dict[str, Any]:
    config_path = path or os.environ.get(CONFIG_PATH_ENV_VAR)
    if not config_path or not os.path.exists(config_path):
        return {"providers": {}}
    with open(config_path, encoding="utf-8") as f:
        loaded = yaml.safe_load(f)
    return loaded or {"providers": {}}


def get_instance_default(operation: str) -> str | None:
    config = load_provider_config()
    return config.get("providers", {}).get(operation, {}).get("default")


def build_ai_upscale_provider(name: str) -> ImageEnhanceProvider:
    config = load_provider_config()
    registered = config.get("providers", {}).get("ai_upscale", {}).get("registered", {})
    entry = registered.get(name)
    if entry is None:
        raise NoProviderConfiguredError(
            f"ai_upscale-Provider {name!r} ist nicht in providers.ai_upscale.registered konfiguriert."
        )

    if name == "claid-ai":
        api_key = os.environ.get(entry.get("api_key_env", ""), "")
        return ClaidAiProvider(api_key=api_key)
    if name == "codeformer":
        return CodeFormerProvider(endpoint=entry["endpoint"])
    if name.startswith("seedvr2-"):
        return SeedVR2Provider(endpoint=entry["endpoint"], variant=name.removeprefix("seedvr2-"))
    return RealEsrganProvider(endpoint=entry["endpoint"])


def build_caption_provider() -> VisionChatProvider:
    config = load_provider_config()
    caption_config = config.get("providers", {}).get("caption", {})
    base_url = caption_config.get("base_url")
    model = caption_config.get("model")
    if not base_url or not model:
        raise NoProviderConfiguredError(
            "caption-Provider ist nicht konfiguriert (providers.caption.base_url/model fehlen)."
        )
    api_key_env = caption_config.get("api_key_env")
    api_key = os.environ.get(api_key_env) if api_key_env else None
    return OpenAICompatibleVisionProvider(base_url=base_url, model=model, api_key=api_key)
