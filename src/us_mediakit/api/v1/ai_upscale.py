"""KI-Hochskalierung/-Verbesserung über austauschbare Provider.

`restore_faces=True` ruft nach dem eigentlichen Upscaling zusätzlich CodeFormer als
eigenständigen, separat abgerechneten Schritt auf (`face_restore.codeformer` in
`costweights.json`, addiert über `run_metered`s `extra_credits` — siehe dortiger
Kommentar zur vereinfachten Ein-Event-Abrechnung).

**Fallback bei Nichterreichbarkeit** (Programmierplan Abschnitt 7, Phase 5): schlägt der
gewählte Provider mit `ProviderUnavailableError` fehl (z. B. claid.ai down), wird auf ein
einfaches, nicht-KI-gestütztes Resize zurückgefallen, statt die Anfrage scheitern zu
lassen — Antwort trägt dann `ai_upscale_fallback: true`.
"""

from __future__ import annotations

import base64
import io

from fastapi import APIRouter, Depends, HTTPException
from PIL import Image
from sqlalchemy.orm import Session

from us_mediakit.api.deps import get_session, require_api_key
from us_mediakit.api.metering import MeteringContext, run_metered
from us_mediakit.api.schemas import AiUpscaleApiRequest, AiUpscaleApiResponse
from us_mediakit.billing.cost import CostTable
from us_mediakit.billing.idempotency import ResponseCache
from us_mediakit.db.models import ApiKey
from us_mediakit.providers.base import ProviderError, ProviderUnavailableError
from us_mediakit.providers.registry import build_ai_upscale_provider, get_instance_default
from us_mediakit.providers.resolution import NoProviderConfiguredError, resolve_provider

router = APIRouter()

_cost_table = CostTable.load()
_response_cache = ResponseCache()


def _plain_resize_fallback(data: bytes, *, target_width: int | None, target_height: int | None) -> bytes:
    with Image.open(io.BytesIO(data)) as img:
        img.load()
        width = target_width or img.width
        height = target_height or img.height
        resized = img.resize((width, height), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        save_format = img.format or "JPEG"
        resized.save(buffer, format=save_format)
        return buffer.getvalue()


@router.post("/v1/ai_upscale", response_model=AiUpscaleApiResponse)
def post_ai_upscale(
    body: AiUpscaleApiRequest,
    api_key: ApiKey = Depends(require_api_key),
    session: Session = Depends(get_session),
) -> AiUpscaleApiResponse:
    try:
        provider_name = resolve_provider(
            request_provider=body.provider,
            account_default_provider=None,  # kommt vom Kundenbereich, hier nicht verfügbar
            instance_default_provider=get_instance_default("ai_upscale"),
        )
    except NoProviderConfiguredError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None

    operation = f"ai_upscale.{provider_name}"
    if operation not in _cost_table.weights:
        # Ein registrierter Provider ohne Credits-Gewicht ist eine Konfigurationslücke,
        # kein Serverfehler — z. B. weil "codeformer" nur als restore_faces-Zusatzschritt
        # (face_restore.codeformer) bepreist ist, nicht als primärer ai_upscale-Provider.
        raise HTTPException(
            status_code=422,
            detail=f"Kein Credits-Gewicht für {operation!r} in costweights.json konfiguriert.",
        )

    source_bytes = base64.b64decode(body.source)
    ctx = MeteringContext(
        session=session, api_key=api_key, cost_table=_cost_table, response_cache=_response_cache
    )

    # Vorab feststehend, unabhängig vom tatsächlichen Ausgang des Zusatzschritts in
    # work(): wer restore_faces anfragt, wird dafür berechnet — genau wie beim
    # Provider-Fallback unten wird der angefragte Umfang abgerechnet, nicht das
    # tatsächlich erreichte Ergebnis. run_metered berechnet Credits vor der Ausführung,
    # ein von work() erst danach bekanntes Ergebnis könnte das nicht mehr rückwirkend ändern.
    extra_credits = (
        _cost_table.credits_for_operation("face_restore.codeformer")
        if (body.restore_faces and provider_name != "codeformer")
        else 0.0
    )

    def work() -> tuple[bytes, dict]:
        try:
            provider = build_ai_upscale_provider(provider_name)
        except NoProviderConfiguredError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from None

        try:
            enhanced = provider.enhance(
                source_bytes, target_width=body.target_width, target_height=body.target_height
            )
        except ProviderUnavailableError:
            fallback_bytes = _plain_resize_fallback(
                source_bytes, target_width=body.target_width, target_height=body.target_height
            )
            return fallback_bytes, {"provider": provider_name, "ai_upscale_fallback": True}
        except ProviderError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        result_bytes = enhanced.data
        result_provider = enhanced.provider

        if body.restore_faces and provider_name != "codeformer":
            try:
                codeformer = build_ai_upscale_provider("codeformer")
                restored = codeformer.enhance(result_bytes, restore_faces=True)
                result_bytes = restored.data
                result_provider = f"{enhanced.provider}+codeformer"
            except (ProviderUnavailableError, ProviderError, NoProviderConfiguredError):
                # Gesichtsrestauration ist ein Zusatzschritt — schlägt sie fehl, bleibt das
                # (bereits erfolgreiche) Upscaling-Ergebnis bestehen, statt die ganze
                # Operation scheitern zu lassen. Abgerechnet wird trotzdem (siehe
                # extra_credits oben) — der angefragte Umfang, nicht das Ergebnis.
                pass

        return result_bytes, {"provider": result_provider, "ai_upscale_fallback": False}

    result = run_metered(
        ctx,
        request_id=body.request_id,
        operation=f"ai_upscale.{provider_name}",
        dry_run=body.dry_run,
        bytes_in=len(source_bytes),
        work=work,
        extra_credits=extra_credits,
    )

    data_field = None
    if "_result_bytes" in result:
        data_field = base64.b64encode(result.pop("_result_bytes")).decode("ascii")

    return AiUpscaleApiResponse(data=data_field, **result)
