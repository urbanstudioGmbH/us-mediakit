"""Animierter WebP-Ausschnitt aus einem Video — eigene Operation, siehe
`us_mediakit.media.animated_webp` für die Begründung der Trennung von `thumbnail`."""

from __future__ import annotations

import base64
import io

from fastapi import APIRouter, Depends, HTTPException
from PIL import Image
from sqlalchemy.orm import Session

from us_mediakit.api.deps import get_session, require_api_key
from us_mediakit.api.limits import video_pdf_limiter
from us_mediakit.api.metering import MeteringContext, run_metered
from us_mediakit.api.schemas import AnimatedWebpApiRequest, AnimatedWebpApiResponse
from us_mediakit.billing.cost import CostTable
from us_mediakit.billing.idempotency import ResponseCache
from us_mediakit.billing.rate_limit import ConcurrencyLimitExceeded
from us_mediakit.db.models import ApiKey
from us_mediakit.media.animated_webp import extract_animated_webp

router = APIRouter()

_cost_table = CostTable.load()
_response_cache = ResponseCache()


@router.post("/v1/animated_webp", response_model=AnimatedWebpApiResponse)
def post_animated_webp(
    body: AnimatedWebpApiRequest,
    api_key: ApiKey = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> AnimatedWebpApiResponse:
    source_bytes = base64.b64decode(body.source)
    ctx = MeteringContext(
        session=session, api_key=api_key, cost_table=_cost_table, response_cache=_response_cache
    )

    def work() -> tuple[bytes, dict]:
        try:
            with video_pdf_limiter:
                result_bytes = extract_animated_webp(
                    source_bytes,
                    start_seconds=body.start_seconds,
                    duration_seconds=body.duration_seconds,
                    width=body.width,
                    fps=body.fps,
                    quality=body.quality,
                )
        except ConcurrencyLimitExceeded:
            raise HTTPException(
                status_code=429,
                detail="Zu viele gleichzeitige Video-/PDF-Jobs, bitte später erneut versuchen.",
            ) from None
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        with Image.open(io.BytesIO(result_bytes)) as img:
            frame_count = getattr(img, "n_frames", 1)
            width, height = img.size

        return result_bytes, {
            "frame_count": frame_count,
            "target_width": width,
            "target_height": height,
        }

    result = run_metered(
        ctx,
        request_id=body.request_id,
        operation="animated_webp",
        dry_run=body.dry_run,
        bytes_in=len(source_bytes),
        work=work,
    )

    data_field = None
    if "_result_bytes" in result:
        data_field = base64.b64encode(result.pop("_result_bytes")).decode("ascii")

    return AnimatedWebpApiResponse(data=data_field, **result)
