"""Auth-Dependencies: API-Key (Kunden-Endpunkte) und Admin-Token (Verwaltung), getrennt.

API-Keys haben die Form `usmk_<32 Hex-Zeichen>`. Gespeichert wird nie der Klartext,
sondern `key_prefix` (die ersten 12 Zeichen, für Anzeige/Log-Zuordnung ohne den
vollständigen Key offenzulegen) und `key_hash` (SHA-256 über den vollständigen Key).
"""

from __future__ import annotations

import hashlib
import os
import secrets
from collections.abc import Generator
from dataclasses import dataclass
from datetime import datetime, timezone

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from us_mediakit.db.engine import create_db_engine, create_session_factory
from us_mediakit.db.models import ApiKey

# `auto_error=False`: wir werfen die 401 selbst mit eigener deutscher Fehlermeldung,
# statt FastAPIs generische englische Standardmeldung zu übernehmen. Zentraler Nutzen
# dieses Security-Schemas gegenüber einem rohen Header()-Parameter: FastAPI trägt es als
# echtes `securitySchemes`-Objekt ins OpenAPI-Schema ein, wodurch Swagger UI erst den
# globalen "Authorize"-Button anzeigt (ohne das gibt es dort keinen Login-Dialog, der
# Authorization-Header wäre nur ein verstecktes Parameterfeld pro Endpunkt gewesen).
_bearer_scheme = HTTPBearer(auto_error=False)

_KEY_PREFIX = "usmk_"
_KEY_RANDOM_HEX_LENGTH = 32
_DISPLAY_PREFIX_LENGTH = 12


def hash_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


@dataclass
class GeneratedApiKey:
    raw_key: str  # nur bei Erzeugung sichtbar, wird nirgendwo gespeichert
    key_prefix: str
    key_hash: str


def generate_api_key() -> GeneratedApiKey:
    raw_key = _KEY_PREFIX + secrets.token_hex(_KEY_RANDOM_HEX_LENGTH // 2)
    return GeneratedApiKey(
        raw_key=raw_key,
        key_prefix=raw_key[:_DISPLAY_PREFIX_LENGTH],
        key_hash=hash_key(raw_key),
    )


_engine = None
_session_factory = None


def _get_session_factory():
    global _engine, _session_factory
    if _session_factory is None:
        _engine = create_db_engine()
        _session_factory = create_session_factory(_engine)
    return _session_factory


def get_session() -> Generator[Session, None, None]:
    factory = _get_session_factory()
    with factory() as session:
        yield session


def require_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    session: Session = Depends(get_session),
) -> ApiKey:
    if credentials is None or not credentials.credentials.strip():
        raise HTTPException(status_code=401, detail="Fehlender oder ungültiger Authorization-Header")

    raw_key = credentials.credentials.strip()
    key_hash = hash_key(raw_key)

    api_key = session.execute(select(ApiKey).where(ApiKey.key_hash == key_hash)).scalar_one_or_none()
    if api_key is None:
        raise HTTPException(status_code=401, detail="Unbekannter API-Key")
    if api_key.status != "active":
        raise HTTPException(status_code=403, detail="API-Key ist gesperrt")

    api_key.last_used_at = datetime.now(timezone.utc)
    session.commit()

    return api_key


def load_configured_signer_config():
    """Lädt die instanzweite C2PA-Signierkonfiguration aus
    `USMEDIAKIT_C2PA_CERT_FILE`/`USMEDIAKIT_C2PA_KEY_FILE`. Anders als bei der CLI (die
    Zertifikat/Schlüssel pro Aufruf übergeben bekommt) ist das im Netzwerk-Dienst eine
    Instanz-Konfiguration, kein Request-Parameter — Zertifikate gehören nicht in einen
    JSON-Body."""
    from us_mediakit.c2pa.sign import SignerConfig

    cert_file = os.environ.get("USMEDIAKIT_C2PA_CERT_FILE")
    key_file = os.environ.get("USMEDIAKIT_C2PA_KEY_FILE")
    if not cert_file or not key_file:
        raise HTTPException(
            status_code=503,
            detail="C2PA-Signieren ist auf dieser Instanz nicht konfiguriert "
            "(USMEDIAKIT_C2PA_CERT_FILE/USMEDIAKIT_C2PA_KEY_FILE fehlen).",
        )
    with open(cert_file, "rb") as f:
        sign_cert = f.read()
    with open(key_file, "rb") as f:
        private_key = f.read()
    return SignerConfig(sign_cert=sign_cert, private_key=private_key)


def try_load_configured_signer_config():
    """Wie `load_configured_signer_config`, aber gibt None zurück statt eines Fehlers,
    wenn nichts konfiguriert ist — für Endpunkte, bei denen Signieren optional ist
    (z. B. `thumbnail` mit Provenienz-Propagation), im Gegensatz zu `c2pa/sign`, wo es
    der Zweck des Aufrufs ist."""
    try:
        return load_configured_signer_config()
    except HTTPException:
        return None


def _load_admin_token() -> str | None:
    token_file = os.environ.get("USMEDIAKIT_ADMIN_TOKEN_FILE")
    if token_file and os.path.exists(token_file):
        return open(token_file, encoding="utf-8").read().strip()
    return os.environ.get("USMEDIAKIT_ADMIN_TOKEN")


def require_admin_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> None:
    expected = _load_admin_token()
    if not expected:
        raise HTTPException(status_code=503, detail="Kein Admin-Token konfiguriert")

    if credentials is None or not credentials.credentials.strip():
        raise HTTPException(status_code=401, detail="Fehlender oder ungültiger Authorization-Header")

    provided = credentials.credentials.strip()
    if not secrets.compare_digest(provided, expected):
        raise HTTPException(status_code=403, detail="Ungültiges Admin-Token")
