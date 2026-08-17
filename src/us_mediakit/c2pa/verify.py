"""C2PA-Signatur/Trust-Chain prüfen."""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any

import c2pa


@dataclass
class VerificationResult:
    has_manifest: bool
    validation_state: str | None
    validation_results: dict[str, Any] | None
    active_manifest: dict[str, Any] | None


def verify(data: bytes, mime_type: str) -> VerificationResult:
    """Prüft Signatur und Trust-Chain. `validation_state` ist z. B. "Valid"/"Invalid".

    Ein selbst signiertes Testzertifikat ohne Trust-Anker liefert korrekt "Invalid" mit
    dem Grund `signingCredential.untrusted` — das ist erwartetes Verhalten, kein Fehler
    im Code. Für produktiv vertrauenswürdige Signaturen braucht es ein über das
    C2PA-Conformance-Programm ausgestelltes Zertifikat (siehe Programmierplan Abschnitt 9).
    """
    reader = c2pa.Reader.try_create(mime_type, io.BytesIO(data))
    if reader is None:
        return VerificationResult(
            has_manifest=False,
            validation_state=None,
            validation_results=None,
            active_manifest=None,
        )
    try:
        return VerificationResult(
            has_manifest=True,
            validation_state=reader.get_validation_state(),
            validation_results=reader.get_validation_results(),
            active_manifest=reader.get_active_manifest(),
        )
    finally:
        reader.close()
