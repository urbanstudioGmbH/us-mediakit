"""Sichtbares/unsichtbares Wasserzeichen + Erkennung — drei getrennte Operationen
(siehe Programmierplan Phase 6), nicht Varianten eines Features.

**Referenz-ID-Verwaltung, bewusst einfach gehalten:** Für das unsichtbare Wasserzeichen
gibt entweder der Aufrufer eine `reference_id` mit, oder der Dienst erzeugt eine
zufällige. In beiden Fällen liegt die Zuordnung "Referenz-ID → welches Asset/Konto"
**beim Aufrufer** — us-mediakit legt dafür keine eigene Tabelle an (analog zur
Account-Default-Provider-Auflösung in Phase 5: das gehört zum aufrufenden System, nicht
in dieses Datenmodell). `POST /v1/watermark/detect` liefert die gefundene Referenz-ID
zurück, der Abgleich "stammt das von Konto X" ist Sache des Aufrufers.
"""

from __future__ import annotations

import base64
import secrets

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from us_mediakit.api.deps import get_session, require_api_key
from us_mediakit.api.metering import MeteringContext, run_metered
from us_mediakit.api.schemas import (
    WatermarkApiRequest,
    WatermarkApiResponse,
    WatermarkDetectApiRequest,
    WatermarkDetectApiResponse,
)
from us_mediakit.billing.cost import CostTable
from us_mediakit.billing.idempotency import ResponseCache
from us_mediakit.db.models import ApiKey
from us_mediakit.watermark import detect as detect_module
from us_mediakit.watermark import invisible as invisible_module
from us_mediakit.watermark import visible as visible_module

router = APIRouter()

_cost_table = CostTable.load()
_watermark_response_cache = ResponseCache()
_detect_response_cache = ResponseCache()


@router.post("/v1/watermark", response_model=WatermarkApiResponse)
def post_watermark(
    body: WatermarkApiRequest,
    api_key: ApiKey = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> WatermarkApiResponse:
    if body.mode not in ("visible", "invisible"):
        raise HTTPException(status_code=422, detail='mode muss "visible" oder "invisible" sein.')

    source_bytes = base64.b64decode(body.source)
    ctx = MeteringContext(
        session=session, api_key=api_key, cost_table=_cost_table, response_cache=_watermark_response_cache
    )

    if body.mode == "visible":
        return _handle_visible(body, source_bytes, ctx)
    return _handle_invisible(body, source_bytes, ctx)


def _handle_visible(body: WatermarkApiRequest, source_bytes: bytes, ctx: MeteringContext) -> WatermarkApiResponse:
    if not body.logo and not body.text:
        raise HTTPException(status_code=422, detail="Für mode=visible wird logo oder text benötigt.")

    def work() -> tuple[bytes, dict]:
        try:
            if body.logo:
                result_bytes = visible_module.apply_logo(
                    source_bytes,
                    base64.b64decode(body.logo),
                    position=body.position,
                    opacity=body.opacity,
                    output_format=body.output_format,
                )
            elif body.text:
                result_bytes = visible_module.apply_text(
                    source_bytes,
                    body.text,
                    position=body.position,
                    opacity=body.opacity,
                    output_format=body.output_format,
                )
            else:
                raise HTTPException(
                    status_code=422, detail="Für mode=visible wird logo oder text benötigt."
                )
        except visible_module.VisibleWatermarkError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return result_bytes, {}

    result = run_metered(
        ctx,
        request_id=body.request_id,
        operation="watermark_visible",
        dry_run=body.dry_run,
        bytes_in=len(source_bytes),
        work=work,
    )
    return _finish(result, WatermarkApiResponse)


def _handle_invisible(body: WatermarkApiRequest, source_bytes: bytes, ctx: MeteringContext) -> WatermarkApiResponse:
    if body.reference_id is not None:
        try:
            reference_id = bytes.fromhex(body.reference_id)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=f"reference_id ist kein gültiges Hex: {exc}") from None
        if len(reference_id) != invisible_module.REFERENCE_ID_LENGTH_BYTES:
            raise HTTPException(
                status_code=422,
                detail=f"reference_id muss {invisible_module.REFERENCE_ID_LENGTH_BYTES} Byte lang sein.",
            )
    else:
        reference_id = secrets.token_bytes(invisible_module.REFERENCE_ID_LENGTH_BYTES)

    def work() -> tuple[bytes, dict]:
        try:
            result_bytes = invisible_module.embed(
                source_bytes, reference_id, output_format=body.output_format
            )
        except invisible_module.WatermarkError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        return result_bytes, {"reference_id": reference_id.hex()}

    result = run_metered(
        ctx,
        request_id=body.request_id,
        operation="watermark_invisible",
        dry_run=body.dry_run,
        bytes_in=len(source_bytes),
        work=work,
    )
    return _finish(result, WatermarkApiResponse)


def _finish(result: dict, response_cls: type) -> WatermarkApiResponse:
    data_field = None
    if "_result_bytes" in result:
        data_field = base64.b64encode(result.pop("_result_bytes")).decode("ascii")
    return response_cls(data=data_field, **result)


@router.post("/v1/watermark/detect", response_model=WatermarkDetectApiResponse)
def post_watermark_detect(
    body: WatermarkDetectApiRequest,
    api_key: ApiKey = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> WatermarkDetectApiResponse:
    source_bytes = base64.b64decode(body.source)
    ctx = MeteringContext(
        session=session, api_key=api_key, cost_table=_cost_table, response_cache=_detect_response_cache
    )

    def work() -> tuple[bytes, dict]:
        result = detect_module.detect(source_bytes)
        payload = {
            "detected": result.detected,
            "reference_id": result.reference_id.hex() if result.reference_id else None,
        }
        return source_bytes, payload

    result = run_metered(
        ctx,
        request_id=body.request_id,
        operation="watermark_detect",
        dry_run=body.dry_run,
        bytes_in=len(source_bytes),
        work=work,
    )
    result.pop("_result_bytes", None)
    return WatermarkDetectApiResponse(**result)
