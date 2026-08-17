from __future__ import annotations

import base64
import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from us_mediakit.api.deps import get_session, load_configured_signer_config, require_api_key
from us_mediakit.api.metering import MeteringContext, run_metered
from us_mediakit.api.schemas import (
    C2paSignApiRequest,
    C2paSignApiResponse,
    C2paVerifyApiRequest,
    C2paVerifyApiResponse,
)
from us_mediakit.billing.cost import CostTable
from us_mediakit.billing.idempotency import ResponseCache
from us_mediakit.c2pa.sign import SignerConfig, SignRequest
from us_mediakit.c2pa.sign import sign as c2pa_sign
from us_mediakit.c2pa.verify import verify as c2pa_verify
from us_mediakit.db.models import ApiKey

router = APIRouter()

_cost_table = CostTable.load()
_verify_response_cache = ResponseCache()
_sign_response_cache = ResponseCache()


@router.post("/v1/c2pa/verify", response_model=C2paVerifyApiResponse)
def post_c2pa_verify(
    body: C2paVerifyApiRequest,
    api_key: ApiKey = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> C2paVerifyApiResponse:
    source_bytes = base64.b64decode(body.source)
    ctx = MeteringContext(
        session=session, api_key=api_key, cost_table=_cost_table, response_cache=_verify_response_cache
    )

    def work() -> tuple[bytes, dict]:
        result = c2pa_verify(source_bytes, body.mime_type)
        payload = {
            "has_manifest": result.has_manifest,
            "validation_state": result.validation_state,
            "validation_results": result.validation_results,
        }
        return json.dumps(payload, default=str).encode("utf-8"), payload

    result = run_metered(
        ctx,
        request_id=body.request_id,
        operation="c2pa.verify",
        dry_run=body.dry_run,
        bytes_in=len(source_bytes),
        work=work,
    )
    result.pop("_result_bytes", None)
    return C2paVerifyApiResponse(**result)


@router.post("/v1/c2pa/sign", response_model=C2paSignApiResponse)
def post_c2pa_sign(
    body: C2paSignApiRequest,
    signer_config: SignerConfig = Depends(load_configured_signer_config),
    api_key: ApiKey = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> C2paSignApiResponse:
    source_bytes = base64.b64decode(body.source)
    ctx = MeteringContext(
        session=session, api_key=api_key, cost_table=_cost_table, response_cache=_sign_response_cache
    )

    def work() -> tuple[bytes, dict]:
        signed = c2pa_sign(
            SignRequest(
                data=source_bytes,
                mime_type=body.mime_type,
                signer_config=signer_config,
                digital_source_type=body.digital_source_type,
                extra_actions=body.actions,
                extra_assertions=body.assertions,
            )
        )
        return signed, {}

    result = run_metered(
        ctx,
        request_id=body.request_id,
        operation="c2pa.sign",
        dry_run=body.dry_run,
        bytes_in=len(source_bytes),
        work=work,
    )

    data_field = None
    if "_result_bytes" in result:
        data_field = base64.b64encode(result.pop("_result_bytes")).decode("ascii")

    return C2paSignApiResponse(data=data_field, **result)
