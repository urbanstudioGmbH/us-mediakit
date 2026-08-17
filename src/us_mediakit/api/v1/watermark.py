"""Sichtbares/unsichtbares Wasserzeichen + Erkennung — folgt in Phase 6."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from us_mediakit.api.deps import require_api_key
from us_mediakit.db.models import ApiKey

router = APIRouter()


@router.post("/v1/watermark")
def post_watermark(api_key: ApiKey = Depends(require_api_key)) -> None:
    raise HTTPException(
        status_code=501, detail="watermark ist noch nicht implementiert — folgt in Phase 6."
    )


@router.post("/v1/watermark/detect")
def post_watermark_detect(api_key: ApiKey = Depends(require_api_key)) -> None:
    raise HTTPException(
        status_code=501, detail="watermark/detect ist noch nicht implementiert — folgt in Phase 6."
    )
