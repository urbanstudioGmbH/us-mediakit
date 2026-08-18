from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from us_mediakit import config
from us_mediakit.api.deps import get_session, require_api_key, try_load_configured_signer_config
from us_mediakit.api.limits import video_pdf_limiter as _video_pdf_limiter
from us_mediakit.api.metering import MeteringContext, run_metered
from us_mediakit.api.schemas import ThumbnailApiRequest, ThumbnailApiResponse
from us_mediakit.billing.cost import CostTable
from us_mediakit.billing.idempotency import ResponseCache
from us_mediakit.billing.rate_limit import ConcurrencyLimitExceeded
from us_mediakit.core.pipeline import ThumbnailRequest, generate_thumbnail
from us_mediakit.db.models import ApiKey
from us_mediakit.media.video import DEFAULT_SEEK_SECONDS

router = APIRouter()

_cost_table = CostTable.load()
_response_cache = ResponseCache()


@router.post("/v1/thumbnail", response_model=ThumbnailApiResponse)
def post_thumbnail(
    body: ThumbnailApiRequest,
    api_key: ApiKey = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> ThumbnailApiResponse:
    if body.mode is not None:
        presets = config.load_imageformats()
        if body.mode not in presets:
            raise HTTPException(status_code=422, detail=f"Unbekanntes Preset {body.mode!r}")
        thumbnail_mode = presets[body.mode]
    elif body.width and body.height:
        # Presets sind optional: ohne mode reichen Zielmaße direkt aus, ohne dafür vorher
        # einen benannten Eintrag in imageformats.json anlegen zu müssen.
        thumbnail_mode = {"w": body.width, "h": body.height, "fit": body.fit}
    else:
        raise HTTPException(status_code=422, detail="Entweder mode oder width zusammen mit height angeben.")

    source_bytes = base64.b64decode(body.source)
    ctx = MeteringContext(
        session=session, api_key=api_key, cost_table=_cost_table, response_cache=_response_cache
    )

    def work() -> tuple[bytes, dict]:
        request = ThumbnailRequest(
            source=source_bytes,
            mode=thumbnail_mode,
            output_format=body.output_format,
            crop=body.crop,
            aspect_ratio=body.aspect_ratio,
            alignx=body.alignx,
            aligny=body.aligny,
            zoom=body.zoom,
            max_upscale_factor=body.max_upscale_factor,
            is_video=body.is_video,
            video_seek_seconds=(
                body.video_seek_seconds if body.video_seek_seconds is not None else DEFAULT_SEEK_SECONDS
            ),
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
        try:
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
        except ValueError as exc:
            # Deckt u. a. UnsupportedOutputFormatError, SecurityLimitExceeded,
            # SvgSanitizeError und einen unbekannten Fit-Modus ab — alles
            # Eingabefehler des Aufrufers, kein Serverfehler.
            raise HTTPException(status_code=422, detail=str(exc)) from exc

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
