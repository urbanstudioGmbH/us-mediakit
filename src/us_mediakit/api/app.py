"""FastAPI-App-Factory. `create_app()` statt eines Modul-globalen `app`, damit Tests
eigene Datenbank-/Konfigurationszustände isolieren können."""

from __future__ import annotations

from fastapi import FastAPI

from us_mediakit.api.admin import api_keys as admin_api_keys
from us_mediakit.api.admin import usage as admin_usage
from us_mediakit.api.v1 import ai_upscale, c2pa, caption, health, meta, thumbnail, watermark


def create_app() -> FastAPI:
    app = FastAPI(title="us-mediakit", description="Bild-Metadaten, C2PA und KI-Bildverarbeitung")

    app.include_router(thumbnail.router)
    app.include_router(meta.router)
    app.include_router(c2pa.router)
    app.include_router(caption.router)
    app.include_router(ai_upscale.router)
    app.include_router(watermark.router)
    app.include_router(health.router)
    app.include_router(admin_api_keys.router)
    app.include_router(admin_usage.router)

    return app


app = create_app()
