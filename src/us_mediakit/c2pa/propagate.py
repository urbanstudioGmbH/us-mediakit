"""Provenienz-Propagation — die Pflichtprüfung aus Programmierplan Abschnitt 5a.

Betrifft jede derivat-erzeugende Operation: `thumbnail`, `ai_upscale`, `watermark`,
`meta.write` mit Re-Encode. Kein separat aufzurufendes Feature, sondern eine feste
Pipeline-Regel — `propagation_hook` erfüllt exakt die `ProvenanceHook`-Schnittstelle aus
`core.pipeline` und wird dort als der reale (nicht mehr No-Op-) Erweiterungspunkt
eingehängt.

Ablauf, unabhängig davon, ob der Aufrufer explizit danach fragt:

1. Besitzt die Quelle ein gültiges, lesbares C2PA-Manifest? → als Ingredient referenzieren.
2. Besitzt die Quelle IPTC/XMP `DigitalSourceType` ohne volles C2PA-Manifest?
3. Liefert der Aufrufer selbst `digital_source_type`/`actions`/`assertions` mit?

Trifft (1), (2) oder (3) zu, bekommt das Ergebnis ein neues, eigenes Manifest. Trifft
nichts davon zu, bleibt das Ergebnis unverändert — es wird nie eine Provenienz für einen
unbekannten Ursprung erfunden.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from us_mediakit.c2pa.read import read_manifest
from us_mediakit.c2pa.sign import IngredientRef, SignRequest, sign
from us_mediakit.core.formats import get_content_type, get_image_type_from_bytes
from us_mediakit.metadata.read import read_metadata

if TYPE_CHECKING:
    from us_mediakit.core.pipeline import ThumbnailRequest

_ACTION_LABELS = ("c2pa.actions", "c2pa.actions.v2")


def _extract_digital_source_type(manifest: dict[str, Any]) -> str | None:
    for assertion in manifest.get("assertions", []):
        if assertion.get("label") in _ACTION_LABELS:
            for action in assertion.get("data", {}).get("actions", []):
                source_type = action.get("digitalSourceType")
                if source_type:
                    return source_type
    return None


def _read_iptc_digital_source_type(data: bytes) -> str | None:
    try:
        tags = read_metadata(data)
    except Exception:  # noqa: BLE001 — exiftool nicht installiert/Datei nicht lesbar: kein Signal, kein Absturz
        return None
    return tags.get("XMP:DigitalSourceType") or tags.get("XMP-iptcExt:DigitalSourceType")


def propagate(
    *,
    source: bytes,
    result: bytes,
    request: ThumbnailRequest,
) -> bytes:
    """Reale Implementierung des Provenienz-Hooks. Signatur passend zu
    `core.pipeline.ProvenanceHook`."""
    if not request.carry_c2pa or request.c2pa_signer_config is None:
        return result

    source_mime_type = get_content_type(get_image_type_from_bytes(source) or "") or "image/jpeg"
    result_mime_type = get_content_type(request.output_format) or "image/jpeg"

    source_manifest = read_manifest(source, source_mime_type)
    ingredient = IngredientRef(data=source, mime_type=source_mime_type) if source_manifest else None

    digital_source_type = request.c2pa_digital_source_type
    if digital_source_type is None and source_manifest is not None:
        digital_source_type = _extract_digital_source_type(source_manifest)
    if digital_source_type is None:
        digital_source_type = _read_iptc_digital_source_type(source)

    if digital_source_type is None:
        return result

    sign_request = SignRequest(
        data=result,
        mime_type=result_mime_type,
        signer_config=request.c2pa_signer_config,
        digital_source_type=digital_source_type,
        # request.c2pa_action wird von core.pipeline vor dem Hook-Aufruf immer aus dem
        # Fit-Modus aufgelöst; der Fallback greift nur bei direkter Nutzung außerhalb
        # der Pipeline ohne vorherige Auflösung.
        action=request.c2pa_action or "c2pa.edited",
        extra_actions=request.c2pa_actions or [],
        extra_assertions=request.c2pa_assertions or [],
        ingredient=ingredient,
    )
    return sign(sign_request)
