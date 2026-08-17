from __future__ import annotations

import base64
import os

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from us_mediakit import config
from us_mediakit.api.deps import get_session, require_api_key, try_load_configured_signer_config
from us_mediakit.api.metering import MeteringContext, run_metered
from us_mediakit.api.schemas import ThumbnailApiRequest, ThumbnailApiResponse
from us_mediakit.billing.cost import CostTable
from us_mediakit.billing.idempotency import ResponseCache
from us_mediakit.billing.rate_limit import ConcurrencyLimiter, ConcurrencyLimitExceeded
from us_mediakit.core.pipeline import ThumbnailRequest, generate_thumbnail
from us_mediakit.db.models import ApiKey

router = APIRouter()

_cost_table = CostTable.load()
_response_cache = ResponseCache()

# Tarifunabhängige Zusatzschwelle für gleichzeitige Video-/PDF-Jobs — unabhängig vom
# Credits/Minute-Limit pro Plan-Tier, das die Kundenbereich-Zuordnung Account→Limit
# voraussetzt (siehe billing/rate_limit.py).
_video_pdf_limiter = ConcurrencyLimiter(
    max_concurrent=int(os.environ.get("USMEDIAKIT_MAX_CONCURRENT_VIDEO_PDF_JOBS", "4"))
)


@router.post("/v1/thumbnail", response_model=ThumbnailApiResponse)
def post_thumbnail(
    body: ThumbnailApiRequest,
    api_key: ApiKey = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> ThumbnailApiResponse:
    presets = config.load_imageformats()
    if body.mode not in presets:
        raise HTTPException(status_code=422, detail=f"Unbekanntes Preset {body.mode!r}")

    source_bytes = base64.b64decode(body.source)
    ctx = MeteringContext(
        session=session, api_key=api_key, cost_table=_cost_table, response_cache=_response_cache
    )

    def work() -> tuple[bytes, dict]:
        request = ThumbnailRequest(
            source=source_bytes,
            mode=presets[body.mode],
            output_format=body.output_format,
            crop=body.crop,
            aspect_ratio=body.aspect_ratio,
            zoom=body.zoom,
            is_video=body.is_video,
            is_pdf=body.is_pdf,
            pdf_page=body.pdf_page,
            carry_metadata=body.carry_metadata,
            strip_gps=body.strip_gps,
            carry_c2pa=body.carry_c2pa,
            c2pa_signer_config=try_load_configured_signer_config(),
            c2pa_digital_source_type=body.c2pa.digital_source_type if body.c2pa else None,
            c2pa_actions=body.c2pa.actions if body.c2pa else [],
            c2pa_assertions=body.c2pa.assertions if body.c2pa else [],
        )
        result = generate_thumbnail(request)
        return result.data, {
            "content_type": result.content_type,
            "target_width": result.target_width,
            "target_height": result.target_height,
        }

    def metered_work() -> tuple[bytes, dict]:
        if not (body.is_video or body.is_pdf):
            return work()
        try:
            with _video_pdf_limiter:
                return work()
        except ConcurrencyLimitExceeded:
            raise HTTPException(
                status_code=429,
                detail="Zu viele gleichzeitige Video-/PDF-Jobs, bitte später erneut versuchen.",
            ) from None

    result = run_metered(
        ctx,
        request_id=body.request_id,
        operation="thumbnail",
        dry_run=body.dry_run,
        bytes_in=len(source_bytes),
        work=metered_work,
    )

    data_field = None
    if "_result_bytes" in result:
        data_field = base64.b64encode(result.pop("_result_bytes")).decode("ascii")

    return ThumbnailApiResponse(data=data_field, **result)
