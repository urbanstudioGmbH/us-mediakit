"""uvicorn-Einstiegspunkt: `uvicorn us_mediakit.server:app`.

Socket-Aktivierung (`--fd 3`, siehe `deploy/us-mediakit.socket`/`.service`) ist eine
uvicorn-CLI-Option, kein Code hier — dieses Modul stellt nur `app` bereit.
"""

from __future__ import annotations

from us_mediakit.api.app import app

__all__ = ["app"]
