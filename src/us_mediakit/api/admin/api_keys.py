from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from us_mediakit.api.deps import generate_api_key, get_session, require_admin_token
from us_mediakit.api.schemas import ApiKeyCreateRequest, ApiKeyCreateResponse
from us_mediakit.db.models import ApiKey

router = APIRouter()


@router.post("/admin/api-keys", response_model=ApiKeyCreateResponse, dependencies=[Depends(require_admin_token)])
def create_api_key(
    body: ApiKeyCreateRequest, session: Session = Depends(get_session)
) -> ApiKeyCreateResponse:
    generated = generate_api_key()
    api_key = ApiKey(
        id=generated.key_prefix,
        account_ref=body.account_ref,
        key_prefix=generated.key_prefix,
        key_hash=generated.key_hash,
        label=body.label,
        status="active",
        created_at=datetime.now(timezone.utc),
    )
    session.add(api_key)
    session.commit()

    return ApiKeyCreateResponse(
        id=api_key.id, api_key=generated.raw_key, key_prefix=generated.key_prefix
    )


@router.post("/admin/api-keys/{key_id}/suspend", dependencies=[Depends(require_admin_token)])
def suspend_api_key(key_id: str, session: Session = Depends(get_session)) -> dict:
    api_key = session.get(ApiKey, key_id)
    if api_key is None:
        raise HTTPException(status_code=404, detail="API-Key nicht gefunden")
    api_key.status = "suspended"
    session.commit()
    return {"id": key_id, "status": "suspended"}


@router.post("/admin/api-keys/{key_id}/reactivate", dependencies=[Depends(require_admin_token)])
def reactivate_api_key(key_id: str, session: Session = Depends(get_session)) -> dict:
    api_key = session.get(ApiKey, key_id)
    if api_key is None:
        raise HTTPException(status_code=404, detail="API-Key nicht gefunden")
    api_key.status = "active"
    session.commit()
    return {"id": key_id, "status": "active"}


@router.delete("/admin/api-keys/{key_id}", dependencies=[Depends(require_admin_token)])
def revoke_api_key(key_id: str, session: Session = Depends(get_session)) -> dict:
    """Endgültiger Widerruf — löscht den Schlüssel-Datensatz. `usage_events` bleiben
    unabhängig davon erhalten (denormalisiertes `account_ref`, siehe Datenmodell)."""
    api_key = session.get(ApiKey, key_id)
    if api_key is None:
        raise HTTPException(status_code=404, detail="API-Key nicht gefunden")
    session.delete(api_key)
    session.commit()
    return {"id": key_id, "status": "revoked"}
