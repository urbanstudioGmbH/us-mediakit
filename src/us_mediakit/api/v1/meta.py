from __future__ import annotations

import base64
import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from us_mediakit.api.deps import get_session, require_api_key
from us_mediakit.api.metering import MeteringContext, run_metered
from us_mediakit.api.schemas import (
    MetaReadApiRequest,
    MetaReadApiResponse,
    MetaWriteApiRequest,
    MetaWriteApiResponse,
)
from us_mediakit.billing.cost import CostTable
from us_mediakit.billing.idempotency import ResponseCache
from us_mediakit.db.models import ApiKey
from us_mediakit.metadata.gps import strip_gps as strip_gps_tags
from us_mediakit.metadata.read import read_metadata
from us_mediakit.metadata.write import write_tags

router = APIRouter()

_cost_table = CostTable.load()
_read_response_cache = ResponseCache()
_write_response_cache = ResponseCache()


@router.post("/v1/meta/read", response_model=MetaReadApiResponse)
def post_meta_read(
    body: MetaReadApiRequest,
    api_key: ApiKey = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> MetaReadApiResponse:
    source_bytes = base64.b64decode(body.source)
    ctx = MeteringContext(
        session=session, api_key=api_key, cost_table=_cost_table, response_cache=_read_response_cache
    )

    def work() -> tuple[bytes, dict]:
        tags = read_metadata(source_bytes)
        # bytes_out spiegelt die tatsächliche Antwortgröße (Tags als JSON), nicht die
        # unveränderte Quellbildgröße — für eine Lese-Operation aussagekräftiger.
        return json.dumps(tags, default=str).encode("utf-8"), {"tags": tags}

    result = run_metered(
        ctx,
        request_id=body.request_id,
        operation="meta.read",
        dry_run=body.dry_run,
        bytes_in=len(source_bytes),
        work=work,
    )
    result.pop("_result_bytes", None)
    return MetaReadApiResponse(**result)


@router.post("/v1/meta/write", response_model=MetaWriteApiResponse)
def post_meta_write(
    body: MetaWriteApiRequest,
    api_key: ApiKey = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> MetaWriteApiResponse:
    source_bytes = base64.b64decode(body.source)
    ctx = MeteringContext(
        session=session, api_key=api_key, cost_table=_cost_table, response_cache=_write_response_cache
    )

    def work() -> tuple[bytes, dict]:
        result_bytes = write_tags(source_bytes, body.tags) if body.tags else source_bytes
        if body.strip_gps:
            result_bytes = strip_gps_tags(result_bytes)
        return result_bytes, {}

    result = run_metered(
        ctx,
        request_id=body.request_id,
        operation="meta.write",
        dry_run=body.dry_run,
        bytes_in=len(source_bytes),
        work=work,
    )

    data_field = None
    if "_result_bytes" in result:
        data_field = base64.b64encode(result.pop("_result_bytes")).decode("ascii")

    return MetaWriteApiResponse(data=data_field, **result)
