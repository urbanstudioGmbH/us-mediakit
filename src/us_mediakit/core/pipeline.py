"""Kern-Pipeline: decode → transform → re-encode → metadata merge.

Fester Erweiterungspunkt für die Provenienz-Prüfung (siehe Abschnitt 5a des
Programmierplans): `provenance_hook` wird nach dem Transform-Schritt aufgerufen, bevor
das Ergebnis zurückgegeben wird. In Phase 1 ist das ein No-Op-Platzhalter; Phase 3 hängt
hier die echte C2PA-Propagationslogik ein, ohne dass die Pipeline-Struktur nachträglich
geändert werden muss. Die Metadaten-Übernahme (Phase 2) wird dagegen direkt in diese
Pipeline fest verdrahtet, sobald `metadata/` existiert — kein eigener Hook, weil sie für
jede Operation ausnahmslos gilt.
"""

from __future__ import annotations

import io
from dataclasses import dataclass, field
from typing import Any, Protocol

from PIL import Image

from us_mediakit.core import formats, security, svg, transform
from us_mediakit.media import pdf as pdf_media
from us_mediakit.media import video as video_media
from us_mediakit.metadata.exiftool_client import ExifToolClient
from us_mediakit.metadata.write import copy_metadata_from

DEFAULT_QUALITY = 80

_SAVE_FORMAT = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP", "gif": "GIF"}


@dataclass
class ThumbnailRequest:
    source: bytes
    mode: transform.FitMode
    output_format: str = "jpg"
    crop: str | None = None
    aspect_ratio: str | None = None
    alignx: str | float | None = None
    aligny: str | float | None = None
    zoom: str | float | None = None
    ai: str | None = None
    is_video: bool = False
    is_pdf: bool = False
    pdf_page: int = 1
    video_seek_seconds: float = video_media.DEFAULT_SEEK_SECONDS
    carry_metadata: bool = True
    strip_gps: bool = False
    carry_c2pa: bool = True
    c2pa_signer_config: Any = None  # us_mediakit.c2pa.sign.SignerConfig | None
    c2pa_digital_source_type: str | None = None
    c2pa_action: str | None = None  # None = automatisch aus dem Fit-Modus ableiten
    c2pa_actions: list[dict[str, Any]] = field(default_factory=list)
    c2pa_assertions: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class ThumbnailResult:
    data: bytes
    content_type: str
    target_width: int
    target_height: int
    source_image_type: str | None


class ProvenanceHook(Protocol):
    def __call__(self, *, source: bytes, result: bytes, request: ThumbnailRequest) -> bytes: ...


def _default_provenance_hook(*, source: bytes, result: bytes, request: ThumbnailRequest) -> bytes:
    """Echte Provenienz-Propagation aus Phase 3 (siehe Abschnitt 5a). Verhält sich wie ein
    No-Op, solange kein `c2pa_signer_config` konfiguriert ist — der Import liegt hier
    lokal in der Funktion, um einen Modul-Ladezyklus core.pipeline ↔ c2pa.propagate zu
    vermeiden (propagate.py importiert ThumbnailRequest nur für Typprüfungen)."""
    from us_mediakit.c2pa.propagate import propagate

    return propagate(source=source, result=result, request=request)


_CROP_FIT_MODES = ("crop", "greedycrop")


def generate_thumbnail(
    request: ThumbnailRequest,
    *,
    provenance_hook: ProvenanceHook = _default_provenance_hook,
    exiftool_client: ExifToolClient | None = None,
) -> ThumbnailResult:
    original_source = request.source
    source = request.source

    if request.is_video:
        source = video_media.extract_frame(source, seek_seconds=request.video_seek_seconds)
    elif request.is_pdf:
        source = pdf_media.render_page(source, page=request.pdf_page)

    security.check_file_size(source)
    source_image_type = formats.get_image_type_from_bytes(source)

    if source_image_type == "svg":
        sanitized = svg.sanitize_svg(source)
        return ThumbnailResult(
            data=sanitized,
            content_type="image/svg+xml",
            target_width=0,
            target_height=0,
            source_image_type="svg",
        )

    # Pixelanzahl-Check bewusst erst hier: SVG ist kein Rasterformat, das sich über
    # PIL.Image.open() prüfen ließe (siehe Passthrough-Zweig oben) — die reine
    # Dateigrößenprüfung lief für beide Zweige bereits gemeinsam oben.
    security.check_image_size(source)

    with Image.open(io.BytesIO(source)) as decoded:
        decoded.load()
        fit_result = transform.apply_fit(
            decoded,
            request.mode,
            crop=request.crop,
            aspect_ratio=request.aspect_ratio,
            alignx=request.alignx,
            aligny=request.aligny,
            zoom=request.zoom,
            ai=request.ai,
        )

    save_format = _SAVE_FORMAT.get(request.output_format.lower(), "JPEG")
    quality = request.mode.get("quality", DEFAULT_QUALITY)

    image_to_save = fit_result.image
    if save_format == "JPEG" and image_to_save.mode == "RGBA":
        image_to_save = image_to_save.convert("RGB")

    buffer = io.BytesIO()
    save_kwargs = {"quality": quality} if save_format in ("JPEG", "WEBP") else {}
    image_to_save.save(buffer, format=save_format, **save_kwargs)
    encoded = buffer.getvalue()

    # Metadaten-Übernahme (Phase 2, siehe Abschnitt 7 des Programmierplans): jede erzeugte
    # Variante bekommt die EXIF/IPTC/XMP-Daten des Originals zurückgeschrieben — kein
    # separat aufzurufender Schritt. Bewusst ausgenommen: Video-/PDF-Quellen, weil das
    # extrahierte Frame keine sinnvoll übertragbaren Bild-Metadaten besitzt und die
    # Container-Metadaten von Video/PDF ein eigenes, hier nicht spezifiziertes Mapping
    # bräuchten (dokumentierte Scope-Grenze für Phase 2, keine übersehene Lücke).
    if request.carry_metadata and not (request.is_video or request.is_pdf):
        encoded = copy_metadata_from(
            original_source,
            encoded,
            exclude_groups=["GPS"] if request.strip_gps else None,
            client=exiftool_client,
        )

    if request.c2pa_action is None:
        effective_fit = request.crop or request.mode.get("fit")
        request.c2pa_action = "c2pa.cropped" if effective_fit in _CROP_FIT_MODES else "c2pa.resized"

    encoded = provenance_hook(source=source, result=encoded, request=request)

    return ThumbnailResult(
        data=encoded,
        content_type=formats.get_content_type(request.output_format) or "application/octet-stream",
        target_width=fit_result.target_width,
        target_height=fit_result.target_height,
        source_image_type=source_image_type,
    )
