"""Pydantic-Schemas für die HTTP-Ebene.

Die Bibliotheks- und CLI-Ebene nutzt Dataclasses (`ThumbnailRequest`, `SignRequest`,
...); diese Datei ist die Schema-Quelle *für die HTTP-Ebene* — die Endpunkte
übersetzen zwischen Pydantic-Request und den bestehenden Dataclasses.

Bilddaten reisen als Base64-String im JSON-Body.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class OperationRequestBase(BaseModel):
    request_id: str = Field(description="Idempotenz-Key; bei Wiederholung keine erneute Abrechnung")
    dry_run: bool = False


class C2paOverride(BaseModel):
    digital_source_type: str | None = None
    actions: list[dict[str, Any]] = Field(default_factory=list)
    assertions: list[dict[str, Any]] = Field(default_factory=list)


class ThumbnailApiRequest(OperationRequestBase):
    source: str = Field(description="Bilddaten, Base64-kodiert")
    mode: str = Field(description="Preset-Name aus imageformats.json")
    output_format: str = "jpg"
    crop: str | None = None
    aspect_ratio: str | None = None
    zoom: str | float | None = None
    is_video: bool = False
    video_seek_seconds: float | None = Field(
        default=None, description="Zeitpunkt für die Frame-Extraktion bei is_video, in Sekunden. Ohne Angabe gilt der Bibliotheks-Default (siehe media.video.DEFAULT_SEEK_SECONDS)."
    )
    is_pdf: bool = False
    pdf_page: int = 1
    carry_metadata: bool = True
    strip_gps: bool = False
    carry_c2pa: bool = True
    c2pa: C2paOverride | None = None


class OperationResponseBase(BaseModel):
    request_id: str
    credits_charged: float | None = None
    dry_run: bool = False
    estimated_credits: float | None = None
    confidence: str | None = None


class ThumbnailApiResponse(OperationResponseBase):
    data: str | None = None
    content_type: str | None = None
    target_width: int | None = None
    target_height: int | None = None


class MetaReadApiRequest(OperationRequestBase):
    source: str


class MetaReadApiResponse(OperationResponseBase):
    tags: dict[str, Any] | None = None


class MetaWriteApiRequest(OperationRequestBase):
    source: str
    tags: dict[str, str] = Field(default_factory=dict)
    strip_gps: bool = False


class MetaWriteApiResponse(OperationResponseBase):
    data: str | None = None


class C2paVerifyApiRequest(OperationRequestBase):
    source: str
    mime_type: str = "image/jpeg"


class C2paVerifyApiResponse(OperationResponseBase):
    has_manifest: bool = False
    validation_state: str | None = None
    validation_results: dict[str, Any] | None = None


class C2paSignApiRequest(OperationRequestBase):
    source: str
    mime_type: str = "image/jpeg"
    digital_source_type: str
    actions: list[dict[str, Any]] = Field(default_factory=list)
    assertions: list[dict[str, Any]] = Field(default_factory=list)


class C2paSignApiResponse(OperationResponseBase):
    data: str | None = None


class CaptionApiRequest(OperationRequestBase):
    source: str
    write_to: list[str] = Field(default_factory=lambda: ["IPTC:ObjectName", "XMP-dc:Description"])
    mirror_exif: bool = False
    only_if_empty: bool = True
    provider_url: str | None = None
    provider_key: str | None = None
    provider_model: str | None = None


class CaptionApiResponse(OperationResponseBase):
    data: str | None = None
    caption: str | None = None
    skipped_existing: bool = False


class AiUpscaleApiRequest(OperationRequestBase):
    source: str
    provider: str | None = None
    target_width: int | None = None
    target_height: int | None = None
    restore_faces: bool = False


class AiUpscaleApiResponse(OperationResponseBase):
    data: str | None = None
    provider: str | None = None
    ai_upscale_fallback: bool = False


class WatermarkApiRequest(OperationRequestBase):
    source: str
    mode: str = Field(description='"visible" oder "invisible"')
    output_format: str = "jpeg"
    # sichtbar:
    logo: str | None = Field(default=None, description="Logo, Base64-kodiert")
    text: str | None = None
    position: str = "bottom-right"
    opacity: float = 0.6
    # unsichtbar:
    reference_id: str | None = Field(
        default=None, description="4 Byte hex-kodiert; ohne Angabe wird eine erzeugt"
    )


class WatermarkApiResponse(OperationResponseBase):
    data: str | None = None
    reference_id: str | None = None  # hex, nur bei mode="invisible"


class WatermarkDetectApiRequest(OperationRequestBase):
    source: str


class WatermarkDetectApiResponse(OperationResponseBase):
    detected: bool = False
    reference_id: str | None = None  # hex


class AnimatedWebpApiRequest(OperationRequestBase):
    source: str = Field(description="Videodaten, Base64-kodiert")
    start_seconds: float = 0.0
    duration_seconds: float = 3.0
    width: int | None = None
    fps: int = 12
    quality: int = 75


class AnimatedWebpApiResponse(OperationResponseBase):
    data: str | None = None
    frame_count: int | None = None
    target_width: int | None = None
    target_height: int | None = None


class HealthResponse(BaseModel):
    status: str = "ok"


class ApiKeyCreateRequest(BaseModel):
    account_ref: str
    label: str


class ApiKeyCreateResponse(BaseModel):
    id: str
    api_key: str = Field(description="Nur bei Erzeugung sichtbar, wird nirgendwo gespeichert")
    key_prefix: str


class UsageEventOut(BaseModel):
    id: int
    request_id: str
    operation: str
    provider: str | None
    status: str
    occurred_at: str
    bytes_in: int
    bytes_out: int
    credits: float
    credits_table_version: int
    external_cost_micros: int | None
    duration_ms: int


class UsageExportResponse(BaseModel):
    events: list[UsageEventOut]
    next_since_id: int | None
