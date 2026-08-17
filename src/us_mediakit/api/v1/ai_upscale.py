"""KI-Hochskalierung/-Verbesserung — Provider-Anbindung folgt in Phase 5."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from us_mediakit.api.deps import require_api_key
from us_mediakit.db.models import ApiKey

router = APIRouter()


@router.post("/v1/ai_upscale")
def post_ai_upscale(api_key: ApiKey = Depends(require_api_key)) -> None:
    raise HTTPException(
        status_code=501,
        detail="ai_upscale ist noch nicht implementiert — folgt in Phase 5 (KI-Provider).",
    )
