"""`request_id`-Deduplizierung.

Zwei getrennte Aspekte, die beide zur Idempotenz-Anforderung aus Programmierplan
Abschnitt 5 gehören:

1. **Kein doppelter `usage_events`-Eintrag** — durchgesetzt über die `UNIQUE`-Constraint
   auf `UsageEvent.request_id` selbst; `is_duplicate_request` prüft das vorab, damit die
   Pipeline für eine Wiederholung gar nicht erst erneut läuft.
2. **Dieselbe Antwort zurückgeben, nicht neu rechnen** — dafür braucht es einen
   Zwischenspeicher für die tatsächlichen Ergebnis-Bytes, die in `usage_events` bewusst
   NICHT liegen (das bleibt eine schlanke Abrechnungstabelle, kein Blob-Speicher).
   `ResponseCache` deckt das für einen einzelnen Worker-Prozess ab (bounded, TTL-basiert).
   **Bekannte Grenze:** Bei mehreren Worker-Prozessen (z. B. mehrere uvicorn-Worker
   hinter nginx) sieht nicht jeder Worker den Cache der anderen — ein Retry, der auf
   einem anderen Worker landet, würde die Pipeline erneut durchlaufen (aber wegen (1)
   ohne doppelte Abrechnung). Für einen echten Mehr-Worker-Cache wäre ein gemeinsamer
   Speicher (z. B. Redis) nötig — bewusst nicht Teil dieser Phase, da nicht in
   Abschnitt 2 als Abhängigkeit vorgesehen.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from us_mediakit.db.models import UsageEvent

DEFAULT_CACHE_TTL_SECONDS = 300
DEFAULT_CACHE_MAX_ENTRIES = 1000


def is_duplicate_request(session: Session, request_id: str) -> bool:
    existing = session.execute(
        select(UsageEvent.id).where(UsageEvent.request_id == request_id)
    ).first()
    return existing is not None


@dataclass
class _CacheEntry:
    value: Any
    expires_at: float


class ResponseCache:
    """Bounded, TTL-basierter In-Prozess-Cache für bereits berechnete Antworten."""

    def __init__(
        self,
        *,
        ttl_seconds: float = DEFAULT_CACHE_TTL_SECONDS,
        max_entries: int = DEFAULT_CACHE_MAX_ENTRIES,
    ) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._entries: dict[str, _CacheEntry] = {}
        self._lock = threading.Lock()

    def get(self, request_id: str) -> Any | None:
        with self._lock:
            entry = self._entries.get(request_id)
            if entry is None:
                return None
            if entry.expires_at < time.monotonic():
                del self._entries[request_id]
                return None
            return entry.value

    def set(self, request_id: str, value: Any) -> None:
        with self._lock:
            if len(self._entries) >= self._max_entries:
                oldest_key = min(self._entries, key=lambda k: self._entries[k].expires_at)
                del self._entries[oldest_key]
            self._entries[request_id] = _CacheEntry(
                value=value, expires_at=time.monotonic() + self._ttl_seconds
            )
