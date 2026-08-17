"""Aggregierte Nutzung (für die Anzeige im Kundenbereich) und cursor-basierter Export
(für den Guthaben-Abzug im Kundenbereich — Poll-Intervall mit dem Kundenbereich
abstimmen, Empfehlung 1–2 Minuten)."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from us_mediakit.api.deps import get_session, require_admin_token
from us_mediakit.api.schemas import UsageEventOut, UsageExportResponse
from us_mediakit.db.models import UsageEvent

router = APIRouter()


def compute_account_usage(
    session: Session,
    account_ref: str,
    *,
    from_: datetime | None = None,
    to: datetime | None = None,
) -> dict:
    """Wiederverwendet von der Admin-API und `us-mediakit admin usage`, damit beide
    Aufrufwege exakt dieselbe Aggregation liefern."""
    stmt = select(
        UsageEvent.operation,
        func.count(UsageEvent.id).label("count"),
        func.sum(UsageEvent.credits).label("credits"),
        func.sum(UsageEvent.bytes_in).label("bytes_in"),
        func.sum(UsageEvent.bytes_out).label("bytes_out"),
    ).where(UsageEvent.account_ref == account_ref)

    if from_ is not None:
        stmt = stmt.where(UsageEvent.occurred_at >= from_)
    if to is not None:
        stmt = stmt.where(UsageEvent.occurred_at <= to)

    stmt = stmt.group_by(UsageEvent.operation)
    rows = session.execute(stmt).all()

    by_operation = {
        row.operation: {
            "count": row.count,
            "credits": row.credits or 0.0,
            "bytes_in": row.bytes_in or 0,
            "bytes_out": row.bytes_out or 0,
        }
        for row in rows
    }
    return {
        "account_ref": account_ref,
        "total_credits": sum(v["credits"] for v in by_operation.values()),
        "by_operation": by_operation,
    }


@router.get("/admin/accounts/{account_ref}/usage", dependencies=[Depends(require_admin_token)])
def get_account_usage(
    account_ref: str,
    from_: datetime | None = Query(default=None, alias="from"),
    to: datetime | None = Query(default=None),
    session: Session = Depends(get_session),
) -> dict:
    return compute_account_usage(session, account_ref, from_=from_, to=to)


@router.get(
    "/admin/usage/export",
    response_model=UsageExportResponse,
    dependencies=[Depends(require_admin_token)],
)
def export_usage(
    since_id: int = Query(default=0),
    limit: int = Query(default=500, le=5000),
    session: Session = Depends(get_session),
) -> UsageExportResponse:
    """Liefert `UsageEvent`-Zeilen mit `id > since_id`, aufsteigend sortiert. Wiederholtes
    Abfragen mit dem zurückgegebenen `next_since_id` liefert weder Duplikate noch Lücken,
    solange derselbe Cursor konsequent weitergereicht wird (append-only, `id` monoton)."""
    stmt = (
        select(UsageEvent)
        .where(UsageEvent.id > since_id)
        .order_by(UsageEvent.id.asc())
        .limit(limit)
    )
    rows = list(session.execute(stmt).scalars())

    events = [
        UsageEventOut(
            id=row.id,
            request_id=row.request_id,
            operation=row.operation,
            provider=row.provider,
            status=row.status,
            occurred_at=row.occurred_at.isoformat(),
            bytes_in=row.bytes_in,
            bytes_out=row.bytes_out,
            credits=row.credits,
            credits_table_version=row.credits_table_version,
            external_cost_micros=row.external_cost_micros,
            duration_ms=row.duration_ms,
        )
        for row in rows
    ]
    next_since_id = rows[-1].id if rows else since_id
    return UsageExportResponse(events=events, next_since_id=next_since_id if rows else None)
