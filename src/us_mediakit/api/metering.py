"""Gemeinsame Abwicklung für jeden abrechenbaren Endpunkt: Idempotenz, `dry_run`,
Credits-Berechnung, Usage-Logging — an einer Stelle statt in jedem Endpunkt neu.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException
from sqlalchemy.orm import Session

from us_mediakit.billing.cost import CostTable
from us_mediakit.billing.idempotency import ResponseCache, is_duplicate_request
from us_mediakit.db.models import ApiKey, UsageEvent


@dataclass
class MeteringContext:
    session: Session
    api_key: ApiKey
    cost_table: CostTable
    response_cache: ResponseCache


def run_metered(
    ctx: MeteringContext,
    *,
    request_id: str,
    operation: str,
    dry_run: bool,
    bytes_in: int,
    work: Callable[[], tuple[bytes, dict[str, Any]]],
    provider: str | None = None,
    external_cost_micros: int | None = None,
    extra_credits: float = 0.0,
) -> dict[str, Any]:
    """Führt `work()` genau dann aus, wenn nötig, und liefert das fertige Response-Dict
    (ohne `data`-Feld base64-kodiert einzusetzen — das übernimmt der Aufrufer, da nur er
    weiß, welches Feld die Ergebnis-Bytes im jeweiligen Response-Schema trägt).

    `extra_credits` addiert ein zusätzliches, bereits nachgeschlagenes Gewicht (z. B.
    `face_restore.codeformer` neben `ai_upscale.<provider>`, wenn `restore_faces`
    einen zweiten Provider-Aufruf auslöst) — vereinfachte Abrechnung als ein
    kombinierter `UsageEvent` statt zwei getrennter, um das Ein-Event-pro-Aufruf-Modell
    hier nicht aufzubrechen."""
    if external_cost_micros is not None:
        credits = ctx.cost_table.credits_for_external_cost(external_cost_micros)
    else:
        credits = ctx.cost_table.credits_for_operation(operation)
    credits += extra_credits

    if dry_run:
        return {
            "request_id": request_id,
            "dry_run": True,
            "estimated_credits": credits,
            "confidence": "exact",
        }

    cached = ctx.response_cache.get(request_id)
    if cached is not None:
        # Kopie zurückgeben: Aufrufer poppen üblicherweise "_result_bytes" heraus, um es
        # ins jeweilige Response-Feld zu kodieren — ohne Kopie würde das den im Cache
        # abgelegten Eintrag beim ersten Abruf zerstören, und ein zweiter (Retry-)Abruf
        # bekäme kein "data"-Feld mehr.
        return dict(cached)

    if is_duplicate_request(ctx.session, request_id):
        raise HTTPException(
            status_code=409,
            detail=(
                "request_id wurde bereits verarbeitet, die Antwort liegt aber nicht mehr "
                "im Kurzzeit-Cache (Retry-Fenster abgelaufen) — erneuter Aufruf mit "
                "demselben request_id kann nicht mehr identisch beantwortet werden."
            ),
        )

    start = time.monotonic()
    result_bytes, extra_fields = work()
    duration_ms = int((time.monotonic() - start) * 1000)

    ctx.session.add(
        UsageEvent(
            request_id=request_id,
            api_key_id=ctx.api_key.id,
            account_ref=ctx.api_key.account_ref,
            operation=operation,
            provider=provider,
            status="ok",
            occurred_at=datetime.now(timezone.utc),
            bytes_in=bytes_in,
            bytes_out=len(result_bytes),
            credits=credits,
            credits_table_version=ctx.cost_table.version,
            external_cost_micros=external_cost_micros,
            duration_ms=duration_ms,
        )
    )
    ctx.session.commit()

    response = {
        "request_id": request_id,
        "credits_charged": credits,
        "dry_run": False,
        "_result_bytes": result_bytes,
        **extra_fields,
    }
    # Kopie in den Cache, nicht dasselbe Objekt: der Aufrufer poppt "_result_bytes" aus
    # dem zurückgegebenen Dict heraus, um es zu kodieren — ohne Kopie würde das den
    # gecachten Eintrag mit zerstören (siehe Kommentar beim Cache-Hit oben).
    ctx.response_cache.set(request_id, dict(response))
    return response
