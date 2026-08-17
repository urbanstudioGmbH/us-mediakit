"""KI-Bildbeschreibung — generischer OpenAI-kompatibler Vision-Chat-Provider.

`only_if_empty` (Default an): bevor überhaupt ein Modell aufgerufen wird, werden die
Ziel-Metadatenfelder gelesen. Sind sie bereits belegt, wird die Operation ganz
ausgelassen — "skipped_existing ohne Kosten" laut Programmierplan Abschnitt 7 heißt hier
wörtlich: kein `usage_events`-Eintrag, keine Abrechnung, nicht nur 0 Credits bei
trotzdem durchgeführter Operation.
"""

from __future__ import annotations

import base64

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from us_mediakit.api.deps import get_session, require_api_key
from us_mediakit.api.metering import MeteringContext, run_metered
from us_mediakit.api.schemas import CaptionApiRequest, CaptionApiResponse
from us_mediakit.billing.cost import CostTable
from us_mediakit.billing.idempotency import ResponseCache
from us_mediakit.db.models import ApiKey
from us_mediakit.metadata.read import read_metadata
from us_mediakit.metadata.write import write_tags
from us_mediakit.providers.base import ProviderError, ProviderUnavailableError, VisionChatProvider
from us_mediakit.providers.registry import build_caption_provider
from us_mediakit.providers.vision_chat import OpenAICompatibleVisionProvider

router = APIRouter()

_cost_table = CostTable.load()
_response_cache = ResponseCache()


@router.post("/v1/caption", response_model=CaptionApiResponse)
def post_caption(
    body: CaptionApiRequest,
    api_key: ApiKey = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> CaptionApiResponse:
    source_bytes = base64.b64decode(body.source)

    if body.only_if_empty:
        existing_tags = read_metadata(source_bytes)
        if all(existing_tags.get(field) for field in body.write_to):
            return CaptionApiResponse(
                request_id=body.request_id,
                credits_charged=0,
                skipped_existing=True,
                data=base64.b64encode(source_bytes).decode("ascii"),
            )

    byok_override = bool(body.provider_url and body.provider_model)
    provider: VisionChatProvider
    if body.provider_url and body.provider_model:
        provider = OpenAICompatibleVisionProvider(
            base_url=body.provider_url, model=body.provider_model, api_key=body.provider_key
        )
    else:
        try:
            provider = build_caption_provider()
        except Exception as exc:  # noqa: BLE001 — in HTTPException 503 übersetzt
            raise HTTPException(status_code=503, detail=str(exc)) from None

    ctx = MeteringContext(
        session=session, api_key=api_key, cost_table=_cost_table, response_cache=_response_cache
    )
    operation = "caption.byok" if byok_override else "caption.instance-default"

    def work() -> tuple[bytes, dict]:
        try:
            caption_text = provider.caption(source_bytes)
        except ProviderUnavailableError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except ProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        tags = {field: caption_text for field in body.write_to}
        if body.mirror_exif:
            tags["EXIF:ImageDescription"] = caption_text
        result_bytes = write_tags(source_bytes, tags)
        return result_bytes, {"caption": caption_text}

    result = run_metered(
        ctx,
        request_id=body.request_id,
        operation=operation,
        dry_run=body.dry_run,
        bytes_in=len(source_bytes),
        provider=provider.name,
        work=work,
    )

    data_field = None
    if "_result_bytes" in result:
        data_field = base64.b64encode(result.pop("_result_bytes")).decode("ascii")

    return CaptionApiResponse(data=data_field, **result)
