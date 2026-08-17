"""C2PA-Manifest lesen — Provenienzkette, Assertions, Ingredients als JSON."""

from __future__ import annotations

import io
from typing import Any

import c2pa


def read_manifest(data: bytes, mime_type: str) -> dict[str, Any] | None:
    """Aktives C2PA-Manifest als dict, oder None, wenn die Datei keines enthält."""
    reader = c2pa.Reader.try_create(mime_type, io.BytesIO(data))
    if reader is None:
        return None
    try:
        return reader.get_active_manifest()
    finally:
        reader.close()


def has_manifest(data: bytes, mime_type: str) -> bool:
    """Günstiger Vorab-Check, ob überhaupt ein C2PA-Manifest vorhanden ist.

    Wird von der Provenienz-Prüfung aus Abschnitt 5a des Programmierplans genutzt, bevor
    ein neues Manifest für ein Derivat erzeugt wird.
    """
    return read_manifest(data, mime_type) is not None
