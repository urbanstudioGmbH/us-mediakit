"""KI-Bildbeschreibung — Provider-Anbindung folgt in Phase 5.

Die Route existiert bereits (siehe Programmierplan Abschnitt 5, API-Tabelle), damit
Auth/Routing-Struktur stehen, bevor die eigentliche Provider-Logik dazukommt.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from us_mediakit.api.deps import require_api_key
from us_mediakit.db.models import ApiKey

router = APIRouter()


@router.post("/v1/caption")
def post_caption(api_key: ApiKey = Depends(require_api_key)) -> None:
    raise HTTPException(
        status_code=501,
        detail="caption ist noch nicht implementiert — folgt in Phase 5 (KI-Provider).",
    )
