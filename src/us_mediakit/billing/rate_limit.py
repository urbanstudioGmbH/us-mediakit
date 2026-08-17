"""Anwendungs-Rate-Limiting: zwei getrennte Mechanismen.

- **Credits/Minute pro Plan-Tier** — welcher Tarif ein `account_ref` hat, lebt im
  Kundenbereich, nicht im Datenmodell von us-mediakit (`ApiKey` kennt keinen Tarif).
  `CreditsRateLimiter` ist deshalb bewusst tarif-agnostisch: er bekommt das Limit pro
  Aufruf übergeben, statt es selbst nachzuschlagen. Die tatsächliche Zuordnung
  Account → Limit ist Sache des Kundenbereichs, nicht Teil dieses Bausteins.
- **Tarifunabhängige Zusatzschwelle für gleichzeitige Video-/PDF-Jobs** —
  `ConcurrencyLimiter`, unabhängig vom Tarif, schützt den Server unabhängig von der
  Abrechnung vor zu vielen gleichzeitig laufenden ffmpeg/pdftoppm-Prozessen.

Beide sind In-Prozess-Zustand — bei mehreren Worker-Prozessen sieht jeder Worker nur
seinen eigenen Zähler (dieselbe Grenze wie beim `ResponseCache`, siehe `idempotency.py`).
"""

from __future__ import annotations

import threading
import time
from collections import deque


class CreditsRateLimiter:
    """Sliding-Window-Limiter über Credits pro Zeitfenster, pro `account_ref`."""

    def __init__(self, *, window_seconds: float = 60.0) -> None:
        self._window_seconds = window_seconds
        self._windows: dict[str, deque[tuple[float, float]]] = {}
        self._lock = threading.Lock()

    def check_and_record(self, account_ref: str, credits: float, *, limit_per_window: float) -> bool:
        """True + verbucht `credits`, wenn das Limit noch nicht erreicht ist. Sonst False,
        ohne etwas zu verbuchen."""
        now = time.monotonic()
        with self._lock:
            window = self._windows.setdefault(account_ref, deque())
            cutoff = now - self._window_seconds
            while window and window[0][0] < cutoff:
                window.popleft()

            current_total = sum(c for _, c in window)
            if current_total + credits > limit_per_window:
                return False

            window.append((now, credits))
            return True


class ConcurrencyLimiter:
    """Begrenzt die Anzahl gleichzeitig laufender Jobs eines Typs (z. B. Video/PDF)."""

    def __init__(self, *, max_concurrent: int) -> None:
        self._semaphore = threading.Semaphore(max_concurrent)

    def try_acquire(self) -> bool:
        return self._semaphore.acquire(blocking=False)

    def release(self) -> None:
        self._semaphore.release()

    def __enter__(self) -> ConcurrencyLimiter:  # noqa: PYI034 — typing.Self braucht Py 3.11+, wir unterstützen 3.10
        if not self.try_acquire():
            raise ConcurrencyLimitExceeded()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.release()


class ConcurrencyLimitExceeded(RuntimeError):
    pass
