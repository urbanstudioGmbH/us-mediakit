from __future__ import annotations

from fastapi import APIRouter

from us_mediakit.api.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    return HealthResponse()
